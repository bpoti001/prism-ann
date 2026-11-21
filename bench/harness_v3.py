#!/usr/bin/env python3
"""
Provenance Confirmatory Harness for Prism-ANN v3 (ADR-0004 & ADR-0005)
======================================================================
Single entrypoint for `experiments/v3/PROTOCOL_v3.md`:
  - Verifies all 7 SHA-256 hashes in `FREEZE_v3.md` (and clean git tree)
    before permitting `--run-type confirmatory`.
  - Runs H1v3 (memory & persistent PostgreSQL 17 SpiceDB), H2v3 (Quora 523k
    & BEIR NQ 250k), H3v3 (Quora 523k & BEIR NQ 250k), H4v3 (persistent
    PostgreSQL SpiceDB vs pgvector 0.8.7 UPDATE), and H5v3 (4-way portal
    ablation on Quora 523k).
  - Emits one per-query raw JSONL record to `results/v3/raw/*.jsonl` for
    every measurement; summary is computed exclusively by `bench/recompute_v3.py`.
"""

from __future__ import annotations

import argparse
import gc
import os
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import faiss
import numpy as np

from bench.dataset import build_overlay
from bench.dataset_v3 import load_corpus_v3
from bench.engines import PostgresPgvectorService, SpiceDBPostgresService, SpiceDBService
from bench.experiments import (
    H2_SELECTIVITIES,
    _build_h4_hierarchy,
    _build_roaring_postings,
    _compile_roaring_leaves,
    _compile_roaring_ubp,
    _exact_top_k,
    _ubp_to_leaf_docs,
)
from bench.harness import (
    QuerySpec,
    RawRecord,
    RawWriter,
    RunContext,
    git_dirty_paths,
    git_sha,
    run_condition,
    sha256_file,
)
from bench.run_v3_dev_exploratory import (
    CppMode3System,
    HHNSWV3GraphSystem,
    PrismV3FullSystem,
    _sample_h2_tokens_and_docs,
)
from bench.systems import (
    Acorn1System,
    ExactBruteForceSystem,
    FaissHNSWSystem,
    HnswlibSystem,
    PgvectorSystem,
)
from src.modules.prism_ann.trimodal_planner import ZOrderedCorpus
from src.modules.prism_ann.ubp_resolver import ZanzibarAuthGraph
from src.modules.prism_ann_v3.geometric_hhnsw import (
    GeometricBridgeConfig,
    GeometricHHNSW,
)
from src.modules.prism_ann_v3.trimodal_v3 import TriModalPlannerV3

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FREEZE_V3_PATH = os.path.join(REPO_ROOT, "FREEZE_v3.md")

# Frozen v3 hyperparameters (PROTOCOL_v3.md — locked after Phase 17 dev split)
V3_M = 16
V3_M_BRIDGE = 8
V3_EF_CONSTRUCTION = 64
V3_EF_SEARCH = 64
V3_TAU_HIGH = 0.55
V3_TAU_LOW = 0.02
V3_TAU_STALL = 0.04
V3_STALL_CHECK_HOPS = 16
V3_N_GUARD = 25_000
V3_MAX_PORTALS = 4
V3_MODE3_PRECISION = "sq8"


def read_freeze_v3_hashes(freeze_path: str = FREEZE_V3_PATH) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    with open(freeze_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2 and len(parts[0]) == 64:
                hashes[parts[1]] = parts[0]
    return hashes


def freeze_v3_status(
    repo_root: str = REPO_ROOT, freeze_path: str = FREEZE_V3_PATH
) -> Dict[str, Any]:
    expected = read_freeze_v3_hashes(freeze_path)
    mismatches = {}
    for rel, exp in sorted(expected.items()):
        p = os.path.join(repo_root, rel)
        cur = sha256_file(p) if os.path.exists(p) else "<missing>"
        if cur != exp:
            mismatches[rel] = {"expected": exp, "current": cur}
    return {
        "match": bool(expected) and not mismatches,
        "n_files": len(expected),
        "mismatches": mismatches,
    }


# ---------------------------------------------------------------------------
# H1v3 — Live SpiceDB Equivalence & Speedup (Memory AND Persistent Postgres)
# ---------------------------------------------------------------------------
def run_h1_v3(
    X: np.ndarray,
    seeds: Sequence[int],
    n_principals_mem: int,
    n_principals_pg: int,
    ctx_base: Dict[str, Any],
    writer: RawWriter,
) -> None:
    for backend, n_princ, hyp_name in (
        ("memory", n_principals_mem, "H1_memory"),
        ("postgres", n_principals_pg, "H1_postgres"),
    ):
        if n_princ <= 0:
            continue
        print(
            f"[{hyp_name}] starting: backend={backend} seeds={list(seeds)} "
            f"principals/seed={n_princ} N={len(X)}"
        )
        for seed in seeds:
            t_seed = time.perf_counter()
            rng = np.random.default_rng(1000 + seed * 97)
            overlay = build_overlay(X, mode="random", seed=seed, b=8, L=4)
            graph = overlay.auth_graph
            z_corpus = ZOrderedCorpus(X, overlay.ancestor_lineages, overlay.meaning_magnet_ids)
            postings = _build_roaring_postings(z_corpus)
            graph_live = ZanzibarAuthGraph.build_balanced_hierarchy(branching_factor=8, depth=4)

            l1_nodes = [f"node_L1_{i}" for i in range(8)]
            l2_nodes = [f"node_L2_{i}" for i in range(64)]
            l3_nodes = [f"node_L3_{i}" for i in range(512)]

            policies: List[Tuple[str, Set[str], Set[str]]] = []
            for idx in range(n_princ):
                pid = f"user_{backend}_s{seed}_{idx}"
                if idx % 2 == 0:
                    if idx % 6 == 0:
                        grants = {"node_L0_0"}
                    else:
                        k_l1 = int(rng.integers(2, 5))
                        grants = set(rng.choice(l1_nodes, size=k_l1, replace=False).tolist())
                else:
                    kind = int(rng.integers(0, 3))
                    if kind == 0:
                        grants = {str(rng.choice(l1_nodes))}
                    elif kind == 1:
                        grants = set(
                            rng.choice(l2_nodes, size=int(rng.integers(1, 5)), replace=False).tolist()
                        )
                    else:
                        grants = set(
                            rng.choice(l3_nodes, size=int(rng.integers(2, 9)), replace=False).tolist()
                        )

                m_denies = int(rng.integers(0, 21))
                desc = list(graph.get_descendants(grants) - grants)
                if m_denies > 0 and desc:
                    denies = set(
                        rng.choice(desc, size=min(m_denies, len(desc)), replace=False).tolist()
                    )
                else:
                    denies = set()

                for g in grants:
                    graph.grant_access(pid, g)
                for d in denies:
                    graph.add_deny_exclusion(pid, d)
                policies.append((pid, grants, denies))

            svc_cls = SpiceDBPostgresService if backend == "postgres" else SpiceDBService
            with svc_cls() as sp:
                sp.load_hierarchy(graph)
                for pid, grants, denies in policies:
                    sp.write_principal_policy(pid, grants, denies)
                zt = sp.last_zed_token
                _ = sp.lookup_resources_docs(policies[0][0], zed_token=zt)

                mismatches_seed = 0
                ge1000_count = 0
                for pid, grants, denies in policies:
                    t0 = time.perf_counter_ns()
                    sp_docs = sp.lookup_resources_docs(pid, zed_token=zt)
                    b_sp = _compile_roaring_leaves(postings, sp_docs)
                    wall_sp = time.perf_counter_ns() - t0

                    t0 = time.perf_counter_ns()
                    res = graph.upward_boundary_prune(pid)
                    b_ubp = _compile_roaring_ubp(postings, res.tokens_pos, res.tokens_neg)
                    wall_ubp = time.perf_counter_ns() - t0

                    t0 = time.perf_counter_ns()
                    g_live, d_live = sp.read_principal_grants_and_denies(pid, zed_token=zt)
                    graph_live.positive_grants[pid] = g_live
                    graph_live.explicit_denies[pid] = d_live
                    res_live = graph_live.upward_boundary_prune(pid)
                    b_strict = _compile_roaring_ubp(postings, res_live.tokens_pos, res_live.tokens_neg)
                    wall_strict = time.perf_counter_ns() - t0

                    ubp_docs = _ubp_to_leaf_docs(graph, res.tokens_pos, res.tokens_neg)
                    mism_docs = len(ubp_docs ^ sp_docs)
                    mism_chunks = len(b_ubp ^ b_sp)
                    mism_strict = len(b_strict ^ b_sp)
                    mismatches_seed += mism_docs + mism_chunks + mism_strict
                    within_bound = len(res.tokens_pos) <= res.theoretical_upper_bound
                    n_auth_docs = len(sp_docs)
                    if n_auth_docs >= 1000:
                        ge1000_count += 1

                    cond = {
                        "backend": backend,
                        "b": 8,
                        "L": 4,
                        "m_denies": len(denies),
                        "k0_grants": res.k0_grants,
                    }
                    base = dict(hypothesis=hyp_name, seed=int(seed), query_id=pid, condition=cond, **ctx_base)
                    writer.write(
                        RawRecord(
                            system="H1-oracle-check",
                            wall_ns=int(wall_ubp),
                            extra={
                                "mismatch_docs": int(mism_docs),
                                "mismatch_chunks": int(mism_chunks),
                                "mismatch_strict_chunks": int(mism_strict),
                                "within_bound": bool(within_bound),
                                "tokens_pos": int(len(res.tokens_pos)),
                                "tokens_neg": int(len(res.tokens_neg)),
                                "bound": int(res.theoretical_upper_bound),
                                "n_auth_docs": int(n_auth_docs),
                                "m_denies": int(len(denies)),
                                "k0_grants": int(res.k0_grants),
                            },
                            **base,
                        )
                    )
                    writer.write(
                        RawRecord(
                            system="UBP+bitmap",
                            wall_ns=int(wall_ubp),
                            extra={"n_auth_docs": int(n_auth_docs), "tokens_pos": int(len(res.tokens_pos))},
                            **base,
                        )
                    )
                    writer.write(
                        RawRecord(
                            system="SpiceDB-LookupResources+leaf-bitmap",
                            wall_ns=int(wall_sp),
                            extra={"n_auth_docs": int(n_auth_docs)},
                            **base,
                        )
                    )
                    writer.write(
                        RawRecord(
                            system="SpiceDB-ReadRelationships+UBP+bitmap",
                            wall_ns=int(wall_strict),
                            extra={"n_auth_docs": int(n_auth_docs), "tokens_pos": int(len(res_live.tokens_pos))},
                            **base,
                        )
                    )
            del z_corpus, postings, overlay
            gc.collect()
            print(
                f"[{hyp_name}] seed={seed} done in {time.perf_counter()-t_seed:.1f}s "
                f"(principals={len(policies)}, >=1000_docs={ge1000_count}, mismatches={mismatches_seed})"
            )


# ---------------------------------------------------------------------------
# H2v3 + H5v3 — Multi-Corpus Selectivity Sweep & 4-Way Portal Ablation
# ---------------------------------------------------------------------------
def run_h2_and_h5_v3(
    corpus_name: str,
    X: np.ndarray,
    Q: np.ndarray,
    qids: List[str],
    seeds: Sequence[int],
    n_queries: int,
    run_h5: bool,
    run_pgvector: bool,
    acorn_gamma_val: int,
    ctx_base: Dict[str, Any],
    writer: RawWriter,
) -> None:
    hyp_h2 = f"H2_{corpus_name}"
    hyp_h5 = f"H5_{corpus_name}"
    N = len(X)
    print(
        f"[{hyp_h2}] starting: corpus={corpus_name} N={N} Q_pool={len(Q)} "
        f"seeds={list(seeds)} n_queries={n_queries}/S run_h5={run_h5} pgvector={run_pgvector}"
    )

    for seed in seeds:
        t_seed = time.perf_counter()
        rng = np.random.default_rng(2000 + seed * 101 + (0 if corpus_name == "quora" else 5000))
        overlay = build_overlay(X, mode="random", seed=seed, b=8, L=4)
        doc_int_ids = np.array([int(d.split("_")[-1]) for d in overlay.leaf_doc_ids], dtype=np.int32)
        folder_int_ids = np.array([int(f.split("_")[-1]) for f in overlay.folder_ids], dtype=np.int32)

        workloads: Dict[float, List[QuerySpec]] = {}
        for S_target in H2_SELECTIVITIES:
            q_sel = rng.choice(len(Q), size=min(n_queries, len(Q)), replace=False)
            specs: List[QuerySpec] = []
            for qi_local, qi in enumerate(q_sel):
                allowed_docs, ubp_tokens = _sample_h2_tokens_and_docs(S_target, rng)
                mask = np.zeros(N, dtype=np.bool_)
                for di in allowed_docs:
                    mask[overlay.doc_to_chunks[f"doc_L4_{di}"]] = True
                qv = Q[int(qi)]
                gt = _exact_top_k(X, qv, mask, k=10)
                specs.append(
                    QuerySpec(
                        query_id=f"{corpus_name}_S{S_target}_{qids[int(qi)]}_{qi_local}",
                        vector=qv,
                        mask=mask,
                        gt_ids=gt,
                        condition={
                            "corpus": corpus_name,
                            "S_target": float(S_target),
                            "S_actual": float(mask.mean()),
                        },
                        extra={"allowed_doc_ints": allowed_docs, "ubp_tokens": ubp_tokens},
                    )
                )
            workloads[S_target] = specs

        ctx_h2 = RunContext(hypothesis=hyp_h2, **ctx_base)
        ctx_h5 = RunContext(hypothesis=hyp_h5, **ctx_base)

        def _eval_s(sys_obj, ctx_obj: RunContext, also_ctx: Optional[RunContext] = None) -> None:
            for S_target in H2_SELECTIVITIES:
                t_s = time.perf_counter()
                recs = list(run_condition(sys_obj, workloads[S_target], k=10, seed=seed, ctx=ctx_obj))
                writer.write_all(recs)
                if also_ctx is not None:
                    for r in recs:
                        r_copy = RawRecord(
                            run_id=r.run_id,
                            run_type=r.run_type,
                            git_sha=r.git_sha,
                            freeze_match=r.freeze_match,
                            hypothesis=also_ctx.hypothesis,
                            system=r.system,
                            seed=r.seed,
                            query_id=r.query_id,
                            wall_ns=r.wall_ns,
                            condition=dict(r.condition),
                            distance_computations=r.distance_computations,
                            result_ids=list(r.result_ids),
                            gt_ids=list(r.gt_ids),
                            recall=r.recall,
                            extra=dict(r.extra),
                        )
                        writer.write(r_copy)
                print(
                    f"  [{ctx_obj.hypothesis}] seed={seed} S={S_target:<5} {sys_obj.name:<28}: "
                    f"{len(recs)} recs in {time.perf_counter()-t_s:.2f}s"
                )

        # 1. Exact BLAS brute-force ground truth
        _eval_s(ExactBruteForceSystem(X), ctx_h2)

        # 2. Shared Z-Order + FAISS M=16 base graph -> Prism v3, v2 ring-chord, and H5 4-way portal ablation
        z_corpus = ZOrderedCorpus(X, overlay.ancestor_lineages, overlay.meaning_magnet_ids)
        l2_ids = [lin[-3] if len(lin) >= 3 else lin[-1] for lin in z_corpus.ancestor_lineages]

        _eval_s(CppMode3System(z_corpus, precision="sq8", name="cpp-mode3-sq8"), ctx_h2)

        faiss_m16 = FaissHNSWSystem(
            z_corpus.vectors,
            M=V3_M,
            ef_construction=V3_EF_CONSTRUCTION,
            ef_search=V3_EF_SEARCH,
            seed=seed,
            name="faiss-hnsw-M16",
            ext_id_map=z_corpus.z_to_orig,
        )
        print(f"  [{hyp_h2}] seed={seed} faiss-hnsw-M16 build={faiss_m16.build_sec:.1f}s")
        _eval_s(faiss_m16, ctx_h2, also_ctx=ctx_h5 if run_h5 else None)
        prebuilt = (faiss_m16.index, faiss_m16.perm)

        # v2 ring-chord M_bridge=4 on exact same base graph
        idx_ring_m4 = GeometricHHNSW(
            z_corpus.vectors,
            z_corpus.primary_containers,
            l2_ids,
            z_corpus.meaning_magnet_ids,
            bridge_config=GeometricBridgeConfig.for_m_bridge(4, "ring_chord"),
            M=V3_M,
            seed=seed,
            prebuilt_faiss=prebuilt,
        )
        _eval_s(
            HHNSWV3GraphSystem(
                z_corpus, idx_ring_m4, "v2-ring-chord-M4",
                ef_search=V3_EF_SEARCH, tau_high=V3_TAU_HIGH, tau_low=V3_TAU_LOW,
                use_express_bridges=True, use_portals=True, max_portals=V3_MAX_PORTALS,
            ),
            ctx_h2,
        )
        del idx_ring_m4
        gc.collect()

        # v3 geometric M_bridge=8 on exact same base graph
        idx_geom_m8 = GeometricHHNSW(
            z_corpus.vectors,
            z_corpus.primary_containers,
            l2_ids,
            z_corpus.meaning_magnet_ids,
            bridge_config=GeometricBridgeConfig.for_m_bridge(V3_M_BRIDGE, "geometric"),
            M=V3_M,
            seed=seed,
            prebuilt_faiss=prebuilt,
        )
        print(
            f"  [{hyp_h2}] seed={seed} v3-geom-M8 bridges={idx_geom_m8.bridge_build_sec:.1f}s "
            f"ram={idx_geom_m8.memory_footprint_bytes()['total_bytes']/1e6:.1f}MB"
        )
        del faiss_m16, prebuilt
        gc.collect()

        _eval_s(
            HHNSWV3GraphSystem(
                z_corpus, idx_geom_m8, "v3-geom-M8",
                ef_search=V3_EF_SEARCH, tau_high=V3_TAU_HIGH, tau_low=V3_TAU_LOW,
                use_express_bridges=True, use_portals=True, max_portals=V3_MAX_PORTALS,
            ),
            ctx_h2,
            also_ctx=ctx_h5 if run_h5 else None,
        )

        if run_h5:
            _eval_s(
                HHNSWV3GraphSystem(
                    z_corpus, idx_geom_m8, "faiss-M16+4portals",
                    ef_search=V3_EF_SEARCH, use_express_bridges=False,
                    use_portals=True, max_portals=V3_MAX_PORTALS, faiss_style_1hop=True,
                ),
                ctx_h5,
            )
            _eval_s(
                HHNSWV3GraphSystem(
                    z_corpus, idx_geom_m8, "hhnsw-v2-geom-M8-noportal",
                    ef_search=V3_EF_SEARCH, tau_high=V3_TAU_HIGH, tau_low=V3_TAU_LOW,
                    use_express_bridges=True, use_portals=False,
                ),
                ctx_h5,
            )

        planner_v3 = TriModalPlannerV3(
            overlay.auth_graph,
            z_corpus,
            idx_geom_m8,
            ef_search=V3_EF_SEARCH,
            tau_high=V3_TAU_HIGH,
            tau_low=V3_TAU_LOW,
            tau_stall=V3_TAU_STALL,
            stall_check_hops=V3_STALL_CHECK_HOPS,
            n_guard=V3_N_GUARD,
            mode3_precision=V3_MODE3_PRECISION,
            max_portals=V3_MAX_PORTALS,
        )
        _eval_s(PrismV3FullSystem(z_corpus, planner_v3, "v3-full-guard-sq8"), ctx_h2)

        del z_corpus, idx_geom_m8, planner_v3
        gc.collect()

        # 3. Upstream C++ ACORN-1 (gamma=1, M_beta=32) & ACORN-gamma (gamma=4, M_beta=64)
        if Acorn1System.available():
            ac1 = Acorn1System(
                X, M=V3_M, ef_construction=V3_EF_CONSTRUCTION, ef_search=V3_EF_SEARCH,
                seed=seed, name="acorn-1", gamma=1, m_beta=32,
            )
            print(f"  [{hyp_h2}] seed={seed} acorn-1 build={ac1.build_sec:.1f}s")
            try:
                _eval_s(ac1, ctx_h2)
            finally:
                ac1.close()
                del ac1
                gc.collect()

            if acorn_gamma_val >= 2:
                acg = Acorn1System(
                    X, M=V3_M, ef_construction=V3_EF_CONSTRUCTION, ef_search=V3_EF_SEARCH,
                    seed=seed, name="acorn-gamma", gamma=acorn_gamma_val, m_beta=64,
                )
                print(
                    f"  [{hyp_h2}] seed={seed} acorn-gamma(g={acorn_gamma_val},Mb=64) "
                    f"build={acg.build_sec:.1f}s"
                )
                try:
                    _eval_s(acg, ctx_h2)
                finally:
                    acg.close()
                    del acg
                    gc.collect()

        # 4. Real hnswlib-M16
        hnsw_sys = HnswlibSystem(
            X, M=V3_M, ef_construction=V3_EF_CONSTRUCTION, ef_search=V3_EF_SEARCH,
            seed=seed, name="hnswlib-M16",
        )
        print(f"  [{hyp_h2}] seed={seed} hnswlib-M16 build={hnsw_sys.build_sec:.1f}s")
        _eval_s(hnsw_sys, ctx_h2)
        del hnsw_sys
        gc.collect()

        # 5. Real PostgreSQL 17 + pgvector 0.8.7 HNSW iterative_scan
        if run_pgvector:
            with PostgresPgvectorService() as pg:
                pg_order = np.random.default_rng(40_000 + seed * 151).permutation(N).astype(np.int32)
                t_pg = pg.load_vectors_table(
                    "h2_vecs", X, doc_int_ids, folder_int_ids,
                    insert_order=pg_order, m=V3_M, ef_construction=V3_EF_CONSTRUCTION, build_hnsw=True,
                )
                pg.configure_hnsw_session(ef_search=V3_EF_SEARCH)
                plan = pg.verify_uses_hnsw_index(
                    "h2_vecs", workloads[0.05][0].vector, workloads[0.05][0].extra["allowed_doc_ints"], k=10
                )
                assert "h2_vecs_vec_hnsw_idx" in plan, f"pgvector skipped HNSW index!\n{plan}"
                print(f"  [{hyp_h2}] seed={seed} pgvector build={t_pg:.1f}s (EXPLAIN HNSW verified)")
                _eval_s(PgvectorSystem(pg, "h2_vecs"), ctx_h2)

        del workloads, overlay
        gc.collect()
        print(f"[{hyp_h2}] seed={seed} total wall={time.perf_counter()-t_seed:.1f}s")


# ---------------------------------------------------------------------------
# H3v3 — Multi-Corpus Cluster-Aligned Correlation Study (S=2%, measured r)
# ---------------------------------------------------------------------------
def run_h3_v3(
    corpus_name: str,
    X: np.ndarray,
    Q: np.ndarray,
    qids: List[str],
    seeds: Sequence[int],
    n_queries: int,
    ctx_base: Dict[str, Any],
    writer: RawWriter,
) -> None:
    hyp_h3 = f"H3_{corpus_name}"
    N, d = X.shape
    ctx = RunContext(hypothesis=hyp_h3, **ctx_base)
    n_folders_target = 10  # 10 / 512 ~= 1.95% (~2%)
    print(f"[{hyp_h3}] starting: corpus={corpus_name} N={N} seeds={list(seeds)} n_queries={n_queries}")

    flat_ip = faiss.IndexFlatIP(d)
    flat_ip.add(np.ascontiguousarray(X, dtype=np.float32))

    for seed in seeds:
        t_seed = time.perf_counter()
        rng = np.random.default_rng(3000 + seed * 107 + (0 if corpus_name == "quora" else 7000))
        overlay = build_overlay(X, mode="cluster", seed=seed, b=8, L=4)

        q_sel = rng.choice(len(Q), size=min(n_queries, len(Q)), replace=False)
        Q_sub = np.ascontiguousarray(Q[q_sel], dtype=np.float32)
        _, top100_unf = flat_ip.search(Q_sub, 100)
        centroid_sims = Q_sub @ overlay.folder_centroids.T
        n_half = len(q_sel) // 2

        specs: List[QuerySpec] = []
        for qi_local, qi in enumerate(q_sel):
            order_f = np.argsort(-centroid_sims[qi_local])
            if qi_local < n_half:
                regime = "near"
                chosen_f = order_f[:n_folders_target].tolist()
            else:
                regime = "far"
                chosen_f = rng.choice(order_f[64:], size=n_folders_target, replace=False).tolist()

            mask = np.zeros(N, dtype=np.bool_)
            ubp_tokens: List[str] = []
            for fi in chosen_f:
                fid = overlay.folder_list[int(fi)]
                ubp_tokens.append(fid)
                mask[overlay.folder_to_chunks[fid]] = True

            s_actual = float(mask.mean())
            s_loc_100 = float(np.mean(mask[top100_unf[qi_local]]))
            r_measured = (s_loc_100 / s_actual) if s_actual > 0.0 else 0.0
            qv = Q[int(qi)]
            gt = _exact_top_k(X, qv, mask, k=10)
            specs.append(
                QuerySpec(
                    query_id=f"{corpus_name}_H3_{regime}_{qids[int(qi)]}_{qi_local}",
                    vector=qv,
                    mask=mask,
                    gt_ids=gt,
                    condition={
                        "corpus": corpus_name,
                        "S_target": 0.02,
                        "S_actual": s_actual,
                        "r_measured": float(r_measured),
                        "regime": regime,
                    },
                    extra={"s_loc_100": s_loc_100, "ubp_tokens": ubp_tokens},
                )
            )
        n_le05 = sum(1 for s in specs if s.condition["r_measured"] <= 0.5)
        n_ge20 = sum(1 for s in specs if s.condition["r_measured"] >= 2.0)
        print(f"[{hyp_h3}] seed={seed} queries built: r<=0.5={n_le05}, r>=2.0={n_ge20}")

        def _eval_h3(sys_obj) -> None:
            t_s = time.perf_counter()
            n_w = writer.write_all(run_condition(sys_obj, specs, k=10, seed=seed, ctx=ctx))
            print(f"  [{hyp_h3}] seed={seed} {sys_obj.name:<28}: {n_w} recs in {time.perf_counter()-t_s:.2f}s")

        _eval_h3(ExactBruteForceSystem(X))

        z_corpus = ZOrderedCorpus(X, overlay.ancestor_lineages, overlay.meaning_magnet_ids)
        l2_ids = [lin[-3] if len(lin) >= 3 else lin[-1] for lin in z_corpus.ancestor_lineages]

        faiss_m16 = FaissHNSWSystem(
            z_corpus.vectors, M=V3_M, ef_construction=V3_EF_CONSTRUCTION, ef_search=V3_EF_SEARCH,
            seed=seed, name="faiss-hnsw-M16", ext_id_map=z_corpus.z_to_orig,
        )
        _eval_h3(faiss_m16)
        prebuilt = (faiss_m16.index, faiss_m16.perm)

        idx_geom_m8 = GeometricHHNSW(
            z_corpus.vectors, z_corpus.primary_containers, l2_ids, z_corpus.meaning_magnet_ids,
            bridge_config=GeometricBridgeConfig.for_m_bridge(V3_M_BRIDGE, "geometric"),
            M=V3_M, seed=seed, prebuilt_faiss=prebuilt,
        )
        del faiss_m16, prebuilt
        gc.collect()

        _eval_h3(
            HHNSWV3GraphSystem(
                z_corpus, idx_geom_m8, "v3-geom-M8",
                ef_search=V3_EF_SEARCH, tau_high=V3_TAU_HIGH, tau_low=V3_TAU_LOW,
                use_express_bridges=True, use_portals=True, max_portals=V3_MAX_PORTALS,
                use_gls_adaptive=True,
            )
        )
        _eval_h3(
            HHNSWV3GraphSystem(
                z_corpus, idx_geom_m8, "v3-static-2hop",
                ef_search=V3_EF_SEARCH, tau_high=V3_TAU_HIGH, tau_low=V3_TAU_LOW,
                use_express_bridges=True, use_portals=True, max_portals=V3_MAX_PORTALS,
                use_gls_adaptive=False,
            )
        )
        planner_v3 = TriModalPlannerV3(
            overlay.auth_graph, z_corpus, idx_geom_m8, ef_search=V3_EF_SEARCH,
            tau_high=V3_TAU_HIGH, tau_low=V3_TAU_LOW, tau_stall=V3_TAU_STALL,
            stall_check_hops=V3_STALL_CHECK_HOPS, n_guard=V3_N_GUARD,
            mode3_precision=V3_MODE3_PRECISION, max_portals=V3_MAX_PORTALS,
        )
        _eval_h3(PrismV3FullSystem(z_corpus, planner_v3, "v3-full-guard-sq8"))

        del z_corpus, idx_geom_m8, planner_v3
        gc.collect()

        if Acorn1System.available():
            ac1 = Acorn1System(
                X, M=V3_M, ef_construction=V3_EF_CONSTRUCTION, ef_search=V3_EF_SEARCH,
                seed=seed, name="acorn-1", gamma=1, m_beta=32,
            )
            try:
                _eval_h3(ac1)
            finally:
                ac1.close()
                del ac1
                gc.collect()

        hnsw_sys = HnswlibSystem(
            X, M=V3_M, ef_construction=V3_EF_CONSTRUCTION, ef_search=V3_EF_SEARCH,
            seed=seed, name="hnswlib-M16",
        )
        _eval_h3(hnsw_sys)
        del hnsw_sys, specs, overlay
        gc.collect()
        print(f"[{hyp_h3}] seed={seed} total wall={time.perf_counter()-t_seed:.1f}s")

    del flat_ip
    gc.collect()


# ---------------------------------------------------------------------------
# H4v3 — Live Revocation (Persistent Postgres SpiceDB vs pgvector UPDATE)
# ---------------------------------------------------------------------------
def run_h4_v3(
    X_full: np.ndarray,
    n_trials: int,
    ctx_base: Dict[str, Any],
    writer: RawWriter,
) -> None:
    N = len(X_full)
    print(f"[H4_postgres] starting: trials={n_trials} N={N}")
    graph, lineages, doc_ints, folder_ints, docs_covered, chunks_covered = _build_h4_hierarchy(N)
    graph.grant_access("org_exec", "node_L0_0")
    z_corpus = ZOrderedCorpus(X_full, lineages, ["magnet_0"] * N)
    postings = _build_roaring_postings(z_corpus)

    with SpiceDBPostgresService() as sp, PostgresPgvectorService() as pg:
        sp.load_hierarchy(graph)
        sp.write_principal_policy("org_exec", grants={"node_L0_0"}, denies=set())

        t_pg = pg.load_vectors_table(
            "h4_vecs", X_full, doc_ints, folder_ints,
            m=V3_M, ef_construction=V3_EF_CONSTRUCTION, build_hnsw=True,
        )
        pg.conn.execute("CREATE INDEX h4_vecs_folder_idx ON h4_vecs (folder_id);")
        pg.conn.execute("ANALYZE h4_vecs;")
        print(
            f"[H4_postgres] loaded {N} rows into Postgres+pgvector HNSW in {t_pg:.1f}s; "
            f"revoking {docs_covered} docs / {chunks_covered} chunks"
        )

        cond = {"backend": "postgres", "docs_covered": int(docs_covered), "chunks_covered": int(chunks_covered)}
        for trial in range(n_trials):
            t0 = time.perf_counter_ns()
            zt_del = sp.delete_parent_edge("node_L0_0", "node_L1_0")
            graph.remove_hierarchy_edge("node_L0_0", "node_L1_0")
            res = graph.upward_boundary_prune("org_exec")
            b_ubp = _compile_roaring_ubp(postings, res.tokens_pos, res.tokens_neg)
            wall_p4a = time.perf_counter_ns() - t0

            if trial == 0:
                sp_after = sp.lookup_resources_docs("org_exec", zed_token=zt_del)
                ubp_after = _ubp_to_leaf_docs(graph, res.tokens_pos, res.tokens_neg)
                assert sp_after == ubp_after, f"H4 revocation mismatch: {len(sp_after ^ ubp_after)}"
                assert len(b_ubp) == N - chunks_covered

            if trial + 1 < n_trials:
                sp.restore_parent_edge("node_L0_0", "node_L1_0")
                graph.add_hierarchy_edge("node_L0_0", "node_L1_0")

            t0 = time.perf_counter_ns()
            rows_aff = pg.update_acl_for_folder("h4_vecs", folder_id=0, allowed=False)
            wall_p4b = time.perf_counter_ns() - t0
            assert rows_aff == chunks_covered

            if trial + 1 < n_trials:
                pg.update_acl_for_folder("h4_vecs", folder_id=0, allowed=True)
                pg.conn.execute("VACUUM h4_vecs;")

            base = dict(hypothesis="H4_postgres", seed=0, query_id=f"trial_{trial}", condition=cond, **ctx_base)
            writer.write(
                RawRecord(
                    system="P4a-path(SpiceDB-Postgres-Delete+mirror+UBP+bitmap)",
                    wall_ns=int(wall_p4a),
                    extra={"vector_writes": 0, "tokens_pos": int(len(res.tokens_pos))},
                    **base,
                )
            )
            writer.write(
                RawRecord(
                    system="pgvector-UPDATE-acl",
                    wall_ns=int(wall_p4b),
                    extra={"rows_affected": int(rows_aff), "vector_writes": int(rows_aff)},
                    **base,
                )
            )
            print(
                f"  [H4_postgres] trial={trial}: SpiceDB(PG)={wall_p4a/1e6:.2f}ms (0 writes) "
                f"vs pgvector UPDATE={wall_p4b/1e6:.2f}ms ({rows_aff} rows, {wall_p4b/wall_p4a:.1f}x)"
            )


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Prism-ANN v3 confirmatory harness (ADR-0005)")
    ap.add_argument("--run-type", choices=["smoke", "confirmatory", "exploratory"], required=True)
    ap.add_argument("--run-id", default="v3-confirmatory-001")
    ap.add_argument("--hypotheses", default="H1,H2_quora,H3_quora,H2_nq,H3_nq,H4")
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--n-queries", type=int, default=500)
    ap.add_argument("--h1-mem-principals", type=int, default=200)
    ap.add_argument("--h1-pg-principals", type=int, default=200)
    ap.add_argument("--h4-trials", type=int, default=5)
    ap.add_argument("--acorn-gamma", type=int, default=4)
    ap.add_argument("--pgvector-nq", action="store_true", help="Also run pgvector on Corpus 2 NQ")
    ap.add_argument("--raw-dir", default="")
    ap.add_argument("--allow-dirty", action="store_true")
    args = ap.parse_args(argv)

    fz3 = freeze_v3_status()
    dirty = git_dirty_paths()
    if args.run_type == "confirmatory":
        if not fz3["match"]:
            print(f"[harness_v3] REFUSING confirmatory run: FREEZE_v3.md mismatch: {fz3['mismatches']}")
            return 2
        if dirty:
            print(f"[harness_v3] REFUSING confirmatory run: uncommitted tracked changes: {dirty}")
            return 2
    elif dirty and not args.allow_dirty:
        print(f"[harness_v3] dirty tracked files {dirty}; pass --allow-dirty for smoke/exploratory")
        return 2

    raw_dir = args.raw_dir or os.path.join(
        REPO_ROOT, "results", "v3", "raw" if args.run_type == "confirmatory" else f"raw_{args.run_type}"
    )
    os.makedirs(raw_dir, exist_ok=True)
    sha = git_sha()
    ctx_base = dict(run_id=args.run_id, run_type=args.run_type, git_sha=sha, freeze_match=fz3["match"])
    print(
        f"[harness_v3] run_id={args.run_id} type={args.run_type} sha={sha[:10]} "
        f"freeze_v3={fz3['match']} ({fz3['n_files']}/7) raw_dir={raw_dir}"
    )

    hyps = [h.strip() for h in args.hypotheses.split(",") if h.strip()]
    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]

    t_all = time.perf_counter()
    writer = RawWriter(raw_dir, args.run_id)
    try:
        need_quora = any(h in hyps for h in ("H1", "H2_quora", "H3_quora", "H4"))
        if need_quora:
            X_q, Q_q, qids_q, meta_q = load_corpus_v3("quora")
            print(
                f"[harness_v3] loaded Quora: X={X_q.shape} Q_confirmatory={Q_q.shape} "
                f"(slice={meta_q['confirmatory_query_slice']})"
            )
            if "H1" in hyps:
                run_h1_v3(X_q, seeds, args.h1_mem_principals, args.h1_pg_principals, ctx_base, writer)
            if "H2_quora" in hyps:
                run_h2_and_h5_v3(
                    "quora", X_q, Q_q, qids_q, seeds, args.n_queries,
                    run_h5=True, run_pgvector=True, acorn_gamma_val=args.acorn_gamma,
                    ctx_base=ctx_base, writer=writer,
                )
            if "H3_quora" in hyps:
                run_h3_v3("quora", X_q, Q_q, qids_q, seeds, args.n_queries, ctx_base, writer)
            if "H4" in hyps:
                run_h4_v3(X_q, args.h4_trials, ctx_base, writer)
            del X_q, Q_q, qids_q
            gc.collect()

        need_nq = any(h in hyps for h in ("H2_nq", "H3_nq"))
        if need_nq:
            X_n, Q_n, qids_n, _ = load_corpus_v3("nq")
            print(f"[harness_v3] loaded BEIR NQ: X={X_n.shape} Q={Q_n.shape}")
            if "H2_nq" in hyps:
                run_h2_and_h5_v3(
                    "nq", X_n, Q_n, qids_n, seeds, args.n_queries,
                    run_h5=False, run_pgvector=args.pgvector_nq, acorn_gamma_val=args.acorn_gamma,
                    ctx_base=ctx_base, writer=writer,
                )
            if "H3_nq" in hyps:
                run_h3_v3("nq", X_n, Q_n, qids_n, seeds, args.n_queries, ctx_base, writer)
            del X_n, Q_n, qids_n
            gc.collect()
    finally:
        writer.close()

    print(
        f"[harness_v3] COMPLETE in {(time.perf_counter()-t_all)/60.0:.1f} min | "
        f"wrote {writer.count} raw records -> {raw_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
