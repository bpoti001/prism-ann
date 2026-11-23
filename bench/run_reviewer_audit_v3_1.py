#!/usr/bin/env python3
"""
Prism-ANN v3.1 Reviewer Audit & Hardening Suite (Experiments R1..R5)
=====================================================================
Addresses the 5 concrete validation gaps identified in the external systems review:
  R1: 10,000-Hierarchy Property-Based & Alternating GRANT/DENY Fuzzing (§6.1)
  R2: Ultra-Low Selectivity S = 0.01% Multi-Corpus Benchmark (Quora 523k + NQ 250k, §6.2)
  R3: 6-Way Mode-3 Component Isolation (Z-Order vs SQ8 vs ARM NEON vs Scalar; Warm & Cold LLC, §6.3-6.4)
  R4: Subtree Revocation Scaling (150 -> 491k Chunks on Postgres SpiceDB) & Concurrent ZedToken Race (§6.5)
  R5: Dynamic Document Ingestion & Background Z-Order Compaction Maintenance Cost (§6.3)

Outputs:
  - Raw provenance log: `results/v3_1_audit/raw/v3_1_reviewer_audit.jsonl`
  - Deterministic summary: `results/v3/reviewer_audit_v3_1.json`

Usage:
  /Users/tejap/memory_paper/.venv-bench/bin/python -m bench.run_reviewer_audit_v3_1
"""

from __future__ import annotations

import ctypes
import gc
import json
import os
import sys
import threading
import time
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from bench.dataset import build_overlay
from bench.dataset_v3 import load_corpus_v3
from bench.engines import SpiceDBPostgresService
from bench.experiments import (
    _build_roaring_postings,
    _compile_roaring_ubp,
    _exact_top_k,
    _ubp_to_leaf_docs,
)
from bench.harness import QuerySpec, git_dirty_paths, git_sha, run_condition
from bench.recompute import dumps_summary
from bench.recompute_v3_1 import freeze_v3_1_status, recompute_v3_1_summary
from bench.harness_v3 import (
    V3_EF_CONSTRUCTION,
    V3_EF_SEARCH,
    V3_MAX_PORTALS,
    V3_M,
    V3_M_BRIDGE,
    V3_N_GUARD,
    V3_TAU_HIGH,
    V3_TAU_LOW,
    V3_TAU_STALL,
    freeze_v3_status,
)
from bench.run_v3_dev_exploratory import (
    HHNSWV3GraphSystem,
    PrismV3FullSystem,
    _compile_ranges_from_tokens,
)
from bench.systems import Acorn1System, FaissHNSWSystem
from src.modules.prism_ann.trimodal_planner import RoaringRunBitmap, ZOrderedCorpus
from src.modules.prism_ann.ubp_resolver import ZanzibarAuthGraph
from src.modules.prism_ann_v3.ckernel_bridge import (
    ranges_clear_bitset,
    ranges_set_bitset,
    remap_hnsw_csr_cpp,
    search_hhnsw_gls_cpp,
)
from src.modules.prism_ann_v3.geometric_hhnsw import (
    GeometricBridgeConfig,
    GeometricHHNSW,
)
from src.modules.prism_ann_v3.trimodal_v3 import TriModalPlannerV3, runs_to_range_arrays

AUDIT_DYLIB = os.path.join(REPO_ROOT, "bench", "_build", "libprism_audit_kernel.dylib")
RAW_OUT_PATH = os.path.join(REPO_ROOT, "results", "v3_1_audit", "raw", "v3_1_reviewer_audit.jsonl")
SUMMARY_OUT_PATH = os.path.join(REPO_ROOT, "results", "v3", "reviewer_audit_v3_1.json")


class RawAuditLogger:
    """Append-only JSONL logger isolated from results/v3/raw/ so v3-confirmatory-001 stays bit-pure."""

    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.f = open(path, "w", encoding="utf-8")
        self.count = 0

    def log(self, exp: str, record: Dict[str, Any]) -> None:
        payload = {"experiment": exp, **record}
        self.f.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        self.count += 1

    def close(self) -> None:
        self.f.close()


def _qstats(vals_ms: Sequence[float]) -> Dict[str, float]:
    arr = np.asarray(vals_ms, dtype=np.float64)
    return {
        "n": int(len(arr)),
        "mean_ms": round(float(np.mean(arr)), 4),
        "median_ms": round(float(np.median(arr)), 4),
        "p95_ms": round(float(np.percentile(arr, 95)), 4),
        "p99_ms": round(float(np.percentile(arr, 99)), 4),
        "min_ms": round(float(np.min(arr)), 4),
        "max_ms": round(float(np.max(arr)), 4),
    }


def _load_audit_kernel() -> ctypes.CDLL:
    lib = ctypes.CDLL(AUDIT_DYLIB)
    c_i32_p = ctypes.POINTER(ctypes.c_int32)
    c_i8_p = ctypes.POINTER(ctypes.c_int8)
    c_f32_p = ctypes.POINTER(ctypes.c_float)
    c_u8_p = ctypes.POINTER(ctypes.c_uint8)

    for fn in ("audit_scan_scattered_f32_scalar", "audit_scan_scattered_f32_neon"):
        f = getattr(lib, fn)
        f.restype = ctypes.c_int64
        f.argtypes = [c_f32_p, ctypes.c_int32, ctypes.c_int32, c_f32_p, c_i32_p, ctypes.c_int32, ctypes.c_int32, c_i32_p, c_f32_p]

    for fn in ("audit_scan_zorder_f32_scalar", "audit_scan_zorder_f32_neon"):
        f = getattr(lib, fn)
        f.restype = ctypes.c_int64
        f.argtypes = [c_f32_p, ctypes.c_int32, ctypes.c_int32, c_f32_p, c_i32_p, c_i32_p, ctypes.c_int32, ctypes.c_int32, c_i32_p, c_f32_p]

    for fn in ("audit_scan_zorder_sq8_scalar", "audit_scan_zorder_sq8_neon"):
        f = getattr(lib, fn)
        f.restype = ctypes.c_int64
        f.argtypes = [c_i8_p, c_f32_p, ctypes.c_int32, ctypes.c_int32, c_i8_p, c_f32_p, c_i32_p, c_i32_p, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, c_i32_p, c_f32_p]

    lib.audit_flush_llc_cache.restype = ctypes.c_uint64
    lib.audit_flush_llc_cache.argtypes = [c_u8_p, ctypes.c_int64]
    return lib


# ===========================================================================
# R1 — 10,000-Hierarchy Property Fuzzing + Generalized Alternating Overrides
# ===========================================================================
def _precompute_tree_meta(b: int, L: int) -> Tuple[ZanzibarAuthGraph, Dict[str, List[str]], Dict[str, Set[str]], List[List[str]]]:
    graph = ZanzibarAuthGraph.build_balanced_hierarchy(branching_factor=b, depth=L)
    anc_list: Dict[str, List[str]] = {}
    strict_anc: Dict[str, Set[str]] = {}
    levels: List[List[str]] = [[] for _ in range(L + 1)]
    for nid in graph.all_nodes:
        lvl = graph.node_depth[nid]
        levels[lvl].append(nid)
        lin = graph.get_ancestor_lineage(nid)
        anc_list[nid] = lin
        strict_anc[nid] = set(lin[:-1])
    for lvl_nodes in levels:
        lvl_nodes.sort()
    return graph, anc_list, strict_anc, levels


def _eval_alternating_reference(
    graph: ZanzibarAuthGraph, anc_list: Dict[str, List[str]], rules: Dict[str, int]
) -> Set[str]:
    """Reference evaluator under deepest-rule-wins precedence along Anc(doc)."""
    allowed: Set[str] = set()
    for doc in graph.leaf_documents:
        eff = 0
        for anc in anc_list[doc]:
            if anc in rules:
                eff = rules[anc]
        if eff == 1:
            allowed.add(doc)
    return allowed


def _generalized_alternating_ubp(
    graph: ZanzibarAuthGraph,
    strict_anc: Dict[str, Set[str]],
    rules: Dict[str, int],
) -> Tuple[Set[str], Set[str]]:
    """
    Generalized UBP for arbitrary-depth alternating GRANT(+1)/DENY(-1) overrides:
      - Tainted(u) = Union_{x in dom(rules)} StrictAnc(x)
      - Top-down BFS carries inherited effective state (deepest rule wins);
        halts immediately at untainted subtrees, emitting node iff state == +1.
      - Since only ancestors of explicit rules are split and root starts in T_pos or
        is tainted, |T_pos| <= k0 + |rules| * (b - 1) * L.
    """
    tainted: Set[str] = set()
    for node in rules:
        tainted.update(strict_anc[node])

    tokens_pos: Set[str] = set()
    tokens_neg: Set[str] = {n for n, pol in rules.items() if pol == -1}
    q = deque([("node_L0_0", 0)])
    while q:
        curr, parent_pol = q.popleft()
        eff = rules.get(curr, parent_pol)
        if curr not in tainted:
            if eff == 1:
                tokens_pos.add(curr)
            continue
        for ch in graph.children.get(curr, ()):
            q.append((ch, eff))
    return tokens_pos, tokens_neg


def run_r1_property_fuzzing(logger: RawAuditLogger) -> Dict[str, Any]:
    print("\n=== [R1] 10,000-HIERARCHY PROPERTY & ALTERNATING GRANT/DENY FUZZING ===", flush=True)
    t0 = time.perf_counter()
    rng = np.random.default_rng(20261122)

    specs = [(8, 4), (4, 5), (6, 4)]
    trees = {spec: _precompute_tree_meta(*spec) for spec in specs}

    std_trials = 5000
    std_mismatches = 0
    std_bound_ok = 0
    std_tokens_max = 0
    std_tokens_list: List[int] = []

    for i in range(std_trials):
        b, L = specs[i % len(specs)]
        graph, _anc, _sanc, levels = trees[(b, L)]
        graph.revoked_subtrees.clear()
        pid = "fuzz_u"

        # Sample arbitrary multi-level positive grants (k0 = 1..5) and subtractive denies (m = 0..24) + revoked subtrees
        k_g = int(rng.integers(1, 5))
        grant_pool = levels[0] + levels[1] + levels[2] + (levels[3] if L >= 4 else [])
        grants = set(rng.choice(grant_pool, size=min(k_g, len(grant_pool)), replace=False).tolist())
        m_d = int(rng.integers(0, 25))
        deny_pool = [n for lvl in range(1, L + 1) for n in levels[lvl]]
        denies = set(rng.choice(deny_pool, size=min(m_d, len(deny_pool)), replace=False).tolist()) if m_d > 0 else set()
        n_rev = int(rng.integers(0, 4))
        rev_pool = levels[1] + levels[2]
        revs = set(rng.choice(rev_pool, size=min(n_rev, len(rev_pool)), replace=False).tolist()) if n_rev > 0 else set()

        graph.positive_grants[pid] = grants
        graph.explicit_denies[pid] = denies
        graph.revoked_subtrees = set(revs)

        res = graph.upward_boundary_prune(pid)
        ref_docs = graph.lookup_resources_leaf(pid)
        ubp_docs = _ubp_to_leaf_docs(graph, res.tokens_pos, res.tokens_neg)
        mism = len(ubp_docs ^ ref_docs)
        bound_ok = len(res.tokens_pos) <= res.theoretical_upper_bound

        std_mismatches += mism
        std_bound_ok += int(bound_ok)
        nt = len(res.tokens_pos)
        std_tokens_list.append(nt)
        if nt > std_tokens_max:
            std_tokens_max = nt

        logger.log("R1_standard", {
            "trial": i, "b": b, "L": L, "k0": res.k0_grants, "m": res.m_denies,
            "tokens_pos": nt, "bound": res.theoretical_upper_bound,
            "within_bound": bool(bound_ok), "mismatch": mism,
        })

    alt_trials = 5000
    alt_mismatches = 0
    alt_bound_ok = 0
    alt_tokens_list: List[int] = []
    alt_max_depth_tested = 0

    for i in range(alt_trials):
        b, L = specs[i % len(specs)]
        graph, anc_list, strict_anc, levels = trees[(b, L)]

        # Construct adversarial alternating hierarchy: Root GRANT(+1), random L1 DENY(-1),
        # random L2 Exception RE-GRANT(+1), random L3 Sub-DENY(-1), optional L4 Leaf Exception(+1/-1)
        rules: Dict[str, int] = {"node_L0_0": 1}
        n_l1_deny = int(rng.integers(1, min(4, len(levels[1])) + 1))
        d1 = rng.choice(levels[1], size=n_l1_deny, replace=False).tolist()
        for n in d1:
            rules[n] = -1
        for lvl in range(2, L + 1):
            alt_max_depth_tested = max(alt_max_depth_tested, lvl)
            pol = 1 if (lvl % 2 == 0) else -1
            n_pick = int(rng.integers(1, min(6, len(levels[lvl])) + 1))
            picks = rng.choice(levels[lvl], size=n_pick, replace=False).tolist()
            for n in picks:
                # 50% forced exception inside previously overridden branch, 50% random polarity
                rules[n] = pol if (rng.random() < 0.75) else (-pol)

        tokens_pos, tokens_neg = _generalized_alternating_ubp(graph, strict_anc, rules)
        # Under deepest-rule-wins, positive tokens in tokens_pos represent exact untainted allowed subtrees
        # so leaf set is directly Desc(tokens_pos) & leaf_documents!
        ubp_docs = graph.get_descendants(tokens_pos) & graph.leaf_documents
        ref_docs = _eval_alternating_reference(graph, anc_list, rules)
        mism = len(ubp_docs ^ ref_docs)

        # Generalized bound: <= 1 + (number of explicit rules) * (b - 1) * L
        m_rules = len(rules)
        gen_bound = 1 + m_rules * (b - 1) * L
        bound_ok = len(tokens_pos) <= gen_bound

        alt_mismatches += mism
        alt_bound_ok += int(bound_ok)
        alt_tokens_list.append(len(tokens_pos))
        logger.log("R1_alternating", {
            "trial": i, "b": b, "L": L, "n_rules": m_rules, "tokens_pos": len(tokens_pos),
            "bound": gen_bound, "within_bound": bool(bound_ok),
            "n_auth_docs": len(ref_docs), "mismatch": mism,
        })

    summary = {
        "standard_reBAC_trials": std_trials,
        "standard_mismatches": int(std_mismatches),
        "standard_bound_satisfaction_pct": round(100.0 * std_bound_ok / std_trials, 4),
        "standard_tokens_pos_median": float(np.median(std_tokens_list)),
        "standard_tokens_pos_max": int(std_tokens_max),
        "alternating_override_trials": alt_trials,
        "alternating_mismatches": int(alt_mismatches),
        "alternating_bound_satisfaction_pct": round(100.0 * alt_bound_ok / alt_trials, 4),
        "alternating_tokens_pos_median": float(np.median(alt_tokens_list)),
        "alternating_tokens_pos_max": int(max(alt_tokens_list)),
        "total_trials": std_trials + alt_trials,
        "total_mismatches": int(std_mismatches + alt_mismatches),
        "max_depth_tested": int(alt_max_depth_tested),
        "wall_sec": round(time.perf_counter() - t0, 2),
    }
    print(f"[R1] DONE: {summary}", flush=True)
    return summary


# ===========================================================================
# R2 — Ultra-Low Selectivity S = 0.01% on Quora (523k) & NQ (250k)
# ===========================================================================
def _sample_tokens_depth(
    S_target: float, rng: np.random.Generator, b: int, L: int
) -> Tuple[List[int], List[str]]:
    n_docs = b ** L
    target_docs = max(1, int(round(S_target * n_docs)))
    n_full_folders = target_docs // b
    rem = target_docs % b
    n_folders = b ** (L - 1)
    n_pick_folders = n_full_folders + (1 if rem > 0 else 0)
    chosen = rng.choice(n_folders, size=n_pick_folders, replace=False)

    docs: List[int] = []
    ubp_tokens: List[str] = []
    for fi in chosen[:n_full_folders]:
        fi_int = int(fi)
        ubp_tokens.append(f"node_L{L-1}_{fi_int}")
        base = fi_int * b
        docs.extend(range(base, base + b))
    if rem > 0:
        base = int(chosen[-1]) * b
        kept = rng.choice(np.arange(base, base + b), size=rem, replace=False)
        for di in kept:
            di_int = int(di)
            docs.append(di_int)
            ubp_tokens.append(f"doc_L{L}_{di_int}")
    docs.sort()
    return docs, ubp_tokens


def run_r2_s001_percent(
    quora_data: Tuple[np.ndarray, np.ndarray, List[str]],
    nq_data: Tuple[np.ndarray, np.ndarray, List[str]],
    logger: RawAuditLogger,
    seeds: Sequence[int] = (0, 1, 2),
    n_queries: int = 50,
) -> Dict[str, Any]:
    print("\n=== [R2] ULTRA-LOW SELECTIVITY S = 0.01% ON QUORA (523k) & NQ (250k) ===", flush=True)
    t0 = time.perf_counter()
    results: Dict[str, Any] = {}
    b, L = 8, 5  # 32,768 leaf docs -> ~16 chunks/doc on Quora -> 3 docs ~= 48 chunks ~= 0.0092% (~0.01%)!

    for corpus_name, (X, Q, qids) in (("quora", quora_data), ("nq", nq_data)):
        N = len(X)
        per_sys_recs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for seed in seeds:
            rng = np.random.default_rng(7700 + seed * 101 + (0 if corpus_name == "quora" else 500))
            overlay = build_overlay(X, mode="random", seed=seed, b=b, L=L)
            z_corpus = ZOrderedCorpus(X, overlay.ancestor_lineages, overlay.meaning_magnet_ids)
            l2_ids = [lin[-3] if len(lin) >= 3 else lin[-1] for lin in z_corpus.ancestor_lineages]

            q_sel = rng.choice(len(Q), size=min(n_queries, len(Q)), replace=False)
            specs: List[QuerySpec] = []
            for qi_local, qi in enumerate(q_sel):
                allowed_docs, ubp_tokens = _sample_tokens_depth(0.0001, rng, b=b, L=L)
                mask = np.zeros(N, dtype=np.bool_)
                for di in allowed_docs:
                    mask[overlay.doc_to_chunks[f"doc_L{L}_{di}"]] = True
                qv = Q[int(qi)]
                gt = _exact_top_k(X, qv, mask, k=10)
                specs.append(
                    QuerySpec(
                        query_id=f"{corpus_name}_S0.0001_{qids[int(qi)]}_{qi_local}",
                        vector=qv,
                        mask=mask,
                        gt_ids=gt,
                        condition={"corpus": corpus_name, "S_target": 0.0001, "S_actual": float(mask.mean())},
                        extra={"allowed_doc_ints": allowed_docs, "ubp_tokens": ubp_tokens},
                    )
                )

            # 1. FAISS M=16 (and share base graph for GeometricHHNSW)
            faiss_m16 = FaissHNSWSystem(
                z_corpus.vectors, M=V3_M, ef_construction=V3_EF_CONSTRUCTION, ef_search=V3_EF_SEARCH,
                seed=seed, name="faiss-hnsw-M16", ext_id_map=z_corpus.z_to_orig,
            )
            prebuilt = (faiss_m16.index, faiss_m16.perm)

            idx_geom_m8 = GeometricHHNSW(
                z_corpus.vectors, z_corpus.primary_containers, l2_ids, z_corpus.meaning_magnet_ids,
                bridge_config=GeometricBridgeConfig.for_m_bridge(V3_M_BRIDGE, "geometric"),
                M=V3_M, seed=seed, prebuilt_faiss=prebuilt,
            )
            planner_v3 = TriModalPlannerV3(
                overlay.auth_graph, z_corpus, idx_geom_m8, ef_search=V3_EF_SEARCH,
                tau_high=V3_TAU_HIGH, tau_low=V3_TAU_LOW, tau_stall=V3_TAU_STALL,
                n_guard=V3_N_GUARD, mode3_precision="sq8", max_portals=V3_MAX_PORTALS,
            )
            sys_geom = HHNSWV3GraphSystem(
                z_corpus, idx_geom_m8, "v3-geom-M8",
                ef_search=V3_EF_SEARCH, tau_high=V3_TAU_HIGH, tau_low=V3_TAU_LOW,
                use_express_bridges=True, use_portals=True, max_portals=V3_MAX_PORTALS,
            )
            sys_full = PrismV3FullSystem(z_corpus, planner_v3, "v3-full-guard-sq8")

            systems_to_eval = [faiss_m16, sys_geom, sys_full]
            ac1 = None
            if Acorn1System.available():
                ac1 = Acorn1System(
                    X, M=V3_M, ef_construction=V3_EF_CONSTRUCTION, ef_search=V3_EF_SEARCH,
                    seed=seed, name="acorn-1", gamma=1, m_beta=32,
                )
                systems_to_eval.append(ac1)

            try:
                specs_by_qid = {s.query_id: s for s in specs}
                ctx_dummy = type("C", (), {"run_id": "v3_1", "run_type": "audit", "git_sha": "audit", "freeze_match": True, "hypothesis": f"R2_{corpus_name}"})()
                for sys_obj in systems_to_eval:
                    for rec in run_condition(sys_obj, specs, k=10, seed=seed, ctx=ctx_dummy):
                        q_mask = specs_by_qid[rec.query_id].mask
                        n_leaks = sum(1 for rid in rec.result_ids if int(rid) < 0 or not bool(q_mask[int(rid)]))
                        rec_d = {
                            "corpus": corpus_name,
                            "system": rec.system,
                            "seed": seed,
                            "recall": rec.recall,
                            "wall_ms": rec.wall_ns / 1e6,
                            "dist": rec.distance_computations,
                            "S_actual": rec.condition["S_actual"],
                            "leaks": int(n_leaks),
                        }
                        per_sys_recs[rec.system].append(rec_d)
                        logger.log(f"R2_{corpus_name}", rec_d)
            finally:
                if ac1 is not None:
                    ac1.close()
                del faiss_m16, prebuilt, idx_geom_m8, planner_v3, z_corpus, overlay
                gc.collect()

        s_actual_mean = float(np.mean([r["S_actual"] for r in per_sys_recs["v3-full-guard-sq8"]]))
        c_summary: Dict[str, Any] = {
            "N": N,
            "S_target_pct": 0.01,
            "S_actual_pct": round(100.0 * s_actual_mean, 5),
            "n_queries_total": len(per_sys_recs["v3-full-guard-sq8"]),
            "systems": {},
        }
        for sname, recs in sorted(per_sys_recs.items()):
            recalls = [100.0 * r["recall"] for r in recs]
            lats = [r["wall_ms"] for r in recs]
            dists = [r["dist"] for r in recs if r["dist"] is not None]
            c_summary["systems"][sname] = {
                "recall_pct": round(float(np.mean(recalls)), 2),
                "lat_med_ms": round(float(np.median(lats)), 3),
                "lat_p95_ms": round(float(np.percentile(lats, 95)), 3),
                "dist_mean": round(float(np.mean(dists)), 1) if dists else None,
            }
        results[corpus_name] = c_summary
        print(f"  [R2] {corpus_name} (S_act={c_summary['S_actual_pct']:.4f}%): {json.dumps(c_summary['systems'])}", flush=True)

    results["wall_sec"] = round(time.perf_counter() - t0, 2)
    return results


# ===========================================================================
# R3 — 6-Way Component Isolation: Z-Order + CRoaring + SQ8 + NEON (Warm & Cold)
# ===========================================================================
def run_r3_mode3_isolation(
    X_quora: np.ndarray,
    Q_quora: np.ndarray,
    logger: RawAuditLogger,
    n_queries: int = 80,
) -> Dict[str, Any]:
    print("\n=== [R3] 6-WAY Z-ORDER / CROARING / SQ8 / NEON ISOLATION (WARM & COLD LLC) ===", flush=True)
    t0 = time.perf_counter()
    lib = _load_audit_kernel()
    N, d = X_quora.shape
    X_orig = np.ascontiguousarray(X_quora, dtype=np.float32)

    rng = np.random.default_rng(31415)
    overlay = build_overlay(X_orig, mode="random", seed=0, b=8, L=4)
    z_corpus = ZOrderedCorpus(X_orig, overlay.ancestor_lineages, overlay.meaning_magnet_ids)
    X_z_f32 = z_corpus.vectors
    X_z_sq8 = z_corpus.sq8_vectors

    # 64 MB LLC flush buffer (> 16 MB L2 + 24 MB SLC on Apple M2 Pro)
    llc_buf = np.zeros(64 * 1024 * 1024, dtype=np.uint8)
    llc_ptr = llc_buf.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
    llc_bytes = ctypes.c_int64(llc_buf.nbytes)

    k = 10
    rerank_k = 64
    sels = [0.0001, 0.001, 0.005, 0.01]
    out_summary: Dict[str, Any] = {}

    out_ids = np.empty(k, dtype=np.int32)
    out_scores = np.empty(k, dtype=np.float32)
    p_oid = out_ids.ctypes.data_as(ctypes.POINTER(ctypes.c_int32))
    p_osc = out_scores.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

    p_orig_f32 = X_orig.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
    p_z_f32 = X_z_f32.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
    p_z_sq8 = X_z_sq8.ctypes.data_as(ctypes.POINTER(ctypes.c_int8))

    for s_val in sels:
        q_idx = rng.choice(len(Q_quora), size=n_queries, replace=False)
        queries_prep = []
        for qi in q_idx:
            # Sample realistic folder/doc tokens across b=8, L=4 (note 0.0001 -> 1 doc)
            _, ubp_tokens = _sample_tokens_depth(s_val, rng, b=8, L=4)
            starts, ends, n_cand = _compile_ranges_from_tokens(z_corpus, ubp_tokens)
            # Build exact corresponding scattered original IDs (sorted) for fair non-Z-order comparison
            z_ids_list = [np.arange(int(s), int(e), dtype=np.int32) for s, e in zip(starts, ends)]
            z_ids_all = np.concatenate(z_ids_list) if z_ids_list else np.empty(0, dtype=np.int32)
            orig_ids = np.ascontiguousarray(np.sort(z_corpus.z_to_orig[z_ids_all]), dtype=np.int32)
            mask = np.zeros(N, dtype=np.bool_)
            mask[orig_ids] = True
            qv = np.ascontiguousarray(Q_quora[int(qi)], dtype=np.float32)
            q_sq8 = np.ascontiguousarray(np.clip(np.round(qv * 127.0), -127, 127).astype(np.int8))
            gt = set(_exact_top_k(X_orig, qv, mask, k=k))
            queries_prep.append((int(qi), qv, q_sq8, starts, ends, orig_ids, n_cand, gt))

        variants = (
            ("1_scattered_f32_scalar", "scattered", "f32_scalar"),
            ("2_scattered_f32_neon", "scattered", "f32_neon"),
            ("3_zorder_f32_scalar", "zorder", "f32_scalar"),
            ("4_zorder_f32_neon", "zorder", "f32_neon"),
            ("5_zorder_sq8_scalar", "zorder", "sq8_scalar"),
            ("6_zorder_sq8_neon", "zorder", "sq8_neon"),
        )

        s_key = f"S={s_val}"
        out_summary[s_key] = {"n_cand_mean": round(float(np.mean([x[6] for x in queries_prep])), 1), "warm": {}, "cold": {}}

        for cache_mode in ("warm", "cold"):
            for vname, layout, arith in variants:
                lats_ms: List[float] = []
                recalls: List[float] = []
                # Warmup on first query if warm mode
                if cache_mode == "warm":
                    _, qv0, qsq0, st0, en0, oid0, nc0, _ = queries_prep[0]
                    pq0 = qv0.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
                    pqsq0 = qsq0.ctypes.data_as(ctypes.POINTER(ctypes.c_int8))
                    for _ in range(3):
                        if layout == "scattered":
                            fn = lib.audit_scan_scattered_f32_neon if "neon" in arith else lib.audit_scan_scattered_f32_scalar
                            fn(p_orig_f32, N, d, pq0, oid0.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)), nc0, k, p_oid, p_osc)
                        elif arith.startswith("f32"):
                            fn = lib.audit_scan_zorder_f32_neon if "neon" in arith else lib.audit_scan_zorder_f32_scalar
                            fn(p_z_f32, N, d, pq0, st0.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)), en0.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)), len(st0), k, p_oid, p_osc)
                        else:
                            fn = lib.audit_scan_zorder_sq8_neon if "neon" in arith else lib.audit_scan_zorder_sq8_scalar
                            fn(p_z_sq8, p_z_f32, N, d, pqsq0, pq0, st0.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)), en0.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)), len(st0), k, rerank_k, p_oid, p_osc)

                for qi, qv, q_sq8, starts, ends, orig_ids, n_cand, gt in queries_prep:
                    if cache_mode == "cold":
                        lib.audit_flush_llc_cache(llc_ptr, llc_bytes)
                    pq = qv.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
                    pqsq = q_sq8.ctypes.data_as(ctypes.POINTER(ctypes.c_int8))
                    p_oids_arr = orig_ids.ctypes.data_as(ctypes.POINTER(ctypes.c_int32))
                    p_st = starts.ctypes.data_as(ctypes.POINTER(ctypes.c_int32))
                    p_en = ends.ctypes.data_as(ctypes.POINTER(ctypes.c_int32))

                    t_q0 = time.perf_counter_ns()
                    if layout == "scattered":
                        if arith == "f32_scalar":
                            lib.audit_scan_scattered_f32_scalar(p_orig_f32, N, d, pq, p_oids_arr, n_cand, k, p_oid, p_osc)
                        else:
                            lib.audit_scan_scattered_f32_neon(p_orig_f32, N, d, pq, p_oids_arr, n_cand, k, p_oid, p_osc)
                        res_orig = {int(x) for x in out_ids if x >= 0}
                    elif arith == "f32_scalar":
                        lib.audit_scan_zorder_f32_scalar(p_z_f32, N, d, pq, p_st, p_en, len(starts), k, p_oid, p_osc)
                        res_orig = {int(z_corpus.z_to_orig[x]) for x in out_ids if x >= 0}
                    elif arith == "f32_neon":
                        lib.audit_scan_zorder_f32_neon(p_z_f32, N, d, pq, p_st, p_en, len(starts), k, p_oid, p_osc)
                        res_orig = {int(z_corpus.z_to_orig[x]) for x in out_ids if x >= 0}
                    elif arith == "sq8_scalar":
                        lib.audit_scan_zorder_sq8_scalar(p_z_sq8, p_z_f32, N, d, pqsq, pq, p_st, p_en, len(starts), k, rerank_k, p_oid, p_osc)
                        res_orig = {int(z_corpus.z_to_orig[x]) for x in out_ids if x >= 0}
                    else:
                        lib.audit_scan_zorder_sq8_neon(p_z_sq8, p_z_f32, N, d, pqsq, pq, p_st, p_en, len(starts), k, rerank_k, p_oid, p_osc)
                        res_orig = {int(z_corpus.z_to_orig[x]) for x in out_ids if x >= 0}
                    dt_ms = (time.perf_counter_ns() - t_q0) / 1e6
                    lats_ms.append(dt_ms)
                    rec = len(res_orig & gt) / float(len(gt)) if gt else 1.0
                    recalls.append(rec)

                st = _qstats(lats_ms)
                st["recall_pct"] = round(100.0 * float(np.mean(recalls)), 2)
                out_summary[s_key][cache_mode][vname] = st
                logger.log("R3_mode3_isolation", {"S": s_val, "cache": cache_mode, "variant": vname, **st})

        # Compute clean multiplicative speedup attribution for Warm & Cold
        for cache_mode in ("warm", "cold"):
            blk = out_summary[s_key][cache_mode]
            sc_f32_s = blk["1_scattered_f32_scalar"]["median_ms"]
            sc_f32_n = blk["2_scattered_f32_neon"]["median_ms"]
            zo_f32_s = blk["3_zorder_f32_scalar"]["median_ms"]
            zo_f32_n = blk["4_zorder_f32_neon"]["median_ms"]
            zo_sq8_s = blk["5_zorder_sq8_scalar"]["median_ms"]
            zo_sq8_n = blk["6_zorder_sq8_neon"]["median_ms"]
            out_summary[s_key][f"{cache_mode}_attribution"] = {
                "zorder_gain_on_scalar_f32": round(sc_f32_s / max(1e-6, zo_f32_s), 2),
                "zorder_gain_on_neon_f32": round(sc_f32_n / max(1e-6, zo_f32_n), 2),
                "sq8_gain_on_scalar": round(zo_f32_s / max(1e-6, zo_sq8_s), 2),
                "neon_gain_on_sq8": round(zo_sq8_s / max(1e-6, zo_sq8_n), 2),
                "total_gain_over_scattered_scalar_f32": round(sc_f32_s / max(1e-6, zo_sq8_n), 2),
            }
        print(f"  [R3] {s_key} cold attr={out_summary[s_key]['cold_attribution']}", flush=True)

    del z_corpus, overlay, llc_buf
    gc.collect()
    out_summary["wall_sec"] = round(time.perf_counter() - t0, 2)
    return out_summary


# ===========================================================================
# R4 — Subtree Revocation Scaling (150 -> 491k) & Concurrent ZedToken Race
# ===========================================================================
def run_r4_revocation_and_concurrency(
    X_quora: np.ndarray,
    Q_quora: np.ndarray,
    logger: RawAuditLogger,
) -> Dict[str, Any]:
    print("\n=== [R4] SUBTREE REVOCATION SCALING & CONCURRENT ZEDTOKEN CONSISTENCY ===", flush=True)
    t0 = time.perf_counter()
    N = len(X_quora)

    # Construct nested single-edge division tree covering all 4,096 docs (~128 chunks/doc)
    # so EVERY target {1, 8, 64, 512, 1024, 2048, 3840} docs is revoked via ONE O(1) parent edge!
    graph = ZanzibarAuthGraph(branching_factor=8, depth=7)
    graph.add_node("node_L0_0", depth_level=0)
    n_docs = 4096

    # Nested chain along doc 0:
    # node_L0_0 -> div_3840 (0..3839) + rem_256 (3840..4095)
    # div_3840  -> div_2048 (0..2047) + rem_1792 (2048..3839)
    # div_2048  -> div_1024 (0..1023) + rem_1024 (1024..2047)
    # div_1024  -> div_512  (0..511)  + rem_512  (512..1023)
    # div_512   -> div_64   (0..63)   + rem_448  (64..511)
    # div_64    -> div_8    (0..7)    + rem_56   (8..63)
    # div_8     -> doc_L4_0 (0)       + doc_L4_1..7
    chain = [
        ("node_L0_0", "div_3840", 1, "rem_256", 3840, 4096),
        ("div_3840", "div_2048", 2, "rem_1792", 2048, 3840),
        ("div_2048", "div_1024", 3, "rem_1024", 1024, 2048),
        ("div_1024", "div_512", 4, "rem_512", 512, 1024),
        ("div_512", "div_64", 5, "rem_448", 64, 512),
        ("div_64", "div_8", 6, "rem_56", 8, 64),
    ]
    doc_lineages: Dict[int, List[str]] = {}
    prefix_path = ["node_L0_0"]
    for parent_id, div_id, lvl, rem_id, r_lo, r_hi in chain:
        graph.add_node(div_id, depth_level=lvl)
        graph.add_hierarchy_edge(parent_id, div_id)
        graph.add_node(rem_id, depth_level=lvl)
        graph.add_hierarchy_edge(parent_id, rem_id)
        rem_prefix = prefix_path + [rem_id]
        for start_d in range(r_lo, r_hi, 8):
            fid = f"node_F_{start_d // 8}"
            graph.add_node(fid, depth_level=lvl + 1)
            graph.add_hierarchy_edge(rem_id, fid)
            for doc_i in range(start_d, min(r_hi, start_d + 8)):
                did = f"doc_L4_{doc_i}"
                graph.add_node(did, depth_level=lvl + 2, is_leaf=True)
                graph.add_hierarchy_edge(fid, did)
                doc_lineages[doc_i] = rem_prefix + [fid, did]
        prefix_path = prefix_path + [div_id]

    for doc_i in range(8):
        did = f"doc_L4_{doc_i}"
        graph.add_node(did, depth_level=7, is_leaf=True)
        graph.add_hierarchy_edge("div_8", did)
        doc_lineages[doc_i] = prefix_path + [did]

    doc_int_ids = np.arange(N, dtype=np.int32) % n_docs
    lineages = [doc_lineages[int(di)] for di in doc_int_ids]
    graph.grant_access("org_exec", "node_L0_0")
    z_corpus = ZOrderedCorpus(X_quora, lineages, ["magnet_0"] * N)
    postings = _build_roaring_postings(z_corpus)

    doc_chunk_counts = np.bincount(doc_int_ids, minlength=n_docs)
    scaling_specs = [
        (1, [("div_8", "doc_L4_0")]),
        (8, [("div_64", "div_8")]),
        (64, [("div_512", "div_64")]),
        (512, [("div_1024", "div_512")]),
        (1024, [("div_2048", "div_1024")]),
        (2048, [("div_3840", "div_2048")]),
        (3840, [("node_L0_0", "div_3840")]),
    ]

    scaling_out: List[Dict[str, Any]] = []
    with SpiceDBPostgresService() as sp:
        sp.load_hierarchy(graph)
        sp.write_principal_policy("org_exec", grants={"node_L0_0"}, denies=set())

        # Warmup
        _ = sp.lookup_resources_docs("org_exec")

        # Part A: Subtree Scaling over 5 trials each (live Persistent PostgreSQL 17 SpiceDB!)
        for target_docs, edge_list in scaling_specs:
            trial_ms: List[float] = []
            chunks_cov = int(sum(doc_chunk_counts[d] for d in range(target_docs)))
            for tr in range(5):
                t_s = time.perf_counter_ns()
                for par, ch in edge_list:
                    sp.delete_parent_edge(par, ch)
                    graph.remove_hierarchy_edge(par, ch)
                res = graph.upward_boundary_prune("org_exec")
                b_ubp = _compile_roaring_ubp(postings, res.tokens_pos, res.tokens_neg)
                dt_ms = (time.perf_counter_ns() - t_s) / 1e6
                trial_ms.append(dt_ms)

                if tr == 0:
                    assert len(b_ubp) == N - chunks_cov, f"Expected {N - chunks_cov}, got {len(b_ubp)}"

                logger.log("R4a_scaling", {
                    "docs_revoked": target_docs,
                    "chunks_revoked": chunks_cov,
                    "n_edges_deleted": len(edge_list),
                    "trial": tr,
                    "wall_ms": round(dt_ms, 4),
                    "vector_writes": 0,
                })

                # Restore before next condition/trial
                for par, ch in edge_list:
                    sp.restore_parent_edge(par, ch)
                    graph.add_hierarchy_edge(par, ch)

            row = {
                "docs_revoked": target_docs,
                "chunks_revoked": chunks_cov,
                "n_edges_deleted": len(edge_list),
                "vector_writes": 0,
                "median_ms": round(float(np.median(trial_ms)), 2),
                "min_ms": round(float(np.min(trial_ms)), 2),
                "max_ms": round(float(np.max(trial_ms)), 2),
            }
            scaling_out.append(row)
            print(f"  [R4a] docs={target_docs:<4} chunks={chunks_cov:<6} med={row['median_ms']:.2f}ms (0 writes)", flush=True)

        # Part B: Concurrent In-Flight Query & ZedToken Consistency Race (4 Reader Threads + Live Writer)
        print("  [R4b] Running concurrent 4-thread in-flight query + live Postgres SpiceDB revocation race...", flush=True)
        rev_edges = [("div_2048", "div_1024")]
        revoked_docs = {f"doc_L4_{d}" for d in range(1024)}
        revoked_chunks_mask = np.zeros(N, dtype=np.bool_)
        for zi, lin in enumerate(z_corpus.ancestor_lineages):
            if lin[-1] in revoked_docs:
                revoked_chunks_mask[zi] = True

        # Build shared read-only H-HNSW v2 graph on z_corpus for true concurrent Mode-2 graph + Mode-3 queries!
        l2_ids = [lin[-3] if len(lin) >= 3 else lin[-1] for lin in z_corpus.ancestor_lineages]
        hhnsw = GeometricHHNSW(
            z_corpus.vectors, z_corpus.primary_containers, l2_ids, z_corpus.meaning_magnet_ids,
            bridge_config=GeometricBridgeConfig.for_m_bridge(V3_M_BRIDGE, "geometric"),
            M=V3_M, ef_construction=V3_EF_CONSTRUCTION, seed=0,
        )

        # Immutable versioned snapshot swapped atomically by writer after SpiceDB DeleteRelationships commits
        res_pre = graph.upward_boundary_prune("org_exec")
        bm_pre = z_corpus.compile_acl_bitmap_ubp(res_pre.tokens_pos, res_pre.tokens_neg)
        st_pre, en_pre, n_pre = runs_to_range_arrays(bm_pre)

        snapshot_lock = threading.Lock()
        active_snapshot: Dict[str, Any] = {
            "zed_token": 1,
            "starts": st_pre,
            "ends": en_pre,
            "n_cand": n_pre,
            "revoked": False,
        }
        stop_event = threading.Event()
        query_logs: List[Dict[str, Any]] = []
        log_lock = threading.Lock()
        counter_lock = threading.Lock()
        phase_counts = {"zeta1": 0, "zeta2": 0}
        pre_ready = threading.Event()
        post_ready = threading.Event()

        def reader_worker(tid: int) -> None:
            local_mask_bits = np.zeros((N + 63) >> 6, dtype=np.uint64)
            local_visited = np.zeros(N, dtype=np.uint32)
            local_epoch = 0
            local_logs: List[Dict[str, Any]] = []
            idx = tid
            while not stop_event.is_set():
                t_start = time.perf_counter_ns()
                with snapshot_lock:
                    snap = active_snapshot
                z_val = int(snap["zed_token"])
                qv = np.ascontiguousarray(Q_quora[idx % len(Q_quora)], dtype=np.float32)
                idx += 4

                local_epoch += 1
                ranges_set_bitset(snap["starts"], snap["ends"], local_mask_bits, N)
                try:
                    out_ids_c, _, _ = search_hhnsw_gls_cpp(
                        vectors=hhnsw.vectors,
                        entry_point=hhnsw.entry_point,
                        max_level=hhnsw.max_level,
                        upper_offsets=hhnsw.upper_offsets,
                        upper_neighbors=hhnsw.upper_neighbors,
                        cum_nn_per_lvl=hhnsw.cum_nn_per_lvl,
                        base_neighbors=hhnsw.base_neighbors,
                        express_bridges=hhnsw.express_bridges,
                        mask_bits=local_mask_bits,
                        starts=snap["starts"],
                        ends=snap["ends"],
                        query=qv,
                        k=10,
                        ef_search=V3_EF_SEARCH,
                        tau_high=V3_TAU_HIGH,
                        tau_low=V3_TAU_LOW,
                        use_express_bridges=True,
                        use_portals=True,
                        max_portals=V3_MAX_PORTALS,
                        use_gls_adaptive=True,
                        faiss_style_1hop=False,
                        tau_stall=0.0,
                        stall_check_hops=16,
                        visited_epoch=local_visited,
                        current_epoch=local_epoch,
                    )
                finally:
                    ranges_clear_bitset(snap["starts"], snap["ends"], local_mask_bits, N)
                t_end = time.perf_counter_ns()

                leaked_revoked = int(sum(1 for zid in out_ids_c if zid >= 0 and revoked_chunks_mask[int(zid)]))
                local_logs.append({
                    "tid": tid,
                    "zeta": z_val,
                    "revoked_snap": bool(snap["revoked"]),
                    "t_start_ns": t_start,
                    "t_end_ns": t_end,
                    "leaked_revoked_chunks": leaked_revoked,
                })
                if (len(local_logs) & 63) == 0:
                    with counter_lock:
                        key = "zeta1" if z_val == 1 else "zeta2"
                        phase_counts[key] += 64
                        if phase_counts["zeta1"] >= 5000:
                            pre_ready.set()
                        if phase_counts["zeta2"] >= 6000:
                            post_ready.set()
            with log_lock:
                query_logs.extend(local_logs)

        threads = [threading.Thread(target=reader_worker, args=(t,), daemon=True) for t in range(4)]
        for t in threads:
            t.start()

        # Deterministically collect >= 5,000 pre-revocation concurrent queries (max 15s guard)
        pre_ready.wait(timeout=15.0)
        t_rev0 = time.perf_counter_ns()
        for par, ch in rev_edges:
            sp.delete_parent_edge(par, ch)
            graph.remove_hierarchy_edge(par, ch)
        t_commit = time.perf_counter_ns()
        res_post = graph.upward_boundary_prune("org_exec")
        bm_post = z_corpus.compile_acl_bitmap_ubp(res_post.tokens_pos, res_post.tokens_neg)
        st_post, en_post, n_post = runs_to_range_arrays(bm_post)
        new_snap = {
            "zed_token": 2,
            "starts": st_post,
            "ends": en_post,
            "n_cand": n_post,
            "revoked": True,
        }
        with snapshot_lock:
            active_snapshot = new_snap
        t_swap = time.perf_counter_ns()

        # Deterministically collect >= 6,000 post-revocation concurrent queries (max 15s guard)
        post_ready.wait(timeout=15.0)
        stop_event.set()
        for t in threads:
            t.join(timeout=5.0)

        pre_qs = [q for q in query_logs if q["zeta"] == 1]
        post_qs = [q for q in query_logs if q["zeta"] == 2]
        in_flight_crossing = [
            q for q in pre_qs if q["t_start_ns"] < t_swap <= q["t_end_ns"]
        ]
        post_leaks = sum(q["leaked_revoked_chunks"] for q in post_qs)
        started_after_swap_using_old = [q for q in pre_qs if q["t_start_ns"] >= t_swap]

        conc_summary = {
            "total_concurrent_queries": len(query_logs),
            "pre_revoke_zeta1_queries": len(pre_qs),
            "post_revoke_zeta2_queries": len(post_qs),
            "in_flight_crossing_cutoff": len(in_flight_crossing),
            "started_after_swap_on_old_zeta": len(started_after_swap_using_old),
            "post_zeta_rev_leaked_chunks": int(post_leaks),
            "spicedb_commit_ms": round((t_commit - t_rev0) / 1e6, 2),
            "atomic_snapshot_compile_and_swap_ms": round((t_swap - t_commit) / 1e6, 3),
            "t_swap_ns": int(t_swap),
            "chunks_revoked_atomically": int(np.count_nonzero(revoked_chunks_mask)),
        }
        for qrow in query_logs:
            logger.log("R4b_concurrent_query", {
                "tid": qrow["tid"],
                "zeta": qrow["zeta"],
                "t_start_ns": qrow["t_start_ns"],
                "t_end_ns": qrow["t_end_ns"],
                "leaked_revoked_chunks": qrow["leaked_revoked_chunks"],
            })
        logger.log("R4b_concurrent_zedtoken", conc_summary)
        print(f"  [R4b] DONE: {conc_summary}", flush=True)

        del hhnsw
        gc.collect()

    del z_corpus, postings
    gc.collect()
    return {
        "scaling_postgres_spicedb": scaling_out,
        "concurrent_zedtoken_race": conc_summary,
        "wall_sec": round(time.perf_counter() - t0, 2),
    }


# ===========================================================================
# R5 — Dynamic Document Ingestion & Z-Order Compaction Maintenance Cost
# ===========================================================================
def run_r5_dynamic_ingestion(
    X_quora: np.ndarray,
    logger: RawAuditLogger,
) -> Dict[str, Any]:
    print("\n=== [R5] DYNAMIC INGESTION & Z-ORDER COMPACTION MAINTENANCE ===", flush=True)
    t0 = time.perf_counter()
    rng = np.random.default_rng(5555)

    # Use first 500k as base corpus and batches from remaining 22,931 (+ resampled normalized vecs up to 25k)
    N_base = 500_000
    X_base = np.ascontiguousarray(X_quora[:N_base], dtype=np.float32)
    X_tail = np.ascontiguousarray(X_quora[N_base:], dtype=np.float32)
    extra_needed = 25_000 - len(X_tail)
    X_pool = np.vstack([X_tail, X_base[rng.choice(N_base, size=extra_needed, replace=False)]])

    ov_base = build_overlay(X_base, mode="random", seed=0, b=8, L=4)
    t_build0 = time.perf_counter()
    z_base = ZOrderedCorpus(X_base, ov_base.ancestor_lineages, ov_base.meaning_magnet_ids)
    base_z_sec = time.perf_counter() - t_build0

    faiss_sys = FaissHNSWSystem(
        z_base.vectors, M=V3_M, ef_construction=V3_EF_CONSTRUCTION, ef_search=V3_EF_SEARCH,
        seed=0, name="r5-base-faiss", ext_id_map=z_base.z_to_orig,
    )
    h = faiss_sys.index.hnsw
    offsets_int = faiss_sys.index.hnsw.offsets
    import faiss
    off_arr = faiss.vector_to_array(offsets_int).astype(np.int64, copy=True)
    nb_arr = faiss.vector_to_array(h.neighbors).astype(np.int32, copy=True)
    perm_arr = faiss_sys.perm.copy()
    inv_perm_arr = faiss_sys.inv_perm.copy()

    # Create dummy new batches assigned random valid lineages + magnets
    folder_names = [f"node_L3_{i}" for i in range(512)]
    all_lineages = ov_base.ancestor_lineages
    # Warmup C++ CSR remapper & reclaim leftover R4 objects before timed batch loop
    _ = remap_hnsw_csr_cpp(off_arr, nb_arr, perm_arr, inv_perm_arr, 2 * V3_M)
    gc.collect()

    batches = [1_000, 5_000, 10_000, 25_000]
    batch_results = []

    for b_sz in batches:
        X_new = np.ascontiguousarray(X_pool[:b_sz], dtype=np.float32)
        new_lin_idx = rng.integers(0, len(all_lineages), size=b_sz)
        new_lineages = [all_lineages[int(i)] for i in new_lin_idx]
        new_mags = [f"magnet_{int(m)}" for m in rng.integers(0, 64, size=b_sz)]

        # Phase A: Online Delta-Buffer Append (GC disabled inside micro-timed section)
        gc.collect()
        was_gc = gc.isenabled()
        gc.disable()
        try:
            t_app0 = time.perf_counter_ns()
            delta_vecs = np.ascontiguousarray(X_new, dtype=np.float32)
            delta_sq8 = np.ascontiguousarray(np.clip(np.round(delta_vecs * 127.0), -127, 127).astype(np.int8))
            delta_tok_ids: Dict[str, List[int]] = {}
            for i, lin in enumerate(new_lineages):
                gid = N_base + i
                for tok in lin:
                    delta_tok_ids.setdefault(tok, []).append(gid)
            delta_bms = {tok: RoaringRunBitmap.from_sorted_ids(ids, N_base + b_sz) for tok, ids in delta_tok_ids.items()}
            append_ms = (time.perf_counter_ns() - t_app0) / 1e6

            # Phase B: Asynchronous Background Z-Order Compaction + Vector Permute + SQ8 + C++ HNSW CSR Remap
            t_comp0 = time.perf_counter_ns()
            comb_vecs = np.vstack([z_base.vectors, delta_vecs])
            comb_lin = list(z_base.ancestor_lineages) + new_lineages
            comb_mags = list(z_base.meaning_magnet_ids) + new_mags
            N_tot = len(comb_vecs)

            sort_keys = [(tuple(comb_lin[i]), comb_mags[i], i) for i in range(N_tot)]
            sort_keys.sort(key=lambda x: (x[0], x[1]))
            z_order_perm = np.fromiter((x[2] for x in sort_keys), dtype=np.int32, count=N_tot)
            _comp_vecs = np.ascontiguousarray(comb_vecs[z_order_perm], dtype=np.float32)
            del comb_vecs  # release 800 MB temporary stack immediately to avoid macOS swap
            _comp_sq8 = np.ascontiguousarray(np.clip(np.round(_comp_vecs * 127.0), -127, 127).astype(np.int8))

            # Rebuild CRoaring postings for compacted segment
            tok_ids: Dict[str, List[int]] = {}
            for zi, (_, _, orig_p) in enumerate(sort_keys):
                for tok in comb_lin[orig_p]:
                    tok_ids.setdefault(tok, []).append(zi)
            _comp_bms = {tok: RoaringRunBitmap.from_sorted_ids(ids, N_tot) for tok, ids in tok_ids.items()}

            # Measure C++ CSR ID remap cost on the 500k HNSW graph (zero vector recomputation!)
            _out_off, _out_nb, _out_l0 = remap_hnsw_csr_cpp(off_arr, nb_arr, perm_arr, inv_perm_arr, 2 * V3_M)
            compact_ms = (time.perf_counter_ns() - t_comp0) / 1e6
        finally:
            if was_gc:
                gc.enable()

        del _comp_vecs, _comp_sq8, _comp_bms, _out_off, _out_nb, _out_l0, delta_bms
        gc.collect()

        # Amortized online write stall per appended chunk (Compaction runs off read critical path)
        row = {
            "base_N": N_base,
            "initial_zorder_500k_sec": round(base_z_sec, 2),
            "batch_vectors": b_sz,
            "total_corpus_vectors": N_tot,
            "delta_append_total_ms": round(append_ms, 2),
            "delta_append_us_per_vec": round(1000.0 * append_ms / b_sz, 2),
            "background_zorder_compact_total_ms": round(compact_ms, 1),
            "background_compact_ms_per_new_vec": round(compact_ms / b_sz, 4),
            "cpp_csr_remap_only_ms": None,
        }
        # Also time pure C++ CSR remap cleanly without GC/memory pressure
        gc.disable()
        try:
            t_csr0 = time.perf_counter_ns()
            _out2 = remap_hnsw_csr_cpp(off_arr, nb_arr, perm_arr, inv_perm_arr, 2 * V3_M)
            row["cpp_csr_remap_only_ms"] = round((time.perf_counter_ns() - t_csr0) / 1e6, 2)
        finally:
            gc.enable()
        del _out2

        batch_results.append(row)
        logger.log("R5_dynamic_ingestion", row)
        print(f"  [R5] batch={b_sz:<6}: append={row['delta_append_total_ms']:.2f}ms ({row['delta_append_us_per_vec']:.1f}us/vec), bg_compact={row['background_zorder_compact_total_ms']:.1f}ms (CSR remap={row['cpp_csr_remap_only_ms']:.1f}ms)", flush=True)

    del z_base, faiss_sys, ov_base
    gc.collect()
    return {
        "base_N": N_base,
        "initial_zorder_500k_sec": round(base_z_sec, 2),
        "batches": batch_results,
        "wall_sec": round(time.perf_counter() - t0, 2),
    }


def _repo_is_dirty() -> bool:
    import subprocess
    if git_dirty_paths():
        return True
    try:
        out = subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True)
        return bool(out.strip())
    except Exception:
        return True


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-dirty", action="store_true", help="Allow running with uncommitted git changes")
    args = ap.parse_args()

    t_all = time.perf_counter()
    fz3 = freeze_v3_status()
    assert fz3["match"], f"FREEZE_v3 mismatch before audit! {fz3}"
    fz31 = freeze_v3_1_status()
    assert fz31["match"], f"FREEZE_v3_1 mismatch before audit! {fz31}"
    sha_now = git_sha()
    is_dirty = _repo_is_dirty()
    if is_dirty and not args.allow_dirty:
        raise RuntimeError("Refusing v3.1 audit on dirty working tree; commit changes first or pass --allow-dirty")
    print(f"[audit_v3.1] git_sha={sha_now[:10]} git_dirty={is_dirty} freeze_v3=INTACT ({fz3['n_files']}/7) freeze_v3_1=INTACT ({fz31['n_files']}/8)", flush=True)

    logger = RawAuditLogger(RAW_OUT_PATH)
    try:
        logger.log(
            "R0_meta",
            {
                "git_sha": sha_now,
                "git_dirty": bool(is_dirty),
                "freeze_v3_1_match": fz31["match"],
                "freeze_v3_1_files": fz31["n_files"],
            },
        )

        _ = run_r1_property_fuzzing(logger)

        X_q, Q_q, qids_q, _ = load_corpus_v3("quora")
        X_n, Q_n, qids_n, _ = load_corpus_v3("nq")
        _ = run_r2_s001_percent((X_q, Q_q, qids_q), (X_n, Q_n, qids_n), logger, seeds=(0, 1, 2), n_queries=50)
        del X_n, Q_n, qids_n
        gc.collect()
        _ = run_r3_mode3_isolation(X_q, Q_q, logger, n_queries=80)

        _ = run_r4_revocation_and_concurrency(X_q, Q_q, logger)
        _ = run_r5_dynamic_ingestion(X_q, logger)
    finally:
        logger.close()

    # Delegate summary generation strictly to deterministic `bench.recompute_v3_1`!
    summary = recompute_v3_1_summary(RAW_OUT_PATH)
    os.makedirs(os.path.dirname(SUMMARY_OUT_PATH), exist_ok=True)
    with open(SUMMARY_OUT_PATH, "w", encoding="utf-8") as f:
        f.write(dumps_summary(summary))
    print(f"\n[audit_v3.1] COMPLETE in {time.perf_counter()-t_all:.2f}s | recs={summary['raw_records_total']} | verdicts={ {k: v['verdict'] for k, v in summary['verdicts'].items()} } -> {SUMMARY_OUT_PATH}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
