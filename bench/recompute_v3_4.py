#!/usr/bin/env python3
"""
Deterministic Raw-Log -> Summary Recomputation & Pre-Registration Check for v3.4 (R12)
======================================================================================
Reads `results/v3_4_audit/raw/v3_4_reviewer_audit.jsonl`, verifies FREEZE_v3_4.md
(`10/10` SHA-256 hashes), recomputes R12a, R12b, and R12c metrics directly from
per-record raw JSONL rows, and evaluates pre-registered predictions PR12a, PR12b, PR12c.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from bench.recompute import dumps_summary  # noqa: E402

SCHEMA_V3_4 = "prism-ann-v3.4-reviewer-audit/1"
FREEZE_V3_4_PATH = os.path.join(REPO_ROOT, "FREEZE_v3_4.md")
DEFAULT_RAW_PATH = os.path.join(REPO_ROOT, "results", "v3_4_audit", "raw", "v3_4_reviewer_audit.jsonl")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def freeze_v3_4_status(
    repo_root: str = REPO_ROOT, freeze_path: str = FREEZE_V3_4_PATH
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


def load_v3_4_records(raw_path: str = DEFAULT_RAW_PATH) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []
    with open(raw_path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                recs.append(json.loads(s))
    return recs


def _eval_verdicts_v3_4(summary: Dict[str, Any]) -> Dict[str, Any]:
    r12a = summary["R12a_snapshot_race_injection"]
    r12b = summary["R12b_live_spicedb_unsynced_mirror"]
    r12c = summary["R12c_multithreaded_atomic_search_stress"]

    pr12a_ok = (
        r12a["v3_4_trials_total"] >= 200
        and r12a["v3_4_torn_snapshots"] == 0
        and r12a["v3_4_bitmap_mismatches"] == 0
        and r12a["v3_4_ordering_regressions"] == 0
        and r12a["v3_4_search_leaks"] == 0
        and r12a["v3_3_control_torn_snapshots"] >= 1
    )

    pr12b_ok = (
        r12b["scenarios_total"] >= 10
        and r12b["mask_mismatches"] == 0
        and r12b["search_mismatches"] == 0
        and r12b["check_permission_mismatches"] == 0
        and r12b["fail_closed_refusals_verified"] >= 5
        and r12b["spicedb_fallbacks_verified"] >= 4
    )

    pr12c_ok = (
        r12c["concurrent_reads_total"] >= 1000
        and r12c["published_snapshots_verified"] >= 1
        and r12c["torn_snapshots"] == 0
        and r12c["ordering_regressions"] == 0
        and r12c["oracle_mismatches"] == 0
        and r12c["search_leaks"] == 0
    )

    return {
        "PR12a": {
            "verdict": "supported" if pr12a_ok else "falsified",
            "rule": ">=200 injected-race & multi-publisher trials on v3.4: 0 torn snapshots, 0 bitmap mismatches, 0 ordering regressions, 0 search leaks (and >=1 torn snapshot reproduced on frozen v3.3 control)",
            "v3_4_trials_total": r12a["v3_4_trials_total"],
            "v3_4_torn_snapshots": r12a["v3_4_torn_snapshots"],
            "v3_4_ordering_regressions": r12a["v3_4_ordering_regressions"],
            "v3_4_search_leaks": r12a["v3_4_search_leaks"],
            "v3_3_control_torn_snapshots": r12a["v3_3_control_torn_snapshots"],
        },
        "PR12b": {
            "verdict": "supported" if pr12b_ok else "falsified",
            "rule": ">=10 live SpiceDB v1.57.1 unsynced-mirror & opaque-ZedToken scenarios: 0 mask/search/CheckPermission mismatches, >=5 verified fail-closed refusals, >=4 verified live SpiceDB fallbacks",
            "scenarios_total": r12b["scenarios_total"],
            "mask_mismatches": r12b["mask_mismatches"],
            "search_mismatches": r12b["search_mismatches"],
            "check_permission_mismatches": r12b["check_permission_mismatches"],
            "fail_closed_refusals_verified": r12b["fail_closed_refusals_verified"],
            "spicedb_fallbacks_verified": r12b["spicedb_fallbacks_verified"],
        },
        "PR12c": {
            "verdict": "supported" if pr12c_ok else "falsified",
            "rule": ">=1,000 multi-threaded concurrent public search() queries interleaved with DAG mutations & atomic publications: 0 torn snapshots, 0 ordering regressions, 0 oracle mismatches, 0 leaks",
            "concurrent_reads_total": r12c["concurrent_reads_total"],
            "published_snapshots_verified": r12c["published_snapshots_verified"],
            "torn_snapshots": r12c["torn_snapshots"],
            "oracle_mismatches": r12c["oracle_mismatches"],
            "search_leaks": r12c["search_leaks"],
        },
    }


def recompute_v3_4_summary(raw_path: str = DEFAULT_RAW_PATH) -> Dict[str, Any]:
    recs = load_v3_4_records(raw_path)
    by_exp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    meta_rec: Dict[str, Any] = {}
    for r in recs:
        if r.get("experiment") == "META":
            meta_rec = r
        else:
            by_exp[str(r.get("experiment"))].append(r)

    # --- R12a: Race Injection (Frozen v3.3 Control vs. v3.4 Atomic Fix) ---
    r12a_recs = by_exp["R12a"]
    v33_ctrl = [r for r in r12a_recs if r.get("variant") == "v3_3_control"]
    v34_fix = [r for r in r12a_recs if r.get("variant") == "v3_4_atomic"]
    r12a_summary = {
        "v3_3_control_trials": len(v33_ctrl),
        "v3_3_control_torn_snapshots": sum(int(not bool(r["snapshot_consistent"])) for r in v33_ctrl),
        "v3_3_control_zt_disagreements": sum(int(not bool(r["zt_match"])) for r in v33_ctrl),
        "v3_3_control_hv_disagreements": sum(int(not bool(r["hv_match"])) for r in v33_ctrl),
        "v3_3_control_bitmap_mismatches": sum(int(r["bitmap_mismatches"]) for r in v33_ctrl),
        "v3_4_trials_total": len(v34_fix),
        "v3_4_double_injection_trials": sum(1 for r in v34_fix if r.get("subtest") == "double_injection"),
        "v3_4_multipublisher_ordering_trials": sum(1 for r in v34_fix if r.get("subtest") == "multipublisher_ordering"),
        "v3_4_torn_snapshots": sum(int(not bool(r["snapshot_consistent"])) for r in v34_fix),
        "v3_4_zt_disagreements": sum(int(not bool(r["zt_match"])) for r in v34_fix),
        "v3_4_hv_disagreements": sum(int(not bool(r["hv_match"])) for r in v34_fix),
        "v3_4_bitmap_mismatches": sum(int(r["bitmap_mismatches"]) for r in v34_fix),
        "v3_4_ordering_regressions": sum(int(r.get("ordering_regression", 0)) for r in v34_fix),
        "v3_4_search_leaks": sum(int(r.get("search_leaks", 0)) for r in v34_fix),
        "v3_4_search_false_negatives": sum(int(r.get("search_fn", 0)) for r in v34_fix),
    }

    # --- R12b: Live Native SpiceDB v1.57.1 Unsynced Mirror & Opaque ZedToken ---
    r12b_recs = by_exp["R12b"]
    r12b_scenarios = []
    for r in r12b_recs:
        r12b_scenarios.append(
            {
                "scenario": r["scenario"],
                "spicedb_docs": r.get("spicedb_docs"),
                "index_docs": r.get("index_docs"),
                "mask_mismatch": int(r["mask_mismatch"]),
                "search_mismatch": int(r["search_mismatch"]),
                "check_perm_mismatch": int(r["check_perm_mismatch"]),
                "consistency_mode": r["consistency_mode"],
                "on_unavailable": r["on_unavailable"],
                "requested_external_zed_token": r.get("requested_external_zed_token"),
                "evaluated_external_zed_token": r.get("evaluated_external_zed_token", r.get("selected_external_zed_token")),
                "evaluated_external_revision_status": r.get("evaluated_external_revision_status", "unknown"),
                "selected_external_zed_token": r.get("selected_external_zed_token"),
                "selected_local_revision": r.get("selected_local_revision"),
                "fallback_used": r.get("fallback_used"),
                "fail_closed_refusal_verified": bool(r.get("fail_closed_refusal_verified", False)),
                "latency_ms": float(r["latency_ms"]),
            }
        )
    r12b_summary = {
        "scenarios_total": len(r12b_recs),
        "mask_mismatches": sum(int(r["mask_mismatch"]) for r in r12b_recs),
        "search_mismatches": sum(int(r["search_mismatch"]) for r in r12b_recs),
        "check_permission_mismatches": sum(int(r["check_perm_mismatch"]) for r in r12b_recs),
        "fail_closed_refusals_verified": sum(int(bool(r.get("fail_closed_refusal_verified", False))) for r in r12b_recs),
        "spicedb_fallbacks_verified": sum(int(r.get("fallback_used") == "spicedb_leaf_fallback") for r in r12b_recs),
        "scenarios": r12b_scenarios,
    }

    # --- R12c: Multi-Threaded Concurrent Mutation + Publication + Public search() ---
    r12c_recs = by_exp["R12c"]
    r12c_reads = [r for r in r12c_recs if r.get("record_kind") == "read"]
    r12c_snaps = [r for r in r12c_recs if r.get("record_kind") == "snapshot_audit"]
    read_lats = [float(r["latency_ms"]) for r in r12c_reads]
    r12c_summary = {
        "concurrent_reads_total": len(r12c_reads),
        "at_exact_snapshot_reads": sum(1 for r in r12c_reads if r.get("consistency_mode") == "at_exact_snapshot"),
        "at_least_as_fresh_reads": sum(1 for r in r12c_reads if r.get("consistency_mode") == "at_least_as_fresh"),
        "published_snapshots_verified": len(r12c_snaps),
        "torn_snapshots": sum(int(not bool(r["snapshot_consistent"])) for r in r12c_snaps),
        "ordering_regressions": sum(int(r.get("ordering_regression", 0)) for r in r12c_snaps),
        "oracle_mismatches": sum(int(r["oracle_mismatch"]) for r in r12c_reads),
        "search_leaks": sum(int(r["search_leaks"]) for r in r12c_reads),
        "search_false_negatives": sum(int(r["search_fn"]) for r in r12c_reads),
        "median_search_ms": float(np.median(read_lats)) if read_lats else 0.0,
        "p99_search_ms": float(np.percentile(read_lats, 99)) if read_lats else 0.0,
    }

    summary: Dict[str, Any] = {
        "schema": SCHEMA_V3_4,
        "run_id": meta_rec.get("run_id", "v3.4-reviewer-audit-001"),
        "git_sha": meta_rec.get("git_sha", ""),
        "git_dirty": bool(meta_rec.get("git_dirty", False)),
        "freeze_v3_match": bool(meta_rec.get("freeze_v3_match", False)),
        "freeze_v3_1_match": bool(meta_rec.get("freeze_v3_1_match", False)),
        "freeze_v3_3_match": bool(meta_rec.get("freeze_v3_3_match", False)),
        "freeze_v3_4_match": bool(meta_rec.get("freeze_v3_4_match", False)),
        "freeze_v3_4_files": int(meta_rec.get("freeze_v3_4_files", 0)),
        "raw_records_total": len(recs),
        "R12a_snapshot_race_injection": r12a_summary,
        "R12b_live_spicedb_unsynced_mirror": r12b_summary,
        "R12c_multithreaded_atomic_search_stress": r12c_summary,
    }
    summary["verdicts"] = _eval_verdicts_v3_4(summary)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic raw->summary recomputer for Prism-ANN v3.4 (R12)")
    ap.add_argument("--raw", default=DEFAULT_RAW_PATH)
    ap.add_argument("--out", default=None)
    ap.add_argument("--check", default=None)
    args = ap.parse_args()

    f34 = freeze_v3_4_status()
    if not f34["match"]:
        print(f"[recompute_v3_4] FREEZE_v3_4 MISMATCH: {f34}", file=sys.stderr)
        return 2

    summary = recompute_v3_4_summary(args.raw)
    serialized = dumps_summary(summary)

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(serialized)
        print(f"[recompute_v3_4] Wrote {args.out}")

    if args.check:
        with open(args.check, "r", encoding="utf-8") as f:
            existing = f.read()
        if existing != serialized:
            print(f"[recompute_v3_4] MISMATCH against {args.check}!", file=sys.stderr)
            return 1
        print(f"[recompute_v3_4] MATCH: {args.check}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
