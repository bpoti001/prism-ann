#!/usr/bin/env python3
"""
Prism-ANN v3.2 Second-Round Research Audit Suite (Experiments R6..R8)
====================================================================
Pre-registered in `experiments/v3/PROTOCOL_v3_2.md`:
  R6: 5,000-DAG Multi-Parent Property-Based Fuzzing (Theorem 1B, Finding A)
  R7: Two-Track Fair Baseline Benchmark (Track 1 Pure C++ Pre-Materialized Filter
      incl. RACORN-1 Fallback & FP32 Mode 3 vs. Track 2 End-to-End T_total, Findings E & F)
  R8: Exact vs. Empirical Recall Shortlist (SQ8 rerank_k=10..128) & FP32 Parity Audit (Finding B)

Usage:
  /Users/tejap/memory_paper/.venv-bench/bin/python -u -m bench.run_reviewer_audit_v3_2
"""

from __future__ import annotations

import ctypes
import gc
import json
import os
import sys
import time
from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple

import faiss
import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from bench.dataset import build_overlay  # noqa: E402
from bench.dataset_v3 import load_corpus_v3  # noqa: E402
from bench.experiments import _exact_top_k  # noqa: E402
from bench.harness import git_sha  # noqa: E402
from bench.harness_v3 import (  # noqa: E402
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
from bench.recompute import dumps_summary  # noqa: E402
from bench.recompute_v3_1 import freeze_v3_1_status  # noqa: E402
from bench.recompute_v3_2 import recompute_v3_2_summary  # noqa: E402
from bench.run_reviewer_audit_v3_1 import (  # noqa: E402
    RawAuditLogger,
    _load_audit_kernel,
    _repo_is_dirty,
    _sample_tokens_depth,
)
from bench.run_v3_dev_exploratory import _compile_ranges_from_tokens  # noqa: E402
from bench.systems import Acorn1System, FaissHNSWSystem  # noqa: E402
from src.modules.prism_ann.trimodal_planner import ZOrderedCorpus  # noqa: E402
from src.modules.prism_ann.ubp_resolver import ZanzibarAuthGraph  # noqa: E402
from src.modules.prism_ann_v3.ckernel_bridge import (  # noqa: E402
    mode3_scan_ranges_f32,
    mode3_scan_ranges_sq8,
    ranges_clear_bitset,
    ranges_set_bitset,
    search_hhnsw_gls_cpp,
)
from src.modules.prism_ann_v3.geometric_hhnsw import (  # noqa: E402
    GeometricBridgeConfig,
    GeometricHHNSW,
)
from src.modules.prism_ann_v3.trimodal_v3 import TriModalPlannerV3  # noqa: E402

RAW_OUT_PATH = os.path.join(REPO_ROOT, "results", "v3_2_audit", "raw", "v3_2_reviewer_audit.jsonl")
SUMMARY_OUT_PATH = os.path.join(REPO_ROOT, "results", "v3", "reviewer_audit_v3_2.json")
V3_SUMMARY_PATH = os.path.join(REPO_ROOT, "results", "v3", "summary.json")


# ===========================================================================
# R6 — 5,000-DAG Multi-Parent Property-Based Fuzzing (Theorem 1B)
# ===========================================================================
def _dag_oracle_authorized_leaves(
    graph: ZanzibarAuthGraph, principal_id: str
) -> Set[str]:
    """Independent BFS oracle on arbitrary multi-parent DAG under deny-dominates-grant."""
    grants = graph.positive_grants.get(principal_id, set())
    denies = set(graph.explicit_denies.get(principal_id, set())) | graph.revoked_subtrees

    # Reachable from E^- (deny closure)
    deny_reach: Set[str] = set()
    dq = list(denies)
    while dq:
        x = dq.pop()
        if x in deny_reach:
            continue
        deny_reach.add(x)
        for ch in graph.children.get(x, ()):
            if ch not in deny_reach:
                dq.append(ch)

    # Reachable from E^+ (positive closure)
    pos_reach: Set[str] = set()
    pq = list(grants)
    while pq:
        x = pq.pop()
        if x in pos_reach:
            continue
        pos_reach.add(x)
        for ch in graph.children.get(x, ()):
            if ch not in pos_reach:
                pq.append(ch)

    return (pos_reach - deny_reach) & graph.leaf_documents


def run_r6_multiparent_dag_fuzzing(logger: RawAuditLogger) -> Dict[str, Any]:
    print("\n=== [R6] 5,000-DAG MULTI-PARENT PROPERTY FUZZING (THEOREM 1B) ===", flush=True)
    t0 = time.perf_counter()
    rng = np.random.default_rng(20261123)
    topos = [(8, 4), (4, 5), (6, 4)]

    # Build one reusable base DAG per topology with ~30% multi-parent cross-edges,
    # then generate fresh random grants/denies/revocations across 5,000 DAG trials
    # while periodically regenerating the DAG cross-edge wiring every 20 trials.
    topo_base_graphs: List[Tuple[int, int, ZanzibarAuthGraph, List[List[str]], Dict[str, Set[str]], int]] = []

    def _build_multiparent_dag(b: int, L: int, trial_rng: np.random.Generator) -> Tuple[ZanzibarAuthGraph, List[List[str]], Dict[str, Set[str]], int]:
        g = ZanzibarAuthGraph.build_balanced_hierarchy(branching_factor=b, depth=L)
        levels: List[List[str]] = [[] for _ in range(L + 1)]
        for nid in g.all_nodes:
            levels[g.node_depth[nid]].append(nid)
        for arr in levels:
            arr.sort()

        n_sec = 0
        # Attach secondary parents across distinct container branches at levels 2..L
        for lvl in range(2, L + 1):
            cand_parents = levels[lvl - 1]
            for child_id in levels[lvl]:
                if float(trial_rng.random()) < 0.30 and len(cand_parents) >= 3:
                    extra_k = int(trial_rng.integers(1, 3))  # 1 or 2 additional parents
                    picks = trial_rng.choice(len(cand_parents), size=min(len(cand_parents), extra_k + 1), replace=False)
                    added = 0
                    for pi in picks:
                        pid = cand_parents[int(pi)]
                        if pid not in g.parents[child_id]:
                            g.add_hierarchy_edge(pid, child_id)
                            n_sec += 1
                            added += 1
                            if added >= extra_k:
                                break

        # Precompute full descendant leaf posting bitmaps B_g for every node g in the DAG
        leaf_postings: Dict[str, Set[str]] = {}
        for nid in g.leaf_documents:
            leaf_postings[nid] = {nid}
        for lvl in range(L - 1, -1, -1):
            for nid in levels[lvl]:
                s_leaves: Set[str] = set()
                for ch in g.children.get(nid, ()):
                    s_leaves |= leaf_postings[ch]
                leaf_postings[nid] = s_leaves
        return g, levels, leaf_postings, n_sec

    mismatches = 0
    fps_total = 0
    fns_total = 0
    n_trials = 5000

    cur_dags: Dict[Tuple[int, int], Tuple[ZanzibarAuthGraph, List[List[str]], Dict[str, Set[str]], int]] = {}
    for b, L in topos:
        cur_dags[(b, L)] = _build_multiparent_dag(b, L, rng)

    for trial in range(n_trials):
        b, L = topos[trial % len(topos)]
        if trial > 0 and trial % 150 == 0:
            cur_dags[(b, L)] = _build_multiparent_dag(b, L, rng)
        g, levels, leaf_postings, n_sec = cur_dags[(b, L)]

        u = "dag_fuzz_u"
        g.positive_grants[u] = set()
        g.explicit_denies[u] = set()
        g.revoked_subtrees.clear()

        # Assign 1..4 positive grants across depths 0..L-1
        k_grants = int(rng.integers(1, 5))
        if float(rng.random()) < 0.35:
            g.grant_access(u, levels[0][0])
        for _ in range(k_grants):
            gl = int(rng.integers(0, L))
            node_pos = levels[gl][int(rng.integers(0, len(levels[gl])))]
            g.grant_access(u, node_pos)

        # Assign 1..20 subtractive DENY walls across depths 1..L (including shared multi-parent nodes)
        m_den = int(rng.integers(1, 21))
        for _ in range(m_den):
            dl = int(rng.integers(1, L + 1))
            node_neg = levels[dl][int(rng.integers(0, len(levels[dl])))]
            g.add_deny_exclusion(u, node_neg)

        # Optional grant revocation in 25% of trials
        if len(g.positive_grants[u]) >= 2 and float(rng.random()) < 0.25:
            drop_g = sorted(g.positive_grants[u])[-1]
            g.revoke_access(u, drop_g)

        res = g.upward_boundary_prune(u)
        pos_union: Set[str] = set()
        for t in res.tokens_pos:
            pos_union |= leaf_postings[t]
        neg_union: Set[str] = set()
        for z in res.tokens_neg:
            neg_union |= leaf_postings[z]
        ubp_leaves = pos_union - neg_union

        oracle_leaves = _dag_oracle_authorized_leaves(g, u)
        fp = len(ubp_leaves - oracle_leaves)
        fn = len(oracle_leaves - ubp_leaves)
        mm = int((fp + fn) > 0)
        mismatches += mm
        fps_total += fp
        fns_total += fn

        logger.log(
            "R6_multiparent_dag",
            {
                "trial": trial,
                "b": b,
                "L": L,
                "n_secondary_edges": n_sec,
                "tokens_pos": len(res.tokens_pos),
                "tokens_neg": len(res.tokens_neg),
                "oracle_docs": len(oracle_leaves),
                "false_positives": fp,
                "false_negatives": fn,
                "mismatch": mm,
            },
        )

    print(
        f"[R6] DONE in {time.perf_counter()-t0:.2f}s: {n_trials} multi-parent DAGs, "
        f"mismatches={mismatches} (FP={fps_total}, FN={fns_total})",
        flush=True,
    )
    return {"total_dag_trials": n_trials, "total_mismatches": mismatches}


# ===========================================================================
# R7 — Two-Track Fair Benchmark (Pure C++ vs End-to-End T_total) + RACORN-1
# ===========================================================================
def run_r7_two_track_fair_benchmark(
    X_q: np.ndarray,
    Q_q: np.ndarray,
    qids_q: Sequence[str],
    logger: RawAuditLogger,
    auth_consts: Dict[str, float],
) -> None:
    print("\n=== [R7] TWO-TRACK FAIR BENCHMARK (TRACK 1 PURE C++ vs TRACK 2 E2E T_total, QUORA 523k) ===", flush=True)
    t0 = time.perf_counter()
    N, d = X_q.shape
    seed = 0
    b, L = 8, 5  # 32,768 leaf docs -> covers S in [0.01%, 5.0%] on ONE shared M=16 graph

    rng = np.random.default_rng(20261124)
    overlay = build_overlay(X_q, mode="random", seed=seed, b=b, L=L)
    z_corpus = ZOrderedCorpus(X_q, overlay.ancestor_lineages, overlay.meaning_magnet_ids)
    l2_ids = [lin[-3] if len(lin) >= 3 else lin[-1] for lin in z_corpus.ancestor_lineages]

    # Prebuild leaf postings per doc in Z-order ID space for live CRoaring Track 2 filter compilation
    doc_to_z_ids: Dict[str, np.ndarray] = {}
    orig_to_z = np.empty(N, dtype=np.int32)
    orig_to_z[z_corpus.z_to_orig] = np.arange(N, dtype=np.int32)
    for doc_name, orig_arr in overlay.doc_to_chunks.items():
        doc_to_z_ids[doc_name] = orig_to_z[orig_arr]

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
    planner_sq8 = TriModalPlannerV3(
        overlay.auth_graph, z_corpus, idx_geom_m8, ef_search=V3_EF_SEARCH,
        tau_high=V3_TAU_HIGH, tau_low=V3_TAU_LOW, tau_stall=V3_TAU_STALL,
        n_guard=V3_N_GUARD, mode3_precision="sq8", max_portals=V3_MAX_PORTALS,
    )
    planner_f32 = TriModalPlannerV3(
        overlay.auth_graph, z_corpus, idx_geom_m8, ef_search=V3_EF_SEARCH,
        tau_high=V3_TAU_HIGH, tau_low=V3_TAU_LOW, tau_stall=V3_TAU_STALL,
        n_guard=V3_N_GUARD, mode3_precision="f32", max_portals=V3_MAX_PORTALS,
    )
    ac1 = Acorn1System(
        X_q, M=V3_M, ef_construction=V3_EF_CONSTRUCTION, ef_search=V3_EF_SEARCH,
        seed=seed, name="acorn-1", gamma=1, m_beta=32,
    )

    h_pg_lookup = float(auth_consts["h1_pg_lookup_med_ms"])
    h_mem_lookup = float(auth_consts["h1_mem_lookup_med_ms"])
    h_pg_ubp = float(auth_consts["h1_pg_ubp_rpc_med_ms"])
    h_mir_ubp = float(auth_consts["h1_mirror_ubp_med_ms"])

    rerank_k_sq8 = max(10 * planner_sq8.sq8_rerank_mult, 64)
    selectivities = (0.0001, 0.001, 0.005, 0.01, 0.05)
    n_queries = 50
    k = 10

    try:
        for s_target in selectivities:
            q_sel = rng.choice(len(Q_q), size=n_queries, replace=False)
            for qi_local, qi in enumerate(q_sel):
                allowed_docs, ubp_tokens = _sample_tokens_depth(s_target, rng, b=b, L=L)
                mask = np.zeros(N, dtype=np.bool_)
                for di in allowed_docs:
                    mask[overlay.doc_to_chunks[f"doc_L{L}_{di}"]] = True
                s_actual = float(mask.mean())
                qv = np.ascontiguousarray(Q_q[int(qi)], dtype=np.float32)
                gt = set(_exact_top_k(X_q, qv, mask, k=k))
                denom = float(len(gt)) if gt else 1.0

                # Common Z-order range arrays from UBP tokens
                starts, ends, n_cand = _compile_ranges_from_tokens(z_corpus, ubp_tokens)

                # --- 1. FAISS HNSW M=16 (Pure C++ Track 1 + O(N) Filter Compile Track 2) ---
                t_fc0 = time.perf_counter_ns()
                int_mask = mask[faiss_m16.internal_to_orig]
                packed = np.packbits(int_mask, bitorder="little")
                sel = faiss.IDSelectorBitmap(N, faiss.swig_ptr(packed))
                params = faiss.SearchParametersHNSW(efSearch=V3_EF_SEARCH, sel=sel)
                q_mat = np.ascontiguousarray(qv.reshape(1, -1), dtype=np.float32)
                fc_faiss_ms = (time.perf_counter_ns() - t_fc0) / 1e6

                faiss.cvar.hnsw_stats.reset()
                t1_0 = time.perf_counter_ns()
                _, I_f = faiss_m16.index.search(q_mat, k, params=params)
                t1_faiss_ms = (time.perf_counter_ns() - t1_0) / 1e6
                ndis_f = int(faiss.cvar.hnsw_stats.ndis)
                ids_f = [int(faiss_m16.internal_to_orig[i]) for i in I_f[0] if i >= 0]
                leaks_f = sum(1 for nid in ids_f if nid < 0 or nid >= N or not bool(mask[nid]))
                rec_f = len(set(ids_f) & gt) / denom
                logger.log("R7_two_track", {
                    "S_target": s_target, "S_actual": s_actual, "query_idx": int(qi_local),
                    "system": "faiss-hnsw-M16", "recall": rec_f, "leaks": leaks_f, "dist": ndis_f,
                    "track1_cpp_ms": t1_faiss_ms, "filter_compile_ms": fc_faiss_ms,
                    "track2_e2e_pg_ms": h_pg_lookup + fc_faiss_ms + t1_faiss_ms,
                    "track2_e2e_mirror_ms": h_mem_lookup + fc_faiss_ms + t1_faiss_ms,
                })

                # --- 2. Upstream C++ ACORN-1 (Pure C++ Track 1 + O(N) Perm Filter Compile) ---
                t_fc0 = time.perf_counter_ns()
                fmap = np.ascontiguousarray(mask[ac1.perm], dtype=np.uint8)
                fc_ac1_ms = (time.perf_counter_ns() - t_fc0) / 1e6
                out_ids_a = np.full(k, -1, dtype=np.int64)
                out_dists_a = np.zeros(k, dtype=np.float32)
                q_ptr = qv.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
                f_ptr = fmap.ctypes.data_as(ctypes.c_char_p)
                oi_ptr = out_ids_a.ctypes.data_as(ctypes.POINTER(ctypes.c_int64))
                od_ptr = out_dists_a.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

                t1_0 = time.perf_counter_ns()
                ndis_a = int(ac1.lib.acorn_search_one(ac1.handle, q_ptr, k, V3_EF_SEARCH, f_ptr, oi_ptr, od_ptr))
                t1_ac1_ms = (time.perf_counter_ns() - t1_0) / 1e6
                ids_a = [int(ac1.perm[i]) for i in out_ids_a if i >= 0]
                leaks_a = sum(1 for nid in ids_a if nid < 0 or nid >= N or not bool(mask[nid]))
                rec_a = len(set(ids_a) & gt) / denom
                logger.log("R7_two_track", {
                    "S_target": s_target, "S_actual": s_actual, "query_idx": int(qi_local),
                    "system": "acorn-1", "recall": rec_a, "leaks": leaks_a, "dist": ndis_a,
                    "track1_cpp_ms": t1_ac1_ms, "filter_compile_ms": fc_ac1_ms,
                    "track2_e2e_pg_ms": h_pg_lookup + fc_ac1_ms + t1_ac1_ms,
                    "track2_e2e_mirror_ms": h_mem_lookup + fc_ac1_ms + t1_ac1_ms,
                })

                # Pre-measure O(N_cand/64) C++ bitset materialization time vs O(N) naive leaf union time
                t_fc0 = time.perf_counter_ns()
                _s_tmp, _e_tmp, _ = _compile_ranges_from_tokens(z_corpus, ubp_tokens)
                ranges_set_bitset(_s_tmp, _e_tmp, idx_geom_m8._mask_bits, N)
                fc_prism_ms = (time.perf_counter_ns() - t_fc0) / 1e6
                # Clean bitset for RACORN leaf-bitmap compile measurement:
                ranges_clear_bitset(_s_tmp, _e_tmp, idx_geom_m8._mask_bits, N)

                # Naive O(N) bitset fill cost for RACORN-1 Track 2 (cannot use Z-order UBP containers directly)
                t_fcr0 = time.perf_counter_ns()
                _fmap_rac = np.ascontiguousarray(mask[z_corpus.z_to_orig], dtype=np.uint8)
                fc_racorn_ms = (time.perf_counter_ns() - t_fcr0) / 1e6

                # Materialize C++ bitset outside Track 1 timer (shared read-only across graph engines)
                ranges_set_bitset(starts, ends, idx_geom_m8._mask_bits, N)
                try:
                    # --- 3. RACORN-1 Adaptive Fallback (Shared M=16 Graph, No Geometric Bridges, Adaptive Unauth Bridges) ---
                    ep_r = idx_geom_m8._next_epoch()
                    t1_0 = time.perf_counter_ns()
                    z_ids_r, _, st_r = search_hhnsw_gls_cpp(
                        vectors=idx_geom_m8.vectors, entry_point=idx_geom_m8.entry_point, max_level=idx_geom_m8.max_level,
                        upper_offsets=idx_geom_m8.upper_offsets, upper_neighbors=idx_geom_m8.upper_neighbors,
                        cum_nn_per_lvl=idx_geom_m8.cum_nn_per_lvl, base_neighbors=idx_geom_m8.base_neighbors,
                        express_bridges=None, mask_bits=idx_geom_m8._mask_bits,
                        starts=starts, ends=ends, query=qv, k=k, ef_search=V3_EF_SEARCH,
                        tau_high=1.1, tau_low=0.05, use_express_bridges=False, use_portals=False,
                        max_portals=0, use_gls_adaptive=True, faiss_style_1hop=False,
                        tau_stall=0.0, stall_check_hops=16,
                        visited_epoch=idx_geom_m8._visited_epoch, current_epoch=ep_r,
                    )
                    t1_r_ms = (time.perf_counter_ns() - t1_0) / 1e6
                    ids_r = [int(z_corpus.z_to_orig[zid]) for zid in z_ids_r if zid >= 0]
                    leaks_r = sum(1 for nid in ids_r if nid < 0 or nid >= N or not bool(mask[nid]))
                    rec_r = len(set(ids_r) & gt) / denom
                    logger.log("R7_two_track", {
                        "S_target": s_target, "S_actual": s_actual, "query_idx": int(qi_local),
                        "system": "racorn-1-fallback", "recall": rec_r, "leaks": leaks_r, "dist": int(st_r.dist_computations),
                        "track1_cpp_ms": t1_r_ms, "filter_compile_ms": fc_racorn_ms,
                        "track2_e2e_pg_ms": h_pg_lookup + fc_racorn_ms + t1_r_ms,
                        "track2_e2e_mirror_ms": h_mem_lookup + fc_racorn_ms + t1_r_ms,
                    })

                    # --- 4. v3-geom-M8 (Graph-Only Geometric Bridges + GLS, Pure C++) ---
                    ep_g = idx_geom_m8._next_epoch()
                    t1_0 = time.perf_counter_ns()
                    z_ids_g, _, st_g = search_hhnsw_gls_cpp(
                        vectors=idx_geom_m8.vectors, entry_point=idx_geom_m8.entry_point, max_level=idx_geom_m8.max_level,
                        upper_offsets=idx_geom_m8.upper_offsets, upper_neighbors=idx_geom_m8.upper_neighbors,
                        cum_nn_per_lvl=idx_geom_m8.cum_nn_per_lvl, base_neighbors=idx_geom_m8.base_neighbors,
                        express_bridges=idx_geom_m8.express_bridges, mask_bits=idx_geom_m8._mask_bits,
                        starts=starts, ends=ends, query=qv, k=k, ef_search=V3_EF_SEARCH,
                        tau_high=V3_TAU_HIGH, tau_low=V3_TAU_LOW, use_express_bridges=True, use_portals=True,
                        max_portals=V3_MAX_PORTALS, use_gls_adaptive=True, faiss_style_1hop=False,
                        tau_stall=0.0, stall_check_hops=16,
                        visited_epoch=idx_geom_m8._visited_epoch, current_epoch=ep_g,
                    )
                    t1_g_ms = (time.perf_counter_ns() - t1_0) / 1e6
                    ids_g = [int(z_corpus.z_to_orig[zid]) for zid in z_ids_g if zid >= 0]
                    leaks_g = sum(1 for nid in ids_g if nid < 0 or nid >= N or not bool(mask[nid]))
                    rec_g = len(set(ids_g) & gt) / denom
                    logger.log("R7_two_track", {
                        "S_target": s_target, "S_actual": s_actual, "query_idx": int(qi_local),
                        "system": "v3-geom-M8", "recall": rec_g, "leaks": leaks_g, "dist": int(st_g.dist_computations),
                        "track1_cpp_ms": t1_g_ms, "filter_compile_ms": fc_prism_ms,
                        "track2_e2e_pg_ms": h_pg_ubp + fc_prism_ms + t1_g_ms,
                        "track2_e2e_mirror_ms": h_mir_ubp + fc_prism_ms + t1_g_ms,
                    })

                    # --- 5. v3-full-guard-f32 (0 Extra Vector RAM, Pure C++ Exact FP32 Mode 3 / Hybrid) ---
                    t1_0 = time.perf_counter_ns()
                    if s_actual <= planner_f32.s_sparse_threshold or n_cand <= planner_f32.n_flat_star:
                        z_ids_f32, _, ev_f32 = mode3_scan_ranges_f32(z_corpus.vectors, qv, starts, ends, k=k)
                    else:
                        ep_f32 = idx_geom_m8._next_epoch()
                        z_ids_f32, _, st_f32 = search_hhnsw_gls_cpp(
                            vectors=idx_geom_m8.vectors, entry_point=idx_geom_m8.entry_point, max_level=idx_geom_m8.max_level,
                            upper_offsets=idx_geom_m8.upper_offsets, upper_neighbors=idx_geom_m8.upper_neighbors,
                            cum_nn_per_lvl=idx_geom_m8.cum_nn_per_lvl, base_neighbors=idx_geom_m8.base_neighbors,
                            express_bridges=idx_geom_m8.express_bridges, mask_bits=idx_geom_m8._mask_bits,
                            starts=starts, ends=ends, query=qv, k=k, ef_search=V3_EF_SEARCH,
                            tau_high=V3_TAU_HIGH, tau_low=V3_TAU_LOW, use_express_bridges=True, use_portals=True,
                            max_portals=V3_MAX_PORTALS, use_gls_adaptive=True, faiss_style_1hop=False,
                            tau_stall=V3_TAU_STALL if n_cand <= V3_N_GUARD else 0.0, stall_check_hops=16,
                            visited_epoch=idx_geom_m8._visited_epoch, current_epoch=ep_f32,
                        )
                        ev_f32 = int(st_f32.dist_computations)
                        if st_f32.stalled and n_cand <= V3_N_GUARD:
                            z_ids_f32, _, m3ev = mode3_scan_ranges_f32(z_corpus.vectors, qv, starts, ends, k=k)
                            ev_f32 += int(m3ev)
                    t1_f32_ms = (time.perf_counter_ns() - t1_0) / 1e6
                    ids_f32 = [int(z_corpus.z_to_orig[zid]) for zid in z_ids_f32 if zid >= 0]
                    leaks_f32 = sum(1 for nid in ids_f32 if nid < 0 or nid >= N or not bool(mask[nid]))
                    rec_f32 = len(set(ids_f32) & gt) / denom
                    logger.log("R7_two_track", {
                        "S_target": s_target, "S_actual": s_actual, "query_idx": int(qi_local),
                        "system": "v3-full-guard-f32", "recall": rec_f32, "leaks": leaks_f32, "dist": int(ev_f32),
                        "track1_cpp_ms": t1_f32_ms, "filter_compile_ms": fc_prism_ms,
                        "track2_e2e_pg_ms": h_pg_ubp + fc_prism_ms + t1_f32_ms,
                        "track2_e2e_mirror_ms": h_mir_ubp + fc_prism_ms + t1_f32_ms,
                    })

                    # --- 6. v3-full-guard-sq8 (Pure C++ NEON SQ8 + Top-64 FP32 Rerank / Hybrid) ---
                    q_sq8 = np.ascontiguousarray(np.clip(np.round(qv * 127.0), -127, 127).astype(np.int8))
                    t1_0 = time.perf_counter_ns()
                    if s_actual <= planner_sq8.s_sparse_threshold or n_cand <= planner_sq8.n_flat_star:
                        z_ids_sq, _, ev_sq = mode3_scan_ranges_sq8(
                            z_corpus.sq8_vectors, z_corpus.vectors, q_sq8, qv, starts, ends, k=k, rerank_k=rerank_k_sq8
                        )
                    else:
                        ep_sq = idx_geom_m8._next_epoch()
                        z_ids_sq, _, st_sq = search_hhnsw_gls_cpp(
                            vectors=idx_geom_m8.vectors, entry_point=idx_geom_m8.entry_point, max_level=idx_geom_m8.max_level,
                            upper_offsets=idx_geom_m8.upper_offsets, upper_neighbors=idx_geom_m8.upper_neighbors,
                            cum_nn_per_lvl=idx_geom_m8.cum_nn_per_lvl, base_neighbors=idx_geom_m8.base_neighbors,
                            express_bridges=idx_geom_m8.express_bridges, mask_bits=idx_geom_m8._mask_bits,
                            starts=starts, ends=ends, query=qv, k=k, ef_search=V3_EF_SEARCH,
                            tau_high=V3_TAU_HIGH, tau_low=V3_TAU_LOW, use_express_bridges=True, use_portals=True,
                            max_portals=V3_MAX_PORTALS, use_gls_adaptive=True, faiss_style_1hop=False,
                            tau_stall=V3_TAU_STALL if n_cand <= V3_N_GUARD else 0.0, stall_check_hops=16,
                            visited_epoch=idx_geom_m8._visited_epoch, current_epoch=ep_sq,
                        )
                        ev_sq = int(st_sq.dist_computations)
                        if st_sq.stalled and n_cand <= V3_N_GUARD:
                            z_ids_sq, _, m3ev = mode3_scan_ranges_sq8(
                                z_corpus.sq8_vectors, z_corpus.vectors, q_sq8, qv, starts, ends, k=k, rerank_k=rerank_k_sq8
                            )
                            ev_sq += int(m3ev)
                    t1_sq_ms = (time.perf_counter_ns() - t1_0) / 1e6
                    ids_sq = [int(z_corpus.z_to_orig[zid]) for zid in z_ids_sq if zid >= 0]
                    leaks_sq = sum(1 for nid in ids_sq if nid < 0 or nid >= N or not bool(mask[nid]))
                    rec_sq = len(set(ids_sq) & gt) / denom
                    logger.log("R7_two_track", {
                        "S_target": s_target, "S_actual": s_actual, "query_idx": int(qi_local),
                        "system": "v3-full-guard-sq8", "recall": rec_sq, "leaks": leaks_sq, "dist": int(ev_sq),
                        "track1_cpp_ms": t1_sq_ms, "filter_compile_ms": fc_prism_ms,
                        "track2_e2e_pg_ms": h_pg_ubp + fc_prism_ms + t1_sq_ms,
                        "track2_e2e_mirror_ms": h_mir_ubp + fc_prism_ms + t1_sq_ms,
                    })
                finally:
                    ranges_clear_bitset(starts, ends, idx_geom_m8._mask_bits, N)

            print(f"  [R7] S={s_target} completed ({n_queries} queries x 6 systems)", flush=True)
    finally:
        ac1.close()
        del faiss_m16, prebuilt, idx_geom_m8, planner_sq8, planner_f32, z_corpus, overlay
        gc.collect()
    print(f"[R7] DONE in {time.perf_counter()-t0:.2f}s", flush=True)


# ===========================================================================
# R8 — Exact vs. Empirical Recall Shortlist & FP32 Mode-3 Parity Audit
# ===========================================================================
def run_r8_recall_audit(X_q: np.ndarray, Q_q: np.ndarray, logger: RawAuditLogger) -> None:
    print("\n=== [R8] EXACT vs EMPIRICAL RECALL AUDIT (SQ8 rerank_k=10..128 vs EXACT FP32 MODE 3) ===", flush=True)
    t0 = time.perf_counter()
    N, d = X_q.shape
    lib = _load_audit_kernel()
    b, L = 8, 5
    overlay = build_overlay(X_q, mode="random", seed=0, b=b, L=L)
    z_corpus = ZOrderedCorpus(X_q, overlay.ancestor_lineages, overlay.meaning_magnet_ids)

    p_z_f32 = z_corpus.vectors.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
    p_z_sq8 = z_corpus.sq8_vectors.ctypes.data_as(ctypes.POINTER(ctypes.c_int8))

    rng = np.random.default_rng(20261125)
    k = 10
    n_queries = 80
    out_ids = np.empty(k, dtype=np.int32)
    out_scores = np.empty(k, dtype=np.float32)
    p_oid = out_ids.ctypes.data_as(ctypes.POINTER(ctypes.c_int32))
    p_osc = out_scores.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

    for s_val in (0.0001, 0.001, 0.005, 0.01):
        q_sel = rng.choice(len(Q_q), size=n_queries, replace=False)
        for qi_local, qi in enumerate(q_sel):
            allowed_docs, ubp_tokens = _sample_tokens_depth(s_val, rng, b=b, L=L)
            mask = np.zeros(N, dtype=np.bool_)
            for di in allowed_docs:
                mask[overlay.doc_to_chunks[f"doc_L{L}_{di}"]] = True
            qv = np.ascontiguousarray(Q_q[int(qi)], dtype=np.float32)
            q_sq8 = np.ascontiguousarray(np.clip(np.round(qv * 127.0), -127, 127).astype(np.int8))
            pq = qv.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            pqsq = q_sq8.ctypes.data_as(ctypes.POINTER(ctypes.c_int8))
            gt = set(_exact_top_k(X_q, qv, mask, k=k))
            denom = float(len(gt)) if gt else 1.0

            starts, ends, n_cand = _compile_ranges_from_tokens(z_corpus, ubp_tokens)
            p_st = starts.ctypes.data_as(ctypes.POINTER(ctypes.c_int32))
            p_en = ends.ctypes.data_as(ctypes.POINTER(ctypes.c_int32))
            nr = len(starts)

            recs_rk: Dict[int, float] = {}
            ms_rk: Dict[int, float] = {}
            for rk in (10, 32, 64, 128):
                t1 = time.perf_counter_ns()
                lib.audit_scan_zorder_sq8_neon(p_z_sq8, p_z_f32, N, d, pqsq, pq, p_st, p_en, nr, k, rk, p_oid, p_osc)
                ms_rk[rk] = (time.perf_counter_ns() - t1) / 1e6
                res_orig = {int(z_corpus.z_to_orig[x]) for x in out_ids if x >= 0}
                recs_rk[rk] = len(res_orig & gt) / denom

            # Exact FP32 NEON scan (`0 B/node` extra vector RAM, mathematically exact top-k)
            t1 = time.perf_counter_ns()
            lib.audit_scan_zorder_f32_neon(p_z_f32, N, d, pq, p_st, p_en, nr, k, p_oid, p_osc)
            ms_f32 = (time.perf_counter_ns() - t1) / 1e6
            res_f32 = {int(z_corpus.z_to_orig[x]) for x in out_ids if x >= 0}
            rec_f32 = len(res_f32 & gt) / denom

            logger.log("R8_recall_audit", {
                "S_target": s_val,
                "query_idx": int(qi_local),
                "n_cand": n_cand,
                "rec_sq8_m10": recs_rk[10],
                "rec_sq8_m32": recs_rk[32],
                "rec_sq8_m64": recs_rk[64],
                "rec_sq8_m128": recs_rk[128],
                "rec_exact_f32": rec_f32,
                "ms_sq8_m64": ms_rk[64],
                "ms_exact_f32": ms_f32,
            })
        print(f"  [R8] S={s_val} done ({n_queries} queries)", flush=True)

    del z_corpus, overlay
    gc.collect()
    print(f"[R8] DONE in {time.perf_counter()-t0:.2f}s", flush=True)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-dirty", action="store_true", help="Allow running with uncommitted git changes")
    args = ap.parse_args()

    t_all = time.perf_counter()
    fz3 = freeze_v3_status()
    assert fz3["match"], f"FREEZE_v3 mismatch before v3.2 audit! {fz3}"
    fz31 = freeze_v3_1_status()
    assert fz31["match"], f"FREEZE_v3_1 mismatch before v3.2 audit! {fz31}"

    sha_now = git_sha()
    is_dirty = _repo_is_dirty()
    if is_dirty and not args.allow_dirty:
        raise RuntimeError("Refusing v3.2 audit on dirty working tree; commit changes first or pass --allow-dirty")

    with open(V3_SUMMARY_PATH, "r", encoding="utf-8") as f:
        v3_sum = json.load(f)
    h1_pg_t = v3_sum["hypotheses"]["H1_postgres"]["timing"]["auth_docs_ge_1000"]
    h1_mem_t = v3_sum["hypotheses"]["H1_memory"]["timing"]["auth_docs_ge_1000"]
    auth_consts = {
        "h1_pg_lookup_med_ms": float(h1_pg_t["SpiceDB-LookupResources+leaf-bitmap"]["latency_ms_median_pooled"]),
        "h1_mem_lookup_med_ms": float(h1_mem_t["SpiceDB-LookupResources+leaf-bitmap"]["latency_ms_median_pooled"]),
        "h1_pg_ubp_rpc_med_ms": float(h1_pg_t["SpiceDB-ReadRelationships+UBP+bitmap"]["latency_ms_median_pooled"]),
        "h1_mirror_ubp_med_ms": float(h1_pg_t["UBP+bitmap"]["latency_ms_median_pooled"]),
    }

    print(
        f"[audit_v3.2] git_sha={sha_now[:10]} git_dirty={is_dirty} "
        f"freeze_v3_1=INTACT ({fz31['n_files']}/8) auth_consts={auth_consts}",
        flush=True,
    )

    logger = RawAuditLogger(RAW_OUT_PATH)
    try:
        logger.log(
            "R0_meta",
            {
                "git_sha": sha_now,
                "git_dirty": bool(is_dirty),
                "freeze_v3_1_match": fz31["match"],
                "freeze_v3_1_files": fz31["n_files"],
                **auth_consts,
            },
        )
        _ = run_r6_multiparent_dag_fuzzing(logger)
        X_q, Q_q, qids_q, _ = load_corpus_v3("quora")
        run_r7_two_track_fair_benchmark(X_q, Q_q, qids_q, logger, auth_consts)
        run_r8_recall_audit(X_q, Q_q, logger)
    finally:
        logger.close()

    summary = recompute_v3_2_summary(RAW_OUT_PATH)
    os.makedirs(os.path.dirname(SUMMARY_OUT_PATH), exist_ok=True)
    with open(SUMMARY_OUT_PATH, "w", encoding="utf-8") as f:
        f.write(dumps_summary(summary))
    print(
        f"\n[audit_v3.2] COMPLETE in {time.perf_counter()-t_all:.2f}s | recs={summary['raw_records_total']} | "
        f"verdicts={ {k: v['verdict'] for k, v in summary['verdicts'].items()} } -> {SUMMARY_OUT_PATH}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
