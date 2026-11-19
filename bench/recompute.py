#!/usr/bin/env python3
"""
Deterministic summary recomputation from raw records (ADR-0004)
===============================================================
Seam: recompute_summary(raw_dir, run_id=None) -> dict

Reads only results/v2/raw*/<run_id>__<H>.jsonl, aggregates per (hypothesis, condition,
system) per seed, then across seeds (mean and 95% t-interval), and evaluates the
pre-registered predictions via bench.verdicts.  Output is byte-for-byte reproducible:
records are sorted before aggregation, sums use math.fsum, and JSON is written with
sorted keys.

    python -m bench.recompute --raw-dir results/v2/raw --out results/v2/summary.json
    python -m bench.recompute --raw-dir results/v2/raw --check results/v2/summary.json
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

SUMMARY_SCHEMA = "prism-ann-v2-summary/1"


# H3: bins of the per-query measured correlation r (PROTOCOL_v2 H3v2)
def r_bin(r: Optional[float]) -> Optional[str]:
    """r <= 0.5 -> r_le_0.5 ; r >= 2 -> r_ge_2 ; otherwise r_0.5_to_2."""
    if r is None:
        return None
    if r <= 0.5:
        return "r_le_0.5"
    if r >= 2.0:
        return "r_ge_2"
    return "r_0.5_to_2"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_records(raw_dir: str, run_id: Optional[str] = None) -> Tuple[str, List[Dict[str, Any]]]:
    paths = sorted(glob.glob(os.path.join(raw_dir, "*.jsonl")))
    if not paths:
        raise FileNotFoundError(f"no raw *.jsonl files in {raw_dir}")
    run_ids = sorted({os.path.basename(p).split("__")[0] for p in paths})
    if run_id is None:
        if len(run_ids) != 1:
            raise ValueError(f"raw dir holds {len(run_ids)} run_ids {run_ids}; pass --run-id")
        run_id = run_ids[0]
    recs: List[Dict[str, Any]] = []
    for p in paths:
        if os.path.basename(p).split("__")[0] != run_id:
            continue
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    if r.get("run_id") != run_id:
                        raise ValueError(f"record run_id {r.get('run_id')} != file run_id {run_id} in {p}")
                    recs.append(r)
    recs.sort(key=lambda r: (r["hypothesis"], r["system"], int(r["seed"]), str(r["query_id"])))
    return run_id, recs


# ---------------------------------------------------------------------------
# Statistics (deterministic)
# ---------------------------------------------------------------------------
def _mean(xs: List[float]) -> Optional[float]:
    return math.fsum(xs) / len(xs) if xs else None


def _quantile(xs: List[float], q: float) -> Optional[float]:
    """Linear-interpolated quantile on a sorted copy (numpy 'linear' definition)."""
    if not xs:
        return None
    s = sorted(xs)
    pos = (len(s) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _t975(df: int) -> float:
    from scipy.stats import t as student_t
    return float(student_t.ppf(0.975, df))


def across_seeds(values: List[Optional[float]]) -> Dict[str, Any]:
    vals = [v for v in values if v is not None]
    n = len(vals)
    if n == 0:
        return {"mean": None, "ci95": None, "n_seeds": 0, "per_seed": values}
    m = math.fsum(vals) / n
    if n > 1:
        sd = math.sqrt(math.fsum((v - m) ** 2 for v in vals) / (n - 1))
        half = _t975(n - 1) * sd / math.sqrt(n)
    else:
        half = None
    return {"mean": m, "ci95": half, "n_seeds": n, "per_seed": values}


def seed_metrics(recs: List[Dict[str, Any]]) -> Dict[str, Any]:
    rec_vals = [float(r["recall"]) for r in recs if r.get("recall") is not None]
    dist_vals = [float(r["distance_computations"]) for r in recs if r.get("distance_computations") is not None]
    lat_ms = [r["wall_ns"] / 1e6 for r in recs]
    return {
        "n": len(recs),
        "recall_mean": _mean(rec_vals),
        "dist_mean": _mean(dist_vals),
        "latency_ms_median": _quantile(lat_ms, 0.5),
        "latency_ms_p95": _quantile(lat_ms, 0.95),
        "latency_ms_mean": _mean(lat_ms),
    }


def aggregate_group(recs: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_seed: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for r in recs:
        by_seed[int(r["seed"])].append(r)
    seeds = sorted(by_seed)
    per_seed = {str(s): seed_metrics(by_seed[s]) for s in seeds}
    out: Dict[str, Any] = {"seeds": seeds, "per_seed": per_seed, "n_total": len(recs)}
    for key in ("recall_mean", "dist_mean", "latency_ms_median", "latency_ms_p95"):
        out[key] = across_seeds([per_seed[str(s)][key] for s in seeds])
    return out


# ---------------------------------------------------------------------------
# Hypothesis-specific grouping
# ---------------------------------------------------------------------------
def _group(recs: Iterable[Dict[str, Any]], keyfn) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    g: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for r in recs:
        k = keyfn(r)
        if k is not None:
            g[k].append(r)
    return g


def summarize_ann(recs: List[Dict[str, Any]], hyp: str) -> Dict[str, Any]:
    """H2: grouped by target selectivity.  H3: grouped by measured-r bin and by regime."""
    out: Dict[str, Any] = {}
    if hyp == "H2":
        groups = _group(recs, lambda r: (f"S={r['condition']['S_target']}", r["system"]))
    else:
        groups = _group(recs, lambda r: (r_bin(r["condition"].get("r_measured")), r["system"]))
        regime = _group(recs, lambda r: (f"regime={r['condition'].get('regime')}", r["system"]))
        groups.update(regime)
    for (cond, system), g in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        if cond is None:
            continue
        out.setdefault(cond, {})[system] = aggregate_group(g)
    # condition-level descriptors (S actual / r measured) from the per-query conditions
    desc: Dict[str, Any] = {}
    for cond in out:
        rs = [r for (c, _s), g in groups.items() if c == cond for r in g]
        s_act = sorted({(str(r["seed"]), str(r["query_id"])): r["condition"].get("S_actual") for r in rs}.items())
        r_meas = sorted({(str(r["seed"]), str(r["query_id"])): r["condition"].get("r_measured") for r in rs}.items())
        s_vals = [v for _k, v in s_act if v is not None]
        r_vals = [v for _k, v in r_meas if v is not None]
        desc[cond] = {
            "n_queries_x_seeds": len(s_act),
            "S_actual_mean": _mean(s_vals),
            "r_measured_mean": _mean(r_vals),
            "r_measured_median": _quantile(r_vals, 0.5),
        }
    return {"by_condition": out, "condition_descriptors": desc}


def summarize_h1(recs: List[Dict[str, Any]]) -> Dict[str, Any]:
    oracle = [r for r in recs if r["system"] == "H1-oracle-check"]
    mism_docs = sum(int(r["extra"]["mismatch_docs"]) for r in oracle)
    mism_chunks = sum(int(r["extra"]["mismatch_chunks"]) for r in oracle)
    within = [bool(r["extra"]["within_bound"]) for r in oracle]
    tokens = [int(r["extra"]["tokens_pos"]) for r in oracle]
    auth_docs = [int(r["extra"]["n_auth_docs"]) for r in oracle]
    out: Dict[str, Any] = {
        "n_principals": len(oracle),
        "n_principals_per_seed": {str(s): sum(1 for r in oracle if int(r["seed"]) == s)
                                  for s in sorted({int(r["seed"]) for r in oracle})},
        "mismatch_docs_total": mism_docs,
        "mismatch_chunks_total": mism_chunks,
        "principals_with_any_mismatch": sum(
            1 for r in oracle if int(r["extra"]["mismatch_docs"]) or int(r["extra"]["mismatch_chunks"])),
        "within_bound_fraction": (sum(within) / len(within)) if within else None,
        "tokens_pos_max": max(tokens) if tokens else None,
        "tokens_pos_median": _quantile([float(t) for t in tokens], 0.5),
        "auth_docs_median": _quantile([float(a) for a in auth_docs], 0.5),
        "m_denies_range": [min(int(r["extra"]["m_denies"]) for r in oracle),
                           max(int(r["extra"]["m_denies"]) for r in oracle)] if oracle else None,
        "timing": {},
    }
    timing_systems = sorted({r["system"] for r in recs if r["system"] != "H1-oracle-check"})
    for sub_name, pred in (("all", lambda r: True),
                           ("auth_docs_ge_1000", lambda r: int(r["extra"]["n_auth_docs"]) >= 1000)):
        block: Dict[str, Any] = {}
        for sysname in timing_systems:
            rs = [r for r in recs if r["system"] == sysname and pred(r)]
            lat = [r["wall_ns"] / 1e6 for r in rs]
            block[sysname] = {
                "n": len(rs),
                "latency_ms_median_pooled": _quantile(lat, 0.5),
                "latency_ms_p95_pooled": _quantile(lat, 0.95),
                "by_seed": aggregate_group(rs) if rs else None,
            }
        out["timing"][sub_name] = block
    return out


def summarize_h4(recs: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"systems": {}}
    for sysname in sorted({r["system"] for r in recs}):
        rs = [r for r in recs if r["system"] == sysname]
        lat = [r["wall_ns"] / 1e6 for r in rs]
        writes = [r["extra"].get("vector_writes") for r in rs if r["extra"].get("vector_writes") is not None]
        rows = [r["extra"].get("rows_affected") for r in rs if r["extra"].get("rows_affected") is not None]
        out["systems"][sysname] = {
            "n_trials": len(rs),
            "latency_ms_median": _quantile(lat, 0.5),
            "latency_ms_min": min(lat) if lat else None,
            "latency_ms_max": max(lat) if lat else None,
            "vector_writes_max": max(writes) if writes else None,
            "rows_affected_median": _quantile([float(x) for x in rows], 0.5) if rows else None,
            "docs_covered": sorted({r["condition"].get("docs_covered") for r in rs
                                    if r["condition"].get("docs_covered") is not None}),
            "chunks_covered": sorted({r["condition"].get("chunks_covered") for r in rs
                                      if r["condition"].get("chunks_covered") is not None}),
        }
    return out


# ---------------------------------------------------------------------------
# Top level
# ---------------------------------------------------------------------------
def recompute_summary(raw_dir: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    from bench import verdicts

    run_id, recs = load_records(raw_dir, run_id)
    by_h: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in recs:
        by_h[r["hypothesis"]].append(r)
    shas = sorted({r["git_sha"] for r in recs})
    summary: Dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "run_id": run_id,
        "run_types": sorted({r["run_type"] for r in recs}),
        "git_shas": shas,
        "freeze_match_all": all(bool(r["freeze_match"]) for r in recs),
        "n_records": len(recs),
        "n_records_by_hypothesis": {h: len(v) for h, v in sorted(by_h.items())},
        "systems_by_hypothesis": {h: sorted({r["system"] for r in v}) for h, v in sorted(by_h.items())},
        "hypotheses": {},
    }
    if "H1" in by_h:
        summary["hypotheses"]["H1"] = summarize_h1(by_h["H1"])
    for h in ("H2", "H3"):
        if h in by_h:
            summary["hypotheses"][h] = summarize_ann(by_h[h], h)
    if "H4" in by_h:
        summary["hypotheses"]["H4"] = summarize_h4(by_h["H4"])
    summary["verdicts"] = verdicts.evaluate(summary)
    return summary


def _clean(o: Any) -> Any:
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def dumps_summary(summary: Dict[str, Any]) -> str:
    return json.dumps(_clean(summary), sort_keys=True, indent=1, allow_nan=False) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Recompute v2 summary from raw records")
    p.add_argument("--raw-dir", default=os.path.join(REPO_ROOT, "results", "v2", "raw"))
    p.add_argument("--run-id", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--check", default=None, help="exit 1 unless recomputation equals this file byte-for-byte")
    a = p.parse_args(argv)
    text = dumps_summary(recompute_summary(a.raw_dir, a.run_id))
    if a.check:
        with open(a.check, "r", encoding="utf-8") as f:
            same = f.read() == text
        print(f"[recompute] {'MATCH' if same else 'MISMATCH'}: {a.check}")
        return 0 if same else 1
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[recompute] wrote {a.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
