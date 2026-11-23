#!/usr/bin/env python3
"""
Deterministic Raw-Log -> Summary Recomputation & Pre-Registration Check for v3.2
================================================================================
Reads `results/v3_2_audit/raw/v3_2_reviewer_audit.jsonl`, verifies FREEZE_v3.1
SHA-256 hashes, recomputes all R6-R8 metrics from per-record raw JSONL rows,
and evaluates pre-registered predictions PR6, PR7, PR8 from PROTOCOL_v3_2.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from bench.recompute import dumps_summary  # noqa: E402
from bench.recompute_v3_1 import freeze_v3_1_status  # noqa: E402

SCHEMA_V3_2 = "prism-ann-v3.2-reviewer-audit/1"
DEFAULT_RAW_PATH = os.path.join(REPO_ROOT, "results", "v3_2_audit", "raw", "v3_2_reviewer_audit.jsonl")


def load_v3_2_records(raw_path: str = DEFAULT_RAW_PATH) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []
    with open(raw_path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                recs.append(json.loads(s))
    return recs


def _eval_verdicts_v3_2(summary: Dict[str, Any]) -> Dict[str, Any]:
    r6 = summary["R6_multiparent_dag_fuzzing"]
    r7 = summary["R7_two_track_fair_benchmark"]
    r8 = summary["R8_exact_vs_empirical_recall_audit"]

    pr6_ok = (
        r6["total_dag_trials"] >= 5000
        and r6["total_mismatches"] == 0
        and r6["min_secondary_parents_per_dag"] >= 1
    )

    pr7_ok = r7["total_leaks"] == 0 and r7["total_queries"] >= 1500
    low_s_keys = ("0.0001", "0.001", "0.005", "0.01")
    for sk in low_s_keys:
        blk = r7["by_selectivity"][sk]["systems"]
        g_rec = blk["v3-geom-M8"]["recall_pct"]
        f_rec = blk["faiss-hnsw-M16"]["recall_pct"]
        a_rec = blk["acorn-1"]["recall_pct"]
        r_rec = blk["racorn-1-fallback"]["recall_pct"]
        f32 = blk["v3-full-guard-f32"]
        sq8 = blk["v3-full-guard-sq8"]
        ok_s = (
            g_rec > f_rec
            and g_rec > a_rec
            and g_rec > r_rec
            and f32["recall_pct"] == 100.0
            and sq8["recall_pct"] == 100.0
            and f32["track1_cpp_med_ms"] <= 0.35
            and sq8["track1_cpp_med_ms"] <= 0.35
            and sq8["speedup_e2e_pg_vs_faiss"] >= 20.0
            and f32["speedup_e2e_pg_vs_faiss"] >= 20.0
            and sq8["speedup_e2e_mirror_vs_faiss"] >= 100.0
            and f32["speedup_e2e_mirror_vs_faiss"] >= 100.0
        )
        pr7_ok = pr7_ok and ok_s

    s001 = r8["by_selectivity"]["0.0001"]
    pr8_ok = s001["exact_guarantee_coverage_m64_pct"] == 100.0 and s001["sq8_m64_recall_pct"] == 100.0
    for sk in ("0.0001", "0.001", "0.005", "0.01"):
        row = r8["by_selectivity"][sk]
        ok8 = (
            row["sq8_m64_recall_pct"] >= 99.8
            and row["exact_f32_recall_pct"] == 100.0
            and row["exact_f32_med_ms"] <= 0.25
        )
        pr8_ok = pr8_ok and ok8

    return {
        "PR6": {
            "verdict": "supported" if pr6_ok else "falsified",
            "total_dag_trials": r6["total_dag_trials"],
            "total_mismatches": r6["total_mismatches"],
        },
        "PR7": {
            "verdict": "supported" if pr7_ok else "falsified",
            "total_queries": r7["total_queries"],
            "total_leaks": r7["total_leaks"],
        },
        "PR8": {
            "verdict": "supported" if pr8_ok else "falsified",
            "s0001_m64_guarantee_pct": s001["exact_guarantee_coverage_m64_pct"],
            "s001_f32_med_ms": r8["by_selectivity"]["0.01"]["exact_f32_med_ms"],
        },
    }


def recompute_v3_2_summary(raw_path: str = DEFAULT_RAW_PATH) -> Dict[str, Any]:
    recs = load_v3_2_records(raw_path)
    by_exp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in recs:
        by_exp[str(r["experiment"])].append(r)

    meta = by_exp.get("R0_meta", [{}])[-1]

    # ---- R6: Multi-parent DAG fuzzing ----
    r6_recs = by_exp["R6_multiparent_dag"]
    topos: Dict[str, Dict[str, int]] = defaultdict(lambda: {"trials": 0, "mismatches": 0})
    for r in r6_recs:
        tkey = f"b={r['b']},L={r['L']}"
        topos[tkey]["trials"] += 1
        topos[tkey]["mismatches"] += int(r["mismatch"])

    r6_summary = {
        "total_dag_trials": len(r6_recs),
        "total_mismatches": int(sum(int(r["mismatch"]) for r in r6_recs)),
        "false_positives": int(sum(int(r["false_positives"]) for r in r6_recs)),
        "false_negatives": int(sum(int(r["false_negatives"]) for r in r6_recs)),
        "min_secondary_parents_per_dag": int(min(int(r["n_secondary_edges"]) for r in r6_recs)) if r6_recs else 0,
        "mean_secondary_edges_per_dag": round(float(np.mean([int(r["n_secondary_edges"]) for r in r6_recs])), 1) if r6_recs else 0.0,
        "median_ubp_tokens_pos": float(np.median([int(r["tokens_pos"]) for r in r6_recs])) if r6_recs else 0.0,
        "max_ubp_tokens_pos": int(max(int(r["tokens_pos"]) for r in r6_recs)) if r6_recs else 0,
        "by_topology": dict(sorted(topos.items())),
    }

    # ---- R7: Two-Track Fair Benchmark ----
    r7_recs = by_exp["R7_two_track"]
    by_s: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in r7_recs:
        by_s[str(r["S_target"])].append(r)

    r7_by_s: Dict[str, Any] = {}
    for sk in sorted(by_s.keys(), key=lambda x: float(x)):
        s_rows = by_s[sk]
        by_sys: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in s_rows:
            by_sys[str(r["system"])].append(r)

        sys_out: Dict[str, Any] = {}
        for sname, rows in sorted(by_sys.items()):
            recalls = [100.0 * float(r["recall"]) for r in rows]
            t1 = [float(r["track1_cpp_ms"]) for r in rows]
            fc = [float(r["filter_compile_ms"]) for r in rows]
            e2e_pg = [float(r["track2_e2e_pg_ms"]) for r in rows]
            e2e_mir = [float(r["track2_e2e_mirror_ms"]) for r in rows]
            dists = [float(r["dist"]) for r in rows if r.get("dist") is not None]
            sys_out[sname] = {
                "n_queries": len(rows),
                "leaks_total": int(sum(int(r["leaks"]) for r in rows)),
                "recall_pct": round(float(np.mean(recalls)), 2),
                "track1_cpp_med_ms": round(float(np.median(t1)), 4),
                "track1_cpp_p95_ms": round(float(np.percentile(t1, 95)), 4),
                "filter_compile_med_ms": round(float(np.median(fc)), 4),
                "track2_e2e_pg_med_ms": round(float(np.median(e2e_pg)), 2),
                "track2_e2e_mirror_med_ms": round(float(np.median(e2e_mir)), 4),
                "dist_mean": round(float(np.mean(dists)), 1) if dists else None,
            }

        faiss_pg = sys_out["faiss-hnsw-M16"]["track2_e2e_pg_med_ms"]
        faiss_mir = sys_out["faiss-hnsw-M16"]["track2_e2e_mirror_med_ms"]
        for sname, blk in sys_out.items():
            blk["speedup_e2e_pg_vs_faiss"] = round(faiss_pg / max(1e-6, blk["track2_e2e_pg_med_ms"]), 2)
            blk["speedup_e2e_mirror_vs_faiss"] = round(faiss_mir / max(1e-6, blk["track2_e2e_mirror_med_ms"]), 2)

        r7_by_s[sk] = {
            "S_actual_pct": round(100.0 * float(np.mean([float(r["S_actual"]) for r in by_sys["v3-full-guard-sq8"]])), 5),
            "systems": sys_out,
        }

    r7_summary = {
        "N": 522931,
        "total_queries": len(r7_recs),
        "total_leaks": int(sum(int(r["leaks"]) for r in r7_recs)),
        "h1_auth_constants_from_v3_summary_ms": {
            "pg_lookup_plus_roaring": float(meta.get("h1_pg_lookup_med_ms", 0.0)),
            "mem_lookup_plus_roaring": float(meta.get("h1_mem_lookup_med_ms", 0.0)),
            "pg_readrels_plus_ubp_roaring": float(meta.get("h1_pg_ubp_rpc_med_ms", 0.0)),
            "mirror_ubp_plus_roaring": float(meta.get("h1_mirror_ubp_med_ms", 0.0)),
        },
        "by_selectivity": r7_by_s,
    }

    # ---- R8: Exact vs. Empirical Recall Audit ----
    r8_recs = by_exp["R8_recall_audit"]
    r8_by_s_rows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in r8_recs:
        r8_by_s_rows[str(r["S_target"])].append(r)

    r8_by_s: Dict[str, Any] = {}
    for sk in sorted(r8_by_s_rows.keys(), key=lambda x: float(x)):
        rows = r8_by_s_rows[sk]
        n_cands = [int(r["n_cand"]) for r in rows]
        r8_by_s[sk] = {
            "n_queries": len(rows),
            "n_cand_mean": round(float(np.mean(n_cands)), 1),
            "n_cand_max": int(max(n_cands)),
            "exact_guarantee_coverage_m10_pct": round(100.0 * float(np.mean([bool(int(r["n_cand"]) <= 10) for r in rows])), 2),
            "exact_guarantee_coverage_m32_pct": round(100.0 * float(np.mean([bool(int(r["n_cand"]) <= 32) for r in rows])), 2),
            "exact_guarantee_coverage_m64_pct": round(100.0 * float(np.mean([bool(int(r["n_cand"]) <= 64) for r in rows])), 2),
            "exact_guarantee_coverage_m128_pct": round(100.0 * float(np.mean([bool(int(r["n_cand"]) <= 128) for r in rows])), 2),
            "sq8_m10_recall_pct": round(100.0 * float(np.mean([float(r["rec_sq8_m10"]) for r in rows])), 3),
            "sq8_m32_recall_pct": round(100.0 * float(np.mean([float(r["rec_sq8_m32"]) for r in rows])), 3),
            "sq8_m64_recall_pct": round(100.0 * float(np.mean([float(r["rec_sq8_m64"]) for r in rows])), 3),
            "sq8_m128_recall_pct": round(100.0 * float(np.mean([float(r["rec_sq8_m128"]) for r in rows])), 3),
            "exact_f32_recall_pct": round(100.0 * float(np.mean([float(r["rec_exact_f32"]) for r in rows])), 3),
            "sq8_m64_med_ms": round(float(np.median([float(r["ms_sq8_m64"]) for r in rows])), 4),
            "exact_f32_med_ms": round(float(np.median([float(r["ms_exact_f32"]) for r in rows])), 4),
        }

    r8_summary = {
        "N": 522931,
        "total_queries": len(r8_recs),
        "by_selectivity": r8_by_s,
    }

    fz = freeze_v3_1_status()
    summary: Dict[str, Any] = {
        "schema": SCHEMA_V3_2,
        "git_sha_start": meta.get("git_sha", ""),
        "git_dirty": bool(meta.get("git_dirty", False)),
        "freeze_v3_1_match": fz["match"],
        "freeze_v3_1_files": fz["n_files"],
        "raw_jsonl_path": os.path.relpath(raw_path, REPO_ROOT),
        "raw_records_total": len(recs),
        "raw_records_by_experiment": {k: len(v) for k, v in sorted(by_exp.items())},
        "R6_multiparent_dag_fuzzing": r6_summary,
        "R7_two_track_fair_benchmark": r7_summary,
        "R8_exact_vs_empirical_recall_audit": r8_summary,
    }
    summary["verdicts"] = _eval_verdicts_v3_2(summary)
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Deterministically recompute v3.2 reviewer audit summary")
    p.add_argument("--raw", default=DEFAULT_RAW_PATH)
    p.add_argument("--out", default=None)
    p.add_argument("--check", default=None)
    a = p.parse_args(argv)

    text = dumps_summary(recompute_v3_2_summary(a.raw))
    if a.check:
        with open(a.check, "r", encoding="utf-8") as f:
            same = f.read() == text
        print(f"[recompute_v3_2] {'MATCH' if same else 'MISMATCH'}: {a.check}")
        return 0 if same else 1
    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[recompute_v3_2] wrote {a.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
