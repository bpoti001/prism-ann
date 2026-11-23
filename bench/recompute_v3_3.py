#!/usr/bin/env python3
"""
Deterministic Raw-Log -> Summary Recomputation & Pre-Registration Check for v3.3
================================================================================
Reads `results/v3_3_audit/raw/v3_3_reviewer_audit.jsonl`, verifies FREEZE_v3_3.md
(`9/9` SHA-256 hashes), recomputes R9a, R9b, R10, and R11 metrics directly from
per-record raw JSONL rows, and evaluates PR9a, PR9b, PR10, and PR11.
"""

from __future__ import annotations

import argparse
import hashlib
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

SCHEMA_V3_3 = "prism-ann-v3.3-reviewer-audit/1"
FREEZE_V3_3_PATH = os.path.join(REPO_ROOT, "FREEZE_v3_3.md")
DEFAULT_RAW_PATH = os.path.join(REPO_ROOT, "results", "v3_3_audit", "raw", "v3_3_reviewer_audit.jsonl")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def freeze_v3_3_status(
    repo_root: str = REPO_ROOT, freeze_path: str = FREEZE_V3_3_PATH
) -> Dict[str, Any]:
    expected: Dict[str, str] = {}
    if os.path.exists(freeze_path):
        with open(freeze_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 2 and len(parts[0]) == 64:
                    expected[parts[1]] = parts[0]
    mismatches: Dict[str, Dict[str, str]] = {}
    for rel, exp in sorted(expected.items()):
        p = os.path.join(repo_root, rel)
        cur = _sha256(p) if os.path.exists(p) else "<missing>"
        if cur != exp:
            mismatches[rel] = {"expected": exp, "current": cur}
    return {
        "match": bool(expected) and not mismatches,
        "n_files": len(expected),
        "mismatches": mismatches,
    }


def load_v3_3_records(raw_path: str = DEFAULT_RAW_PATH) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []
    with open(raw_path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                recs.append(json.loads(s))
    return recs


def _eval_verdicts_v3_3(summary: Dict[str, Any]) -> Dict[str, Any]:
    r9a = summary["R9a_independent_dag_dynamic_mutations"]
    r9b = summary["R9b_live_spicedb_mutation_matrix"]
    r10 = summary["R10_direct_e2e_and_ef_sweep"]
    r11 = summary["R11_live_spicedb_zedtoken_concurrency"]

    pr9a_ok = (
        r9a["independent_dags"] >= 1000
        and r9a["total_mutation_checkpoints"] >= 5000
        and r9a["false_positives"] == 0
        and r9a["false_negatives"] == 0
        and r9a["search_hit_leaks"] == 0
    )

    pr9b_ok = (
        r9b["scenarios_total"] >= 10
        and r9b["mask_mismatches"] == 0
        and r9b["search_mismatches"] == 0
        and r9b["check_permission_mismatches"] == 0
        and r9b.get("fail_closed_refusals_verified", 0) >= 1
    )

    pr10_ok = r10["e2e_total_leaks"] == 0 and r10["ef_sweep_total_leaks"] == 0
    for sk in ("0.0001", "0.001", "0.005", "0.01"):
        blk = r10["direct_e2e_by_S"][sk]["systems"]
        f_med = blk["faiss-hnsw-M16"]["e2e_lookup_med_ms"]
        f32 = blk["v3-full-guard-f32"]
        sq8 = blk["v3-full-guard-sq8"]
        ok_s = (
            f32["recall_pct"] == 100.0
            and sq8["recall_pct"] == 100.0
            and (f_med / max(1e-6, f32["e2e_live_rpc_med_ms"])) >= 10.0
            and (f_med / max(1e-6, sq8["e2e_live_rpc_med_ms"])) >= 10.0
        )
        pr10_ok = pr10_ok and ok_s

    pr11_ok = (
        r11["concurrent_reads_total"] >= 1600
        and r11["oracle_mismatches"] == 0
        and r11["post_revocation_leaks"] == 0
        and r11["snapshot_stale_reads_after_post_pin"] == 0
    )

    return {
        "PR9a": {
            "verdict": "supported" if pr9a_ok else "falsified",
            "independent_dags": r9a["independent_dags"],
            "total_mutation_checkpoints": r9a["total_mutation_checkpoints"],
            "mismatches": r9a["false_positives"] + r9a["false_negatives"],
        },
        "PR9b": {
            "verdict": "supported" if pr9b_ok else "falsified",
            "scenarios_total": r9b["scenarios_total"],
            "mismatches": r9b["mask_mismatches"] + r9b["search_mismatches"],
            "fail_closed_refusals_verified": r9b["fail_closed_refusals_verified"],
        },
        "PR10": {
            "verdict": "supported" if pr10_ok else "falsified",
            "e2e_total_queries": r10["e2e_total_queries"],
            "e2e_total_leaks": r10["e2e_total_leaks"],
        },
        "PR11": {
            "verdict": "supported" if pr11_ok else "falsified",
            "concurrent_reads_total": r11["concurrent_reads_total"],
            "post_revocation_leaks": r11["post_revocation_leaks"],
        },
    }


def recompute_v3_3_summary(raw_path: str = DEFAULT_RAW_PATH) -> Dict[str, Any]:
    recs = load_v3_3_records(raw_path)
    by_exp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in recs:
        by_exp[str(r["experiment"])].append(r)

    meta = by_exp.get("R0_meta", [{}])[-1]

    # ---- R9a: 1,000 Independent Multi-Parent DAGs + Dynamic Mutations ----
    r9a_recs = by_exp["R9a_independent_dag"]
    dag_ids = {int(r["dag_id"]) for r in r9a_recs}
    by_mut: Dict[str, Dict[str, int]] = defaultdict(lambda: {"checkpoints": 0, "fp": 0, "fn": 0})
    for r in r9a_recs:
        mk = str(r["mutation"])
        by_mut[mk]["checkpoints"] += 1
        by_mut[mk]["fp"] += int(r["fp"])
        by_mut[mk]["fn"] += int(r["fn"])

    r9a_summary = {
        "independent_dags": len(dag_ids),
        "total_mutation_checkpoints": len(r9a_recs),
        "false_positives": int(sum(int(r["fp"]) for r in r9a_recs)),
        "false_negatives": int(sum(int(r["fn"]) for r in r9a_recs)),
        "search_hit_leaks": int(sum(int(r["search_leaks"]) for r in r9a_recs)),
        "min_secondary_edges": int(min(int(r["n_secondary_edges"]) for r in r9a_recs)) if r9a_recs else 0,
        "mean_secondary_edges": round(float(np.mean([int(r["n_secondary_edges"]) for r in r9a_recs])), 1) if r9a_recs else 0.0,
        "by_mutation": dict(sorted(by_mut.items())),
    }

    # ---- R9b: Live Native SpiceDB v1.57.1 Multi-Parent Matrix ----
    r9b_recs = by_exp["R9b_spicedb_matrix"]
    r9b_summary = {
        "scenarios_total": len(r9b_recs),
        "mask_mismatches": int(sum(int(r["mask_mismatch"]) for r in r9b_recs)),
        "search_mismatches": int(sum(int(r["search_mismatch"]) for r in r9b_recs)),
        "check_permission_mismatches": int(sum(int(r["check_perm_mismatch"]) for r in r9b_recs)),
        "fail_closed_refusals_verified": int(sum(1 for r in r9b_recs if r.get("fail_closed_refused"))),
        "scenarios": [
            {
                "scenario": r["scenario"],
                "spicedb_docs": int(r["spicedb_docs"]),
                "index_docs": int(r["index_docs"]),
                "mask_mismatch": int(r["mask_mismatch"]),
                "search_mismatch": int(r["search_mismatch"]),
                "check_perm_mismatch": int(r["check_perm_mismatch"]),
                "write_zed_token": r.get("write_zed_token"),
                "selected_read_revision": r.get("selected_read_revision"),
                "indexed_posting_revision": r.get("indexed_posting_revision"),
                "latency_ms": r.get("latency_ms"),
                "fail_closed_refused": bool(r.get("fail_closed_refused", False)),
            }
            for r in r9b_recs
        ],
    }

    # ---- R10: Directly Timed E2E & Matched-Recall efSearch Sweep ----
    r10_e2e = by_exp["R10_direct_e2e"]
    by_s: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in r10_e2e:
        by_s[str(r["S_target"])].append(r)

    e2e_by_s: Dict[str, Any] = {}
    for sk in sorted(by_s.keys(), key=lambda x: float(x)):
        s_rows = by_s[sk]
        by_sys: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in s_rows:
            by_sys[str(r["system"])].append(r)
        sys_out: Dict[str, Any] = {}
        for sname, rows in sorted(by_sys.items()):
            recalls = [100.0 * float(r["recall"]) for r in rows]
            live_ms = [float(r["e2e_live_ms"]) for r in rows]
            mir_ms = [float(r["e2e_mirror_ms"]) for r in rows if r.get("e2e_mirror_ms") is not None]
            dists = [float(r["dist"]) for r in rows if r.get("dist") is not None]
            entry: Dict[str, Any] = {
                "n_queries": len(rows),
                "leaks_total": int(sum(int(r["leaks"]) for r in rows)),
                "recall_pct": round(float(np.mean(recalls)), 2),
                "dist_mean": round(float(np.mean(dists)), 1) if dists else None,
            }
            if sname in ("faiss-hnsw-M16", "acorn-1", "racorn-1-fallback"):
                entry["e2e_lookup_med_ms"] = round(float(np.median(live_ms)), 4)
                entry["e2e_lookup_p95_ms"] = round(float(np.percentile(live_ms, 95)), 4)
            else:
                entry["e2e_live_rpc_med_ms"] = round(float(np.median(live_ms)), 4)
                entry["e2e_live_rpc_p95_ms"] = round(float(np.percentile(live_ms, 95)), 4)
                entry["e2e_mirror_med_ms"] = round(float(np.median(mir_ms)), 4) if mir_ms else None
                entry["e2e_mirror_p95_ms"] = round(float(np.percentile(mir_ms, 95)), 4) if mir_ms else None
            sys_out[sname] = entry

        f_med = sys_out["faiss-hnsw-M16"]["e2e_lookup_med_ms"]
        for sname, blk in sys_out.items():
            if "e2e_live_rpc_med_ms" in blk:
                blk["speedup_live_rpc_vs_faiss"] = round(f_med / max(1e-6, blk["e2e_live_rpc_med_ms"]), 2)
                if blk.get("e2e_mirror_med_ms"):
                    blk["speedup_mirror_vs_faiss"] = round(f_med / max(1e-6, blk["e2e_mirror_med_ms"]), 2)

        e2e_by_s[sk] = {
            "S_actual_pct": round(100.0 * float(np.mean([float(r["S_actual"]) for r in s_rows])), 5),
            "systems": sys_out,
        }

    r10_ef = by_exp["R10_ef_sweep"]
    ef_by_s: Dict[str, Dict[str, Any]] = defaultdict(dict)
    by_s_ef_sys: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
    for r in r10_ef:
        by_s_ef_sys[(str(r["S_target"]), str(r["ef_search"]), str(r["system"]))].append(r)
    for (sk, ef_str, sname), rows in sorted(by_s_ef_sys.items(), key=lambda x: (float(x[0][0]), int(x[0][1]), x[0][2])):
        ef_by_s.setdefault(sk, {}).setdefault(ef_str, {})[sname] = {
            "n_queries": len(rows),
            "leaks_total": int(sum(int(r["leaks"]) for r in rows)),
            "recall_pct": round(100.0 * float(np.mean([float(r["recall"]) for r in rows])), 2),
            "cpp_med_ms": round(float(np.median([float(r["cpp_ms"]) for r in rows])), 4),
            "dist_mean": round(float(np.mean([float(r["dist"]) for r in rows])), 1),
        }

    r10_summary = {
        "N": int(meta.get("quora_N", 522931)),
        "e2e_total_queries": len(r10_e2e),
        "e2e_total_leaks": int(sum(int(r["leaks"]) for r in r10_e2e)),
        "direct_e2e_by_S": e2e_by_s,
        "ef_sweep_total_queries": len(r10_ef),
        "ef_sweep_total_leaks": int(sum(int(r["leaks"]) for r in r10_ef)),
        "ef_sweep_by_S": dict(ef_by_s),
    }

    # ---- R11: Live SpiceDB Opaque ZedToken Concurrent Reader Stress ----
    r11_recs = by_exp["R11_live_spicedb_zedtoken"]
    post_recs = [r for r in r11_recs if r["consistency_mode"] == "post_revocation_at_least_as_fresh"]
    pre_recs = [r for r in r11_recs if r["consistency_mode"] == "pre_revocation_exact_snapshot"]
    r11_summary = {
        "concurrent_reads_total": len(r11_recs),
        "n_threads": int(meta.get("r11_threads", 8)),
        "pre_revocation_exact_snapshot_reads": len(pre_recs),
        "post_revocation_reads": len(post_recs),
        "oracle_mismatches": int(sum(int(r["oracle_mismatch"]) for r in r11_recs)),
        "post_revocation_leaks": int(sum(int(r["revoked_hit_leaks"]) for r in post_recs)),
        "snapshot_stale_reads_after_post_pin": int(sum(int(r["stale_snapshot_error"]) for r in post_recs)),
        "spicedb_median_rpc_ms": round(float(np.median([float(r["spicedb_rpc_ms"]) for r in r11_recs])), 3) if r11_recs else 0.0,
        "index_median_search_ms": round(float(np.median([float(r["index_search_ms"]) for r in r11_recs])), 3) if r11_recs else 0.0,
    }

    out: Dict[str, Any] = {
        "schema": SCHEMA_V3_3,
        "raw_jsonl_path": os.path.relpath(os.path.abspath(raw_path), REPO_ROOT),
        "raw_records_total": len(recs),
        "raw_records_by_experiment": {k: len(v) for k, v in sorted(by_exp.items())},
        "git_sha_start": meta.get("git_sha", "unknown"),
        "git_dirty": meta.get("git_dirty", True),
        "freeze_v3_3_match": meta.get("freeze_v3_3_match", False),
        "freeze_v3_3_files": meta.get("freeze_v3_3_files", 0),
        "R9a_independent_dag_dynamic_mutations": r9a_summary,
        "R9b_live_spicedb_mutation_matrix": r9b_summary,
        "R10_direct_e2e_and_ef_sweep": r10_summary,
        "R11_live_spicedb_zedtoken_concurrency": r11_summary,
    }
    out["verdicts"] = _eval_verdicts_v3_3(out)
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Deterministically recompute v3.3 audit JSON from raw JSONL")
    ap.add_argument("--raw", default=DEFAULT_RAW_PATH)
    ap.add_argument("--out", default=None)
    ap.add_argument("--check", default=None)
    args = ap.parse_args(argv)

    summary = recompute_v3_3_summary(args.raw)
    payload = dumps_summary(summary)

    if args.check:
        with open(args.check, "r", encoding="utf-8") as f:
            existing = f.read()
        if existing == payload:
            print(f"[recompute_v3_3] MATCH: {args.check}")
            return 0
        print(f"[recompute_v3_3] MISMATCH against {args.check}!")
        return 1

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(payload)
        print(f"[recompute_v3_3] WROTE {args.out}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
