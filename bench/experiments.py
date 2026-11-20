"""
Experiment runners H1v2..H4v2 for Prism-ANN v2 (ADR-0004, PROTOCOL_v2.md).
==========================================================================
Called exclusively by bench/harness.py.  Every single measurement is emitted
as a RawRecord through RawWriter; no summary numbers are ever hardcoded here.
"""

from __future__ import annotations

import gc
import time
from typing import Dict, List, Sequence, Set, Tuple

import faiss
import numpy as np
from pyroaring import BitMap

from bench.dataset import HierarchyOverlay, build_overlay, load_quora_embeddings
from bench.engines import PostgresPgvectorService, SpiceDBService
from bench.harness import QuerySpec, RawRecord, RawWriter, RunContext, run_condition
from bench.systems import (
    Acorn1System,
    ExactBruteForceSystem,
    FaissHNSWSystem,
    HnswlibSystem,
    PgvectorSystem,
    PrismFullSystem,
    PrismGraphOnlySystem,
    build_prism_bundle,
)
from src.modules.prism_ann.trimodal_planner import ZOrderedCorpus
from src.modules.prism_ann.ubp_resolver import ZanzibarAuthGraph

H2_SELECTIVITIES = (0.001, 0.005, 0.01, 0.05)


# ---------------------------------------------------------------------------
# CRoaring helpers (used symmetrically for UBP and SpiceDB leaf bitmap build)
# ---------------------------------------------------------------------------
def _build_roaring_postings(z_corpus: ZOrderedCorpus) -> Dict[str, BitMap]:
    postings: Dict[str, BitMap] = {}
    for tok, rbm in z_corpus.token_bitmaps.items():
        bm = BitMap()
        for s, e in rbm.runs:
            bm.add_range(s, e)
        bm.run_optimize()
        postings[tok] = bm
    return postings


def _compile_roaring_ubp(
    postings: Dict[str, BitMap], tokens_pos: Set[str], tokens_neg: Set[str]
) -> BitMap:
    pos_bms = [postings[t] for t in tokens_pos if t in postings]
    b_pos = BitMap.union(*pos_bms) if pos_bms else BitMap()
    if not tokens_neg:
        return b_pos
    neg_bms = [postings[z] for z in tokens_neg if z in postings]
    if not neg_bms:
        return b_pos
    return b_pos - BitMap.union(*neg_bms)


def _compile_roaring_leaves(postings: Dict[str, BitMap], leaf_docs: Set[str]) -> BitMap:
    leaf_bms = [postings[d] for d in leaf_docs if d in postings]
    return BitMap.union(*leaf_bms) if leaf_bms else BitMap()


def _ubp_to_leaf_docs(graph: ZanzibarAuthGraph, tokens_pos: Set[str], tokens_neg: Set[str]) -> Set[str]:
    pos_desc = graph.get_descendants(tokens_pos)
    neg_desc = graph.get_descendants(tokens_neg)
    return (pos_desc - neg_desc) & graph.leaf_documents


def _exact_top_k(X: np.ndarray, q_vec: np.ndarray, mask: np.ndarray, k: int = 10) -> List[int]:
    valid = np.flatnonzero(mask)
    if len(valid) == 0:
        return []
    sims = X[valid] @ q_vec
    if len(valid) <= k:
        order = np.argsort(-sims)
    else:
        part = np.argpartition(-sims, k)[:k]
        order = part[np.argsort(-sims[part])]
    return [int(valid[i]) for i in order[:k]]


# ---------------------------------------------------------------------------
# H1v2 — UBP exact equivalence vs real SpiceDB, bound, and latency
# ---------------------------------------------------------------------------
def run_h1(
    X: np.ndarray,
    seeds: Sequence[int],
    n_principals_per_seed: int,
    ctx_base: Dict[str, object],
    writer: RawWriter,
) -> None:
    print(f"[H1] starting: seeds={list(seeds)} principals/seed={n_principals_per_seed} N={len(X)}")
    for seed in seeds:
        t_seed = time.perf_counter()
        rng = np.random.default_rng(1000 + seed * 97)
        overlay = build_overlay(X, mode="random", seed=seed, b=8, L=4)
        graph = overlay.auth_graph
        z_corpus = ZOrderedCorpus(X, overlay.ancestor_lineages, overlay.meaning_magnet_ids)
        postings = _build_roaring_postings(z_corpus)

        # Fresh structural mirror for the strict ReadRelationships+UBP+bitmap path
        graph_live = ZanzibarAuthGraph.build_balanced_hierarchy(branching_factor=8, depth=4)

        l1_nodes = [f"node_L1_{i}" for i in range(8)]
        l2_nodes = [f"node_L2_{i}" for i in range(64)]
        l3_nodes = [f"node_L3_{i}" for i in range(512)]

        # Pre-generate principal policies (mix of broad >=1,000-doc and narrow principals, 0..20 denies)
        policies: List[Tuple[str, Set[str], Set[str]]] = []
        for idx in range(n_principals_per_seed):
            pid = f"user_s{seed}_{idx}"
            if idx % 2 == 0:
                # Broad principal: 2..4 L1 grants (1,024..2,048 docs) or root (4,096 docs)
                if idx % 6 == 0:
                    grants = {"node_L0_0"}
                else:
                    k_l1 = int(rng.integers(2, 5))
                    grants = set(rng.choice(l1_nodes, size=k_l1, replace=False).tolist())
            else:
                # Narrower principal: 1 L1 or 1..4 L2 / folder grants
                kind = int(rng.integers(0, 3))
                if kind == 0:
                    grants = {str(rng.choice(l1_nodes))}
                elif kind == 1:
                    grants = set(rng.choice(l2_nodes, size=int(rng.integers(1, 5)), replace=False).tolist())
                else:
                    grants = set(rng.choice(l3_nodes, size=int(rng.integers(2, 9)), replace=False).tolist())

            m_denies = int(rng.integers(0, 21))  # 0..20 inclusive (PROTOCOL_v2)
            desc = list(graph.get_descendants(grants) - grants)
            if m_denies > 0 and desc:
                n_pick = min(m_denies, len(desc))
                denies = set(rng.choice(desc, size=n_pick, replace=False).tolist())
            else:
                denies = set()

            for g in grants:
                graph.grant_access(pid, g)
            for d in denies:
                graph.add_deny_exclusion(pid, d)
            policies.append((pid, grants, denies))

        with SpiceDBService() as sp:
            sp.load_hierarchy(graph)
            for pid, grants, denies in policies:
                sp.write_principal_policy(pid, grants, denies)
            zt = sp.last_zed_token

            # Warmup one gRPC call (not recorded)
            _ = sp.lookup_resources_docs(policies[0][0], zed_token=zt)

            mismatches_seed = 0
            ge1000_count = 0
            for pid, grants, denies in policies:
                # 1. Real SpiceDB LookupResources + CRoaring leaf bitmap build
                t0 = time.perf_counter_ns()
                sp_docs = sp.lookup_resources_docs(pid, zed_token=zt)
                b_sp = _compile_roaring_leaves(postings, sp_docs)
                wall_sp = time.perf_counter_ns() - t0

                # 2. Local UBP + CRoaring bitmap build
                t0 = time.perf_counter_ns()
                res = graph.upward_boundary_prune(pid)
                b_ubp = _compile_roaring_ubp(postings, res.tokens_pos, res.tokens_neg)
                wall_ubp = time.perf_counter_ns() - t0

                # 3. Strict path: live SpiceDB ReadRelationships + UBP + CRoaring bitmap build
                t0 = time.perf_counter_ns()
                g_live, d_live = sp.read_principal_grants_and_denies(pid, zed_token=zt)
                graph_live.positive_grants[pid] = g_live
                graph_live.explicit_denies[pid] = d_live
                res_live = graph_live.upward_boundary_prune(pid)
                b_strict = _compile_roaring_ubp(postings, res_live.tokens_pos, res_live.tokens_neg)
                wall_strict = time.perf_counter_ns() - t0

                # Exact oracle equivalence verification
                ubp_docs = _ubp_to_leaf_docs(graph, res.tokens_pos, res.tokens_neg)
                mism_docs = len(ubp_docs ^ sp_docs)
                mism_chunks = len(b_ubp ^ b_sp)
                mism_strict = len(b_strict ^ b_sp)
                mismatches_seed += mism_docs + mism_chunks + mism_strict
                within_bound = len(res.tokens_pos) <= res.theoretical_upper_bound
                n_auth_docs = len(sp_docs)
                if n_auth_docs >= 1000:
                    ge1000_count += 1

                cond = {"b": 8, "L": 4, "m_denies": len(denies), "k0_grants": res.k0_grants}
                base = dict(hypothesis="H1", seed=int(seed), query_id=pid, condition=cond, **ctx_base)
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
        print(
            f"[H1] seed={seed} done in {time.perf_counter()-t_seed:.1f}s "
            f"(principals={len(policies)}, >=1000_docs={ge1000_count}, mismatches={mismatches_seed})"
        )


# ---------------------------------------------------------------------------
# H2v2 — Low-selectivity recall (random assignment, S in {0.1%, 0.5%, 1%, 5%})
# ---------------------------------------------------------------------------
def _sample_h2_allowed_docs(S_target: float, rng: np.random.Generator, b: int = 8, L: int = 4) -> List[int]:
    """
    Samples a Zanzibar-consistent document set matching S_target over 4,096 leaf docs
    (512 folders of 8 docs each), using container/folder grants + optional leaf denies.
    """
    n_docs = b ** L       # 4096
    n_folders = b ** (L - 1)  # 512
    target_docs = max(1, int(round(S_target * n_docs)))
    n_full_folders = target_docs // b
    rem = target_docs % b
    n_pick_folders = n_full_folders + (1 if rem > 0 else 0)
    chosen_folders = rng.choice(n_folders, size=n_pick_folders, replace=False)
    docs: List[int] = []
    for fi in chosen_folders[:n_full_folders]:
        base = int(fi) * b
        docs.extend(range(base, base + b))
    if rem > 0:
        # 1 folder grant minus (b - rem) leaf DENY rules
        base = int(chosen_folders[-1]) * b
        kept = rng.choice(np.arange(base, base + b), size=rem, replace=False)
        docs.extend(int(x) for x in kept)
    docs.sort()
    return docs


def run_h2(
    X: np.ndarray,
    Q: np.ndarray,
    qids: List[str],
    seeds: Sequence[int],
    n_queries: int,
    ctx_base: Dict[str, object],
    writer: RawWriter,
) -> None:
    print(f"[H2] starting: seeds={list(seeds)} n_queries={n_queries}/S N={len(X)}")
    N = len(X)
    for seed in seeds:
        t_seed = time.perf_counter()
        rng = np.random.default_rng(2000 + seed * 101)
        overlay = build_overlay(X, mode="random", seed=seed, b=8, L=4)
        doc_int_ids = np.array([int(d.split("_")[-1]) for d in overlay.leaf_doc_ids], dtype=np.int32)
        folder_int_ids = np.array([int(f.split("_")[-1]) for f in overlay.folder_ids], dtype=np.int32)

        # Build query workloads for all 4 selectivities once per seed
        workloads: Dict[float, List[QuerySpec]] = {}
        for S_target in H2_SELECTIVITIES:
            q_sel = rng.choice(len(Q), size=min(n_queries, len(Q)), replace=False)
            specs: List[QuerySpec] = []
            for qi_local, qi in enumerate(q_sel):
                allowed_docs = _sample_h2_allowed_docs(S_target, rng)
                chunks_parts = [overlay.doc_to_chunks[f"doc_L4_{di}"] for di in allowed_docs]
                mask = np.zeros(N, dtype=np.bool_)
                for part in chunks_parts:
                    mask[part] = True
                qv = Q[int(qi)]
                gt = _exact_top_k(X, qv, mask, k=10)
                specs.append(
                    QuerySpec(
                        query_id=f"S{S_target}_{qids[int(qi)]}_{qi_local}",
                        vector=qv,
                        mask=mask,
                        gt_ids=gt,
                        condition={"S_target": float(S_target), "S_actual": float(mask.mean())},
                        extra={"allowed_doc_ints": allowed_docs},
                    )
                )
            workloads[S_target] = specs

        ctx = RunContext(hypothesis="H2", **ctx_base)

        def _eval_all_s(sys_obj) -> None:
            for S_target in H2_SELECTIVITIES:
                t_s = time.perf_counter()
                n_w = writer.write_all(run_condition(sys_obj, workloads[S_target], k=10, seed=seed, ctx=ctx))
                print(f"  [H2] seed={seed} S={S_target} {sys_obj.name}: {n_w} recs in {time.perf_counter()-t_s:.2f}s")

        # Run each heavy index one at a time and free RAM to stay safely within 16 GB at N=522,931
        print(f"[H2] seed={seed} evaluating exact-brute-force (N={N})...")
        _eval_all_s(ExactBruteForceSystem(X))

        print(f"[H2] seed={seed} building & evaluating faiss-hnsw-M16...")
        faiss_m16 = FaissHNSWSystem(X, M=16, ef_construction=64, ef_search=64, seed=seed, name="faiss-hnsw-M16")
        print(f"  [H2] seed={seed} faiss-hnsw-M16 build={faiss_m16.build_sec:.1f}s")
        _eval_all_s(faiss_m16)
        del faiss_m16
        gc.collect()

        if Acorn1System.available():
            print(f"[H2] seed={seed} building & evaluating acorn-1...")
            acorn_sys = Acorn1System(X, M=16, ef_construction=64, ef_search=64, seed=seed, name="acorn-1")
            print(f"  [H2] seed={seed} acorn-1 build={acorn_sys.build_sec:.1f}s")
            try:
                _eval_all_s(acorn_sys)
            finally:
                acorn_sys.close()
                del acorn_sys
                gc.collect()

        print(f"[H2] seed={seed} building & evaluating hnswlib-M16...")
        hnsw_sys = HnswlibSystem(X, M=16, ef_construction=64, ef_search=64, seed=seed, name="hnswlib-M16")
        print(f"  [H2] seed={seed} hnswlib-M16 build={hnsw_sys.build_sec:.1f}s")
        _eval_all_s(hnsw_sys)
        del hnsw_sys
        gc.collect()

        print(f"[H2] seed={seed} building & evaluating Prism bundle (prism-graph-only, prism-full, faiss-hnsw-M8)...")
        z_corpus, hnsw_idx, planner, faiss_m8, prism_stats = build_prism_bundle(
            overlay.auth_graph, X, overlay.ancestor_lineages, overlay.meaning_magnet_ids,
            seed=seed, ef_construction=64, ef_search=64,
        )
        print(
            f"  [H2] seed={seed} prism build: z={prism_stats['z_order_sec']:.1f}s "
            f"faissM8={prism_stats['faiss_m8_sec']:.1f}s bridges={prism_stats['bridges_sec']:.1f}s "
            f"ram={prism_stats['prism_ram_bytes']/1e6:.1f}MB"
        )
        _eval_all_s(faiss_m8)
        _eval_all_s(PrismGraphOnlySystem(z_corpus, hnsw_idx, ef_search=64, use_gls_adaptive=True))
        _eval_all_s(PrismFullSystem(z_corpus, planner))
        del z_corpus, hnsw_idx, planner, faiss_m8
        gc.collect()

        # Run real PostgreSQL 17 + pgvector 0.8.7 HNSW iterative_scan=relaxed_order
        with PostgresPgvectorService() as pg:
            pg_order = np.random.default_rng(40_000 + seed * 151).permutation(N).astype(np.int32)
            t_pg = pg.load_vectors_table(
                "h2_vecs", X, doc_int_ids, folder_int_ids,
                insert_order=pg_order, m=16, ef_construction=64, build_hnsw=True,
            )
            pg.configure_hnsw_session(ef_search=64)
            plan = pg.verify_uses_hnsw_index(
                "h2_vecs", workloads[0.05][0].vector, workloads[0.05][0].extra["allowed_doc_ints"], k=10
            )
            print(f"[H2] seed={seed} pgvector build={t_pg:.1f}s | EXPLAIN uses h2_vecs_vec_hnsw_idx={('h2_vecs_vec_hnsw_idx' in plan)}")
            assert "h2_vecs_vec_hnsw_idx" in plan, f"pgvector did not use HNSW index! Plan:\n{plan}"
            _eval_all_s(PgvectorSystem(pg, "h2_vecs"))

        del workloads, overlay
        gc.collect()
        print(f"[H2] seed={seed} total wall={time.perf_counter()-t_seed:.1f}s")


# ---------------------------------------------------------------------------
# H3v2 — Correlation (cluster-aligned assignment, S=2%, measured r per query)
# ---------------------------------------------------------------------------
def run_h3(
    X: np.ndarray,
    Q: np.ndarray,
    qids: List[str],
    seeds: Sequence[int],
    n_queries: int,
    ctx_base: Dict[str, object],
    writer: RawWriter,
) -> None:
    print(f"[H3] starting: seeds={list(seeds)} n_queries={n_queries} (S=2%, cluster-aligned) N={len(X)}")
    N, d = X.shape
    ctx = RunContext(hypothesis="H3", **ctx_base)
    n_folders_target = 10  # 10 / 512 ~= 1.95% (~2% target selectivity)

    # Exact unfiltered index (shared across seeds for measuring per-query local selectivity r)
    flat_ip = faiss.IndexFlatIP(d)
    flat_ip.add(np.ascontiguousarray(X, dtype=np.float32))

    for seed in seeds:
        t_seed = time.perf_counter()
        rng = np.random.default_rng(3000 + seed * 107)
        overlay = build_overlay(X, mode="cluster", seed=seed, b=8, L=4)

        q_sel = rng.choice(len(Q), size=min(n_queries, len(Q)), replace=False)
        Q_sub = np.ascontiguousarray(Q[q_sel], dtype=np.float32)
        _, top100_unfiltered = flat_ip.search(Q_sub, 100)

        # Compute query-to-folder centroid similarities for cluster-aligned regimes
        centroid_sims = Q_sub @ overlay.folder_centroids.T  # (n_q, 512)
        n_half = len(q_sel) // 2

        specs: List[QuerySpec] = []
        r_vals_near: List[float] = []
        r_vals_far: List[float] = []
        for qi_local, qi in enumerate(q_sel):
            order_f = np.argsort(-centroid_sims[qi_local])
            if qi_local < n_half:
                regime = "near"
                chosen_f = order_f[:n_folders_target].tolist()
            else:
                regime = "far"
                # Draw from folders outside the top-64 semantic clusters of q
                pool = order_f[64:]
                chosen_f = rng.choice(pool, size=n_folders_target, replace=False).tolist()

            mask = np.zeros(N, dtype=np.bool_)
            for fi in chosen_f:
                mask[overlay.folder_to_chunks[overlay.folder_list[int(fi)]]] = True

            s_actual = float(mask.mean())
            s_loc_100 = float(np.mean(mask[top100_unfiltered[qi_local]]))
            r_measured = (s_loc_100 / s_actual) if s_actual > 0.0 else 0.0
            if regime == "near":
                r_vals_near.append(r_measured)
            else:
                r_vals_far.append(r_measured)

            qv = Q[int(qi)]
            gt = _exact_top_k(X, qv, mask, k=10)
            specs.append(
                QuerySpec(
                    query_id=f"H3_{regime}_{qids[int(qi)]}_{qi_local}",
                    vector=qv,
                    mask=mask,
                    gt_ids=gt,
                    condition={
                        "S_target": 0.02,
                        "S_actual": s_actual,
                        "r_measured": float(r_measured),
                        "regime": regime,
                    },
                    extra={"s_loc_100": float(s_loc_100)},
                )
            )

        n_le05 = sum(1 for s in specs if s.condition["r_measured"] <= 0.5)
        n_ge2 = sum(1 for s in specs if s.condition["r_measured"] >= 2.0)
        print(
            f"[H3] seed={seed} queries built: r<=0.5 count={n_le05}, r>=2 count={n_ge2} "
            f"(near med r={np.median(r_vals_near):.2f}, far med r={np.median(r_vals_far):.2f})"
        )

        def _eval_h3(sys_obj) -> None:
            t_s = time.perf_counter()
            n_w = writer.write_all(run_condition(sys_obj, specs, k=10, seed=seed, ctx=ctx))
            print(f"  [H3] seed={seed} {sys_obj.name}: {n_w} recs in {time.perf_counter()-t_s:.2f}s")

        _eval_h3(ExactBruteForceSystem(X))

        faiss_m16 = FaissHNSWSystem(X, M=16, ef_construction=64, ef_search=64, seed=seed, name="faiss-hnsw-M16")
        _eval_h3(faiss_m16)
        del faiss_m16
        gc.collect()

        if Acorn1System.available():
            acorn_sys = Acorn1System(X, M=16, ef_construction=64, ef_search=64, seed=seed, name="acorn-1")
            try:
                _eval_h3(acorn_sys)
            finally:
                acorn_sys.close()
                del acorn_sys
                gc.collect()

        hnsw_sys = HnswlibSystem(X, M=16, ef_construction=64, ef_search=64, seed=seed, name="hnswlib-M16")
        _eval_h3(hnsw_sys)
        del hnsw_sys
        gc.collect()

        z_corpus, hnsw_idx, planner, faiss_m8, _ = build_prism_bundle(
            overlay.auth_graph, X, overlay.ancestor_lineages, overlay.meaning_magnet_ids,
            seed=seed, ef_construction=64, ef_search=64,
        )
        _eval_h3(faiss_m8)
        _eval_h3(PrismGraphOnlySystem(z_corpus, hnsw_idx, ef_search=64, use_gls_adaptive=True, name="prism-graph-only"))
        _eval_h3(PrismGraphOnlySystem(z_corpus, hnsw_idx, ef_search=64, use_gls_adaptive=False, name="prism-static-2hop"))
        _eval_h3(PrismFullSystem(z_corpus, planner, name="prism-full"))
        del z_corpus, hnsw_idx, planner, faiss_m8, specs, overlay
        gc.collect()
        print(f"[H3] seed={seed} total wall={time.perf_counter()-t_seed:.1f}s")


# ---------------------------------------------------------------------------
# H4v2 — Revocation cost on real SpiceDB vs real PostgreSQL/pgvector UPDATE
# ---------------------------------------------------------------------------
def _build_h4_hierarchy(N: int) -> Tuple[ZanzibarAuthGraph, List[List[str]], np.ndarray, np.ndarray, int, int]:
    """
    Constructs a Zanzibar tree where one container edge (`node_L0_0` -> `node_L1_0`)
    covers >= 1,000 docs (~150k chunks at full N=522,931; scaled proportionally if N < 200k).
    """
    if N >= 200_000:
        docs_in_revoked = 1024
        chunks_per_doc = 150
        revoked_chunks = min(docs_in_revoked * chunks_per_doc, int(N * 0.45))  # 153,600 chunks!
        total_docs = max(docs_in_revoked + 1024, (N + chunks_per_doc - 1) // chunks_per_doc)
    else:
        # Smoke scale (e.g. N=20,000): still keep >= 1,000 docs in SpiceDB for realism
        docs_in_revoked = 1024
        revoked_chunks = max(1024, int(round(N * 0.30)))
        total_docs = 2048

    graph = ZanzibarAuthGraph(branching_factor=8, depth=3)
    graph.add_node("node_L0_0", depth_level=0)
    # 2 top-level divisions: node_L1_0 (revoked target: 1,024 docs) and node_L1_1 (retained)
    for d_idx in (0, 1):
        div_id = f"node_L1_{d_idx}"
        graph.add_node(div_id, depth_level=1)
        graph.add_hierarchy_edge("node_L0_0", div_id)

    n_docs_div0 = docs_in_revoked
    n_docs_div1 = total_docs - n_docs_div0
    # Attach 128 sub-folders under div0 (8 docs each = 1,024 docs) and sub-folders under div1
    doc_lineages: Dict[int, List[str]] = {}
    doc_counter = 0
    for f_i in range(n_docs_div0 // 8):
        fid = f"node_L2_0_{f_i}"
        graph.add_node(fid, depth_level=2)
        graph.add_hierarchy_edge("node_L1_0", fid)
        for _ in range(8):
            did = f"doc_L3_{doc_counter}"
            graph.add_node(did, depth_level=3, is_leaf=True)
            graph.add_hierarchy_edge(fid, did)
            doc_lineages[doc_counter] = ["node_L0_0", "node_L1_0", fid, did]
            doc_counter += 1

    n_f1 = max(1, (n_docs_div1 + 7) // 8)
    for f_i in range(n_f1):
        fid = f"node_L2_1_{f_i}"
        graph.add_node(fid, depth_level=2)
        graph.add_hierarchy_edge("node_L1_1", fid)
        for _ in range(8):
            if doc_counter >= total_docs:
                break
            did = f"doc_L3_{doc_counter}"
            graph.add_node(did, depth_level=3, is_leaf=True)
            graph.add_hierarchy_edge(fid, did)
            doc_lineages[doc_counter] = ["node_L0_0", "node_L1_1", fid, did]
            doc_counter += 1

    # Assign chunks: first revoked_chunks to div0 docs, rest to div1 docs
    doc_int_ids = np.empty(N, dtype=np.int32)
    folder_int_ids = np.empty(N, dtype=np.int32)
    doc_int_ids[:revoked_chunks] = np.arange(revoked_chunks, dtype=np.int32) % n_docs_div0
    folder_int_ids[:revoked_chunks] = 0
    rem = N - revoked_chunks
    doc_int_ids[revoked_chunks:] = n_docs_div0 + (np.arange(rem, dtype=np.int32) % max(1, total_docs - n_docs_div0))
    folder_int_ids[revoked_chunks:] = 1

    ancestor_lineages = [doc_lineages[int(di)] for di in doc_int_ids]
    return graph, ancestor_lineages, doc_int_ids, folder_int_ids, n_docs_div0, revoked_chunks


def run_h4(
    X_full: np.ndarray,
    n_trials: int,
    ctx_base: Dict[str, object],
    writer: RawWriter,
    build_hnsw_on_h4: bool = True,
) -> None:
    N = len(X_full)
    print(f"[H4] starting: trials={n_trials} N={N}")
    graph, lineages, doc_ints, folder_ints, docs_covered, chunks_covered = _build_h4_hierarchy(N)
    graph.grant_access("org_exec", "node_L0_0")
    dummy_mags = ["magnet_0"] * N
    z_corpus = ZOrderedCorpus(X_full, lineages, dummy_mags)
    postings = _build_roaring_postings(z_corpus)

    with SpiceDBService() as sp, PostgresPgvectorService() as pg:
        sp.load_hierarchy(graph)
        sp.write_principal_policy("org_exec", grants={"node_L0_0"}, denies=set())

        # Load real PostgreSQL + pgvector table (with real HNSW index on vec!)
        t_pg = pg.load_vectors_table(
            "h4_vecs", X_full, doc_ints, folder_ints,
            m=16, ef_construction=64, build_hnsw=build_hnsw_on_h4,
        )
        # Create B-tree index on folder_id so PostgreSQL UPDATE doesn't waste time scanning non-target rows
        pg.conn.execute("CREATE INDEX h4_vecs_folder_idx ON h4_vecs (folder_id);")
        pg.conn.execute("ANALYZE h4_vecs;")
        print(f"[H4] loaded {N} rows into PostgreSQL+pgvector (HNSW={build_hnsw_on_h4}) in {t_pg:.1f}s")
        print(f"[H4] revoking node_L1_0 covering {docs_covered} docs / {chunks_covered} chunks")

        cond = {"docs_covered": int(docs_covered), "chunks_covered": int(chunks_covered)}
        for trial in range(n_trials):
            # --- P4a path: real SpiceDB DeleteRelationships + mirror + next-query UBP + CRoaring bitmap ---
            t0 = time.perf_counter_ns()
            zt_del = sp.delete_parent_edge("node_L0_0", "node_L1_0")
            graph.remove_hierarchy_edge("node_L0_0", "node_L1_0")
            res = graph.upward_boundary_prune("org_exec")
            b_ubp = _compile_roaring_ubp(postings, res.tokens_pos, res.tokens_neg)
            wall_p4a = time.perf_counter_ns() - t0

            # Verify revocation correctness on trial 0 against real SpiceDB (outside timer)
            if trial == 0:
                sp_after = sp.lookup_resources_docs("org_exec", zed_token=zt_del)
                ubp_after = _ubp_to_leaf_docs(graph, res.tokens_pos, res.tokens_neg)
                assert sp_after == ubp_after, f"H4 revocation mismatch: {len(sp_after ^ ubp_after)}"
                assert len(b_ubp) == N - chunks_covered, f"H4 bitmap size {len(b_ubp)} != {N - chunks_covered}"

            # Restore SpiceDB + mirror edge outside timer before next trial
            if trial + 1 < n_trials:
                sp.restore_parent_edge("node_L0_0", "node_L1_0")
                graph.add_hierarchy_edge("node_L0_0", "node_L1_0")

            # --- P4b path: real PostgreSQL UPDATE acl_allowed = FALSE on ~150k rows ---
            t0 = time.perf_counter_ns()
            rows_aff = pg.update_acl_for_folder("h4_vecs", folder_id=0, allowed=False)
            wall_p4b = time.perf_counter_ns() - t0
            assert rows_aff == chunks_covered, f"Updated {rows_aff} != {chunks_covered}"

            # Reset + VACUUM outside timer so subsequent trials start clean
            if trial + 1 < n_trials:
                pg.update_acl_for_folder("h4_vecs", folder_id=0, allowed=True)
                pg.conn.execute("VACUUM h4_vecs;")

            base = dict(hypothesis="H4", seed=0, query_id=f"trial_{trial}", condition=cond, **ctx_base)
            writer.write(
                RawRecord(
                    system="P4a-path(SpiceDB-Delete+mirror+UBP+bitmap)",
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
                f"  [H4] trial={trial}: P4a={wall_p4a/1e6:.2f} ms (0 writes) vs "
                f"pgvector UPDATE={wall_p4b/1e6:.2f} ms ({rows_aff} rows, ratio={wall_p4b/wall_p4a:.1f}x)"
            )


# ---------------------------------------------------------------------------
# Entry point called by bench/harness.py
# ---------------------------------------------------------------------------
def run_all(args, ctx_base: Dict[str, object], writer: RawWriter) -> None:
    hyps = [h.strip().upper() for h in args.hypotheses.split(",") if h.strip()]
    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]

    X, Q, qids = load_quora_embeddings(n_corpus=args.n_corpus)
    print(f"[experiments] loaded BEIR Quora MiniLM: X={X.shape} Q={Q.shape} hyps={hyps} seeds={seeds}")

    if "H1" in hyps:
        run_h1(X, seeds, args.h1_principals, ctx_base, writer)
    if "H2" in hyps:
        run_h2(X, Q, qids, seeds, args.n_queries, ctx_base, writer)
    if "H3" in hyps:
        run_h3(X, Q, qids, seeds, args.n_queries, ctx_base, writer)
    if "H4" in hyps:
        # For confirmatory H4, always load the full corpus if args.n_corpus == 0 (or full 522,931 for ~150k chunks!)
        if args.run_type == "confirmatory" and len(X) < 200_000:
            X_h4, _, _ = load_quora_embeddings(n_corpus=0)
        else:
            X_h4 = X
        run_h4(X_h4, args.h4_trials, ctx_base, writer, build_hnsw_on_h4=True)
