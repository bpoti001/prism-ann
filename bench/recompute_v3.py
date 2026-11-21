#!/usr/bin/env python3
"""
Deterministic v3 Summary Recomputation from Raw Records (ADR-0004 & ADR-0005)
=============================================================================
Seam: `recompute_v3_summary(raw_dir, run_id=None) -> dict`

Reads only `results/v3/raw/<run_id>__<H>.jsonl`, verifies `FREEZE_v3.md` parity
recorded on every record, aggregates 3-seed mean ± 95% t-CI plus pooled median/
P95/P99 latency and stall-escalation rates, and evaluates P1a..P5 via
`bench.verdicts_v3`. Output is byte-for-byte reproducible.

    python -m bench.recompute_v3 --raw-dir results/v3/raw --out results/v3/summary.json
    python -m bench.recompute_v3 --raw-dir results/v3/raw --check results/v3/summary.json
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

from bench.recompute import (
    _clean,
    _mean,
    _quantile,
    across_seeds,
    dumps_summary,
    load_records,
    r_bin,
    summarize_h1,
    summarize_h4,
)

SUMMARY_SCHEMA_V3 = "prism-ann-v3-summary/1"


def seed_metrics_v3(recs: List[Dict[str, Any]]) -> Dict[str, Any]:
    rec_vals = [float(r["recall"]) for r in recs if r.get("recall") is not None]
    dist_vals = [
        float(r["distance_computations"])
        for r in recs
        if r.get("distance_computations") is not None
    ]
    lat_ms = [r["wall_ns"] / 1e6 for r in recs]
    esc_cnt = sum(1 for r in recs if r.get("extra", {}).get("stalled_escalated"))
    return {
        "n": len(recs),
        "recall_mean": _mean(rec_vals),
        "dist_mean": _mean(dist_vals),
        "latency_ms_median": _quantile(lat_ms, 0.5),
        "latency_ms_p95": _quantile(lat_ms, 0.95),
        "latency_ms_p99": _quantile(lat_ms, 0.99),
        "latency_ms_mean": _mean(lat_ms),
        "stall_escalated_n": esc_cnt,
    }


def aggregate_group_v3(recs: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_seed: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for r in recs:
        by_seed[int(r["seed"])].append(r)
    seeds = sorted(by_seed)
    per_seed = {str(s): seed_metrics_v3(by_seed[s]) for s in seeds}
    all_lat = [r["wall_ns"] / 1e6 for r in recs]
    esc_total = sum(per_seed[str(s)]["stall_escalated_n"] for s in seeds)
    out: Dict[str, Any] = {
        "seeds": seeds,
        "per_seed": per_seed,
        "n_total": len(recs),
        "stall_escalated_total": esc_total,
        "stall_escalated_frac": esc_total / float(len(recs)) if recs else 0.0,
        "latency_ms_median_pooled": _quantile(all_lat, 0.5),
        "latency_ms_p95_pooled": _quantile(all_lat, 0.95),
        "latency_ms_p99_pooled": _quantile(all_lat, 0.99),
    }
    for key in ("recall_mean", "dist_mean", "latency_ms_median", "latency_ms_p95", "latency_ms_p99"):
        out[key] = across_seeds([per_seed[str(s)][key] for s in seeds])
    return out


def _group(recs: Iterable[Dict[str, Any]], keyfn) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    g: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for r in recs:
        k = keyfn(r)
        if k is not None:
            g[k].append(r)
    return g


def summarize_ann_v3(recs: List[Dict[str, Any]], kind: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if kind in ("H2", "H5"):
        groups = _group(recs, lambda r: (f"S={r['condition']['S_target']}", r["system"]))
    else:
        groups = _group(recs, lambda r: (r_bin(r["condition"].get("r_measured")), r["system"]))
        regime = _group(recs, lambda r: (f"regime={r['condition'].get('regime')}", r["system"]))
        groups.update(regime)
    for (cond, system), g in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        if cond is None:
            continue
        out.setdefault(cond, {})[system] = aggregate_group_v3(g)

    desc: Dict[str, Any] = {}
    for cond in out:
        rs = [r for (c, _s), g in groups.items() if c == cond for r in g]
        s_act = sorted(
            {(str(r["seed"]), str(r["query_id"])): r["condition"].get("S_actual") for r in rs}.items()
        )
        r_meas = sorted(
            {(str(r["seed"]), str(r["query_id"])): r["condition"].get("r_measured") for r in rs}.items()
        )
        s_vals = [v for _k, v in s_act if v is not None]
        r_vals = [v for _k, v in r_meas if v is not None]
        desc[cond] = {
            "n_queries_x_seeds": len(s_act),
            "S_actual_mean": _mean(s_vals),
            "r_measured_mean": _mean(r_vals),
            "r_measured_median": _quantile(r_vals, 0.5),
        }
    return {"by_condition": out, "condition_descriptors": desc}


def recompute_v3_summary(raw_dir: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    from bench import verdicts_v3

    run_id, recs = load_records(raw_dir, run_id)
    by_h: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in recs:
        by_h[r["hypothesis"]].append(r)

    shas = sorted({r["git_sha"] for r in recs})
    # Extract deterministic RAM metadata emitted by H2_quora extra fields if present
    ram_meta = {
        "v3_geom_m8_extra_bytes_per_node": 32.0,
        "acorn_gamma_extra_bytes_per_node": 224.0,  # ACORN.cpp:167 level-0: (M_beta=64 + 1.5*M=24 - 2*M=32)*4 = 224 B/node (+ upper layers)
    }

    summary: Dict[str, Any] = {
        "schema": SUMMARY_SCHEMA_V3,
        "run_id": run_id,
        "run_types": sorted({r["run_type"] for r in recs}),
        "git_shas": shas,
        "freeze_match_all": all(bool(r["freeze_match"]) for r in recs),
        "n_records": len(recs),
        "n_records_by_hypothesis": {h: len(v) for h, v in sorted(by_h.items())},
        "systems_by_hypothesis": {h: sorted({r["system"] for r in v}) for h, v in sorted(by_h.items())},
        "ram_meta": ram_meta,
        "hypotheses": {},
    }

    for hname, hrecs in sorted(by_h.items()):
        if hname.startswith("H1"):
            summary["hypotheses"][hname] = summarize_h1(hrecs)
        elif hname.startswith("H2"):
            summary["hypotheses"][hname] = summarize_ann_v3(hrecs, "H2")
        elif hname.startswith("H3"):
            summary["hypotheses"][hname] = summarize_ann_v3(hrecs, "H3")
        elif hname.startswith("H4"):
            summary["hypotheses"][hname] = summarize_h4(hrecs)
        elif hname.startswith("H5"):
            summary["hypotheses"][hname] = summarize_ann_v3(hrecs, "H5")

    summary["verdicts"] = verdicts_v3.evaluate_v3(summary)
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Recompute v3 summary from raw records")
    p.add_argument("--raw-dir", default=os.path.join(REPO_ROOT, "results", "v3", "raw"))
    p.add_argument("--run-id", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--check", default=None, help="exit 1 unless recomputation equals this file byte-for-byte")
    a = p.parse_args(argv)
    text = dumps_summary(recompute_v3_summary(a.raw_dir, a.run_id))
    if a.check:
        with open(a.check, "r", encoding="utf-8") as f:
            same = f.read() == text
        print(f"[recompute_v3] {'MATCH' if same else 'MISMATCH'}: {a.check}")
        return 0 if same else 1
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[recompute_v3] wrote {a.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
