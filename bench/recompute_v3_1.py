#!/usr/bin/env python3
"""
Deterministic v3.1 Reviewer-Audit Summary Recomputation & Verdict Evaluation
===========================================================================
Reads strictly from `results/v3_1_audit/raw/v3_1_reviewer_audit.jsonl`,
deterministically recomputes R1..R5 metrics and PR1..PR5 verdicts from
`experiments/v3/PROTOCOL_v3_1.md`, and supports `--check` byte-for-bit verification.

Usage:
    python -m bench.recompute_v3_1 --raw results/v3_1_audit/raw/v3_1_reviewer_audit.jsonl --out results/v3/reviewer_audit_v3_1.json
    python -m bench.recompute_v3_1 --raw results/v3_1_audit/raw/v3_1_reviewer_audit.jsonl --check results/v3/reviewer_audit_v3_1.json
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

SCHEMA_V3_1 = "prism-ann-v3.1-reviewer-audit/2"
FREEZE_V3_1_PATH = os.path.join(REPO_ROOT, "FREEZE_v3_1.md")
DEFAULT_RAW_PATH = os.path.join(REPO_ROOT, "results", "v3_1_audit", "raw", "v3_1_reviewer_audit.jsonl")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def freeze_v3_1_status(
    repo_root: str = REPO_ROOT, freeze_path: str = FREEZE_V3_1_PATH
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


def load_audit_records(raw_path: str = DEFAULT_RAW_PATH) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []
    with open(raw_path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                recs.append(json.loads(s))
    return recs


def _eval_verdicts(summary: Dict[str, Any]) -> Dict[str, Any]:
    r1 = summary["R1_property_fuzzing"]
    r2 = summary["R2_s001_ultra_low_selectivity"]
    r3 = summary["R3_mode3_component_isolation"]
    r4 = summary["R4_revocation_scaling_and_concurrent_zedtoken"]
    r5 = summary["R5_dynamic_ingestion_and_zorder_compaction"]

    # PR1: 0/5000 std + 0/5000 alt mismatches + 100% bound satisfaction
    pr1_ok = (
        r1["standard_reBAC_trials"] >= 5000
        and r1["alternating_override_trials"] >= 5000
        and r1["total_mismatches"] == 0
        and r1["standard_bound_satisfaction_pct"] == 100.0
        and r1["alternating_bound_satisfaction_pct"] == 100.0
    )

    # PR2: On both Quora and NQ at S=0.01%, v3-geom-M8 >= 80% R@10 & >= FAISS+75 & >= ACORN-1+75;
    # v3-full-guard-sq8 == 100% R@10 at <= 0.10 ms
    pr2_ok = True
    pr2_details: Dict[str, Any] = {}
    for cname in ("quora", "nq"):
        blk = r2[cname]["systems"]
        g_rec = blk["v3-geom-M8"]["recall_pct"]
        f_rec = blk["faiss-hnsw-M16"]["recall_pct"]
        a_rec = blk["acorn-1"]["recall_pct"]
        full = blk["v3-full-guard-sq8"]
        ok_c = (
            g_rec >= 80.0
            and (g_rec - f_rec) >= 75.0
            and (g_rec - a_rec) >= 75.0
            and full["recall_pct"] == 100.0
            and full["lat_med_ms"] <= 0.10
            and r2[cname].get("leaks_total", 0) == 0
        )
        pr2_ok = pr2_ok and ok_c
        pr2_details[cname] = {
            "v3_geom_recall_pct": g_rec,
            "faiss_recall_pct": f_rec,
            "acorn1_recall_pct": a_rec,
            "v3_full_recall_pct": full["recall_pct"],
            "v3_full_med_ms": full["lat_med_ms"],
        }

    # PR3: Cold LLC at S=1.0%: Z-order >= 4x, SQ8 >= 2x, NEON >= 4x, scalar SQ8 <= 1.0 ms @ 100% R@10
    s01 = r3["S=0.01"]
    ca = s01["cold_attribution"]
    cold_sq8_scalar = s01["cold"]["5_zorder_sq8_scalar"]
    pr3_ok = (
        ca["zorder_gain_on_neon_f32"] >= 4.0
        and ca["sq8_gain_on_scalar"] >= 2.0
        and ca["neon_gain_on_sq8"] >= 4.0
        and cold_sq8_scalar["median_ms"] <= 1.0
        and cold_sq8_scalar["recall_pct"] == 100.0
    )

    # PR4: Scaling 0 writes, med <= 25ms across 128..490k; concurrent >= 10,000 queries, 0 post-zeta leaks
    sc = r4["scaling_postgres_spicedb"]
    rc = r4["concurrent_zedtoken_race"]
    pr4_ok = (
        len(sc) == 7
        and all(row["vector_writes"] == 0 and row["median_ms"] <= 25.0 for row in sc)
        and rc["total_concurrent_queries"] >= 10_000
        and rc["post_zeta_rev_leaked_chunks"] == 0
        and rc["started_after_swap_on_old_zeta"] == 0
    )

    # PR5: Delta append <= 50 us/vec, bg compact <= 5000 ms, CSR remap <= 250 ms
    batches = r5["batches"]
    pr5_ok = (
        len(batches) == 4
        and all(b["delta_append_us_per_vec"] <= 50.0 for b in batches)
        and all(b["background_zorder_compact_total_ms"] <= 5000.0 for b in batches)
        and all(b["cpp_csr_remap_only_ms"] <= 250.0 for b in batches)
    )

    return {
        "PR1": {
            "verdict": "supported" if pr1_ok else "falsified",
            "total_trials": r1["total_trials"],
            "total_mismatches": r1["total_mismatches"],
            "bound_satisfaction_pct": min(
                r1["standard_bound_satisfaction_pct"], r1["alternating_bound_satisfaction_pct"]
            ),
        },
        "PR2": {"verdict": "supported" if pr2_ok else "falsified", **pr2_details},
        "PR3": {
            "verdict": "supported" if pr3_ok else "falsified",
            "cold_S0.01_attribution": ca,
            "cold_S0.01_sq8_scalar_ms": cold_sq8_scalar["median_ms"],
        },
        "PR4": {
            "verdict": "supported" if pr4_ok else "falsified",
            "scaling_max_median_ms": max(row["median_ms"] for row in sc),
            "scaling_vector_writes_max": max(row["vector_writes"] for row in sc),
            "concurrent_queries": rc["total_concurrent_queries"],
            "post_zeta_rev_leaked_chunks": rc["post_zeta_rev_leaked_chunks"],
        },
        "PR5": {
            "verdict": "supported" if pr5_ok else "falsified",
            "append_us_per_vec_max": max(b["delta_append_us_per_vec"] for b in batches),
            "bg_compact_ms_max": max(b["background_zorder_compact_total_ms"] for b in batches),
            "csr_remap_ms_max": max(b["cpp_csr_remap_only_ms"] for b in batches),
        },
    }


def recompute_v3_1_summary(raw_path: str = DEFAULT_RAW_PATH) -> Dict[str, Any]:
    recs = load_audit_records(raw_path)
    by_exp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in recs:
        by_exp[str(r["experiment"])].append(r)

    # ---- Meta record if emitted ----
    meta_recs = by_exp.get("R0_meta", [])
    meta = meta_recs[-1] if meta_recs else {}

    # ---- R1 ----
    r1_std = by_exp["R1_standard"]
    r1_alt = by_exp["R1_alternating"]
    r1_summary = {
        "standard_reBAC_trials": len(r1_std),
        "standard_mismatches": int(sum(int(r["mismatch"]) for r in r1_std)),
        "standard_bound_satisfaction_pct": round(100.0 * sum(1 for r in r1_std if r["within_bound"]) / len(r1_std), 4),
        "standard_tokens_pos_median": float(np.median([int(r["tokens_pos"]) for r in r1_std])),
        "standard_tokens_pos_max": int(max(int(r["tokens_pos"]) for r in r1_std)),
        "alternating_override_trials": len(r1_alt),
        "alternating_mismatches": int(sum(int(r["mismatch"]) for r in r1_alt)),
        "alternating_bound_satisfaction_pct": round(100.0 * sum(1 for r in r1_alt if r["within_bound"]) / len(r1_alt), 4),
        "alternating_tokens_pos_median": float(np.median([int(r["tokens_pos"]) for r in r1_alt])),
        "alternating_tokens_pos_max": int(max(int(r["tokens_pos"]) for r in r1_alt)),
        "total_trials": len(r1_std) + len(r1_alt),
        "total_mismatches": int(sum(int(r["mismatch"]) for r in r1_std) + sum(int(r["mismatch"]) for r in r1_alt)),
        "max_depth_tested": int(max(int(r["L"]) for r in r1_std + r1_alt)),
    }

    # ---- R2 ----
    r2_summary: Dict[str, Any] = {}
    for cname, n_docs_corpus in (("quora", 522931), ("nq", 250000)):
        c_recs = by_exp[f"R2_{cname}"]
        by_sys: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in c_recs:
            by_sys[r["system"]].append(r)
        s_act = float(np.mean([float(r["S_actual"]) for r in by_sys["v3-full-guard-sq8"]]))
        blk2: Dict[str, Any] = {
            "N": n_docs_corpus,
            "S_target_pct": 0.01,
            "S_actual_pct": round(100.0 * s_act, 5),
            "n_queries_total": len(by_sys["v3-full-guard-sq8"]),
            "leaks_total": int(sum(int(r.get("leaks", 0)) for r in c_recs)),
            "systems": {},
        }
        for sname, srows in sorted(by_sys.items()):
            recalls = [100.0 * float(r["recall"]) for r in srows]
            lats = [float(r["wall_ms"]) for r in srows]
            dists = [float(r["dist"]) for r in srows if r.get("dist") is not None]
            blk2["systems"][sname] = {
                "recall_pct": round(float(np.mean(recalls)), 2),
                "lat_med_ms": round(float(np.median(lats)), 3),
                "lat_p95_ms": round(float(np.percentile(lats, 95)), 3),
                "dist_mean": round(float(np.mean(dists)), 1) if dists else None,
                "leaks_total": int(sum(int(r.get("leaks", 0)) for r in srows)),
            }
        r2_summary[cname] = blk2

    # ---- R3 ----
    r3_recs = by_exp["R3_mode3_isolation"]
    r3_grouped: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(lambda: {"warm": {}, "cold": {}})
    for r in r3_recs:
        s_key = f"S={r['S']}"
        c_mode = r["cache"]
        var = r["variant"]
        r3_grouped[s_key][c_mode][var] = {
            k: v for k, v in r.items() if k not in ("experiment", "S", "cache", "variant")
        }
    r3_summary: Dict[str, Any] = {}
    for s_key in sorted(r3_grouped.keys(), key=lambda x: float(x.split("=")[1])):
        blk3: Dict[str, Any] = {"warm": r3_grouped[s_key]["warm"], "cold": r3_grouped[s_key]["cold"]}
        for cmode in ("warm", "cold"):
            cm = blk3[cmode]
            sc_f32_s = cm["1_scattered_f32_scalar"]["median_ms"]
            sc_f32_n = cm["2_scattered_f32_neon"]["median_ms"]
            zo_f32_s = cm["3_zorder_f32_scalar"]["median_ms"]
            zo_f32_n = cm["4_zorder_f32_neon"]["median_ms"]
            zo_sq8_s = cm["5_zorder_sq8_scalar"]["median_ms"]
            zo_sq8_n = cm["6_zorder_sq8_neon"]["median_ms"]
            blk3[f"{cmode}_attribution"] = {
                "zorder_gain_on_scalar_f32": round(sc_f32_s / max(1e-6, zo_f32_s), 2),
                "zorder_gain_on_neon_f32": round(sc_f32_n / max(1e-6, zo_f32_n), 2),
                "sq8_gain_on_scalar": round(zo_f32_s / max(1e-6, zo_sq8_s), 2),
                "neon_gain_on_sq8": round(zo_sq8_s / max(1e-6, zo_sq8_n), 2),
                "total_gain_over_scattered_scalar_f32": round(sc_f32_s / max(1e-6, zo_sq8_n), 2),
            }
        r3_summary[s_key] = blk3

    # ---- R4a (all individual trial rows -> median/min/max) ----
    r4a_recs = by_exp["R4a_scaling"]
    by_docs: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for r in r4a_recs:
        by_docs[int(r["docs_revoked"])].append(r)
    scaling_out: List[Dict[str, Any]] = []
    for d_rev in sorted(by_docs):
        rows = by_docs[d_rev]
        walls = [float(r["wall_ms"]) for r in rows]
        scaling_out.append({
            "docs_revoked": d_rev,
            "chunks_revoked": int(rows[0]["chunks_revoked"]),
            "n_edges_deleted": int(rows[0]["n_edges_deleted"]),
            "n_trials": len(rows),
            "vector_writes": int(max(int(r["vector_writes"]) for r in rows)),
            "median_ms": round(float(np.median(walls)), 2),
            "min_ms": round(float(np.min(walls)), 2),
            "max_ms": round(float(np.max(walls)), 2),
        })

    # ---- R4b (recomputed strictly from individual concurrent query records + cutoff metadata) ----
    r4b_meta = by_exp["R4b_concurrent_zedtoken"][-1]
    r4b_qs = by_exp["R4b_concurrent_query"]
    t_swap_ns = int(r4b_meta["t_swap_ns"])
    pre_qs = [q for q in r4b_qs if int(q["zeta"]) == 1]
    post_qs = [q for q in r4b_qs if int(q["zeta"]) == 2]
    in_flight = [q for q in pre_qs if int(q["t_start_ns"]) < t_swap_ns <= int(q["t_end_ns"])]
    started_after_swap_old = [q for q in pre_qs if int(q["t_start_ns"]) >= t_swap_ns]
    post_leaks = sum(int(q["leaked_revoked_chunks"]) for q in post_qs)

    conc_summary = {
        "total_concurrent_queries": len(r4b_qs),
        "pre_revoke_zeta1_queries": len(pre_qs),
        "post_revoke_zeta2_queries": len(post_qs),
        "in_flight_crossing_cutoff": len(in_flight),
        "started_after_swap_on_old_zeta": len(started_after_swap_old),
        "post_zeta_rev_leaked_chunks": int(post_leaks),
        "spicedb_commit_ms": float(r4b_meta["spicedb_commit_ms"]),
        "atomic_snapshot_compile_and_swap_ms": float(r4b_meta["atomic_snapshot_compile_and_swap_ms"]),
        "chunks_revoked_atomically": int(r4b_meta["chunks_revoked_atomically"]),
    }

    # ---- R5 ----
    r5_recs = sorted(by_exp["R5_dynamic_ingestion"], key=lambda r: int(r["batch_vectors"]))
    r5_clean = [
        {k: v for k, v in r.items() if k not in ("experiment", "base_N", "initial_zorder_500k_sec")}
        for r in r5_recs
    ]
    r5_summary = {
        "base_N": int(r5_recs[0].get("base_N", 500000)) if r5_recs else 500000,
        "initial_zorder_500k_sec": float(r5_recs[0].get("initial_zorder_500k_sec", 0.0)) if r5_recs else 0.0,
        "batches": r5_clean,
    }

    fz = freeze_v3_1_status()
    summary: Dict[str, Any] = {
        "schema": SCHEMA_V3_1,
        "git_sha_start": meta.get("git_sha", ""),
        "git_dirty": bool(meta.get("git_dirty", False)),
        "freeze_v3_1_match": fz["match"],
        "freeze_v3_1_files": fz["n_files"],
        "raw_jsonl_path": os.path.relpath(raw_path, REPO_ROOT),
        "raw_records_total": len(recs),
        "raw_records_by_experiment": {k: len(v) for k, v in sorted(by_exp.items())},
        "R1_property_fuzzing": r1_summary,
        "R2_s001_ultra_low_selectivity": r2_summary,
        "R3_mode3_component_isolation": r3_summary,
        "R4_revocation_scaling_and_concurrent_zedtoken": {
            "scaling_postgres_spicedb": scaling_out,
            "concurrent_zedtoken_race": conc_summary,
        },
        "R5_dynamic_ingestion_and_zorder_compaction": r5_summary,
    }
    summary["verdicts"] = _eval_verdicts(summary)
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Deterministically recompute v3.1 reviewer audit summary")
    p.add_argument("--raw", default=DEFAULT_RAW_PATH)
    p.add_argument("--out", default=None)
    p.add_argument("--check", default=None)
    a = p.parse_args(argv)

    text = dumps_summary(recompute_v3_1_summary(a.raw))
    if a.check:
        with open(a.check, "r", encoding="utf-8") as f:
            same = f.read() == text
        print(f"[recompute_v3_1] {'MATCH' if same else 'MISMATCH'}: {a.check}")
        return 0 if same else 1
    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[recompute_v3_1] wrote {a.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
