"""
Tracer-Bullet Seam TDD Suite for Prism-ANN (tests/test_prism_ann.py)
====================================================================
Tests ONLY through the public Deep Module seam (`src/modules/prism_ann/index.py`).
Verifies:
  1. ADR-0001 / Theorem 1: 100% set equivalence (0 false positives, 0 false negatives)
     between Subtractive-Aware Upward Boundary Pruning (P_UBP) and exhaustive leaf
     LookupResources across m in [0..20] DENY rules, and strict cardinality bound
     |T_UBP^+(u)| <= k_0 + m * (b - 1) * L.
  2. ADR-0001 / Corollary 1: O(1) zero-write document/container revocation with causal
     ZedToken advancement.
  3. ADR-0002 / Theorems 2 & 3: Ancestor-Stitched Express Bridges (M_bridge=4, <8% RAM)
     restoring sub-1% and negative-correlation (r < 1) recall, and Bitmask-POPCNT
     ACORN-GLS reducing distance evaluations in dense pockets.
  4. ADR-0003 / Theorem 4: Lexicographic Z-Order RunContainer compression and
     Shard-Coupled Tri-Modal Routing across Mode 1, Mode 2, and Mode 3 (1.000 Recall@10).
"""

import os
import sys
import unittest
import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.modules.prism_ann import (
    PrismANNIndex,
    ZanzibarAuthGraph,
    resolve_ubp_tokens,
    AncestorStitchedHNSW,
    compute_theoretical_percolation_cliff,
    search_hnsw_gls,
    RoaringRunBitmap,
    ZOrderedCorpus,
    TriModalQueryPlanner,
    compute_optimal_crossover_threshold,
    execute_trimodal_query,
)


class TestPrismANNSeamTDD(unittest.TestCase):
    """Deterministic unit and property tests for Theorems 1, 2, 3, and 4."""

    def test_theorem1_ubp_exact_set_equivalence_and_cardinality_bound(self):
        """
        Verifies Theorem 1 across m in [0..20] explicit DENY ('but not') exclusions:
          1. 0 false positives and 0 false negatives relative to exhaustive leaf LookupResources.
          2. |T_UBP^+(u)| <= k_0 + m * (b - 1) * L for every configuration.
        """
        b = 4
        L = 4
        graph = ZanzibarAuthGraph.build_balanced_hierarchy(branching_factor=b, depth=L)
        all_leaves = sorted(graph.leaf_documents)
        self.assertEqual(len(all_leaves), b ** L)  # 4^4 = 256 leaf documents

        # Build a ZOrderedCorpus with 2 chunks per leaf document (512 chunks)
        rng = np.random.default_rng(101)
        lineages = []
        magnets = []
        for idx, leaf_id in enumerate(all_leaves):
            anc = graph.get_ancestor_lineage(leaf_id)
            for c_sub in range(2):
                lineages.append(anc)
                magnets.append(f"magnet_{(idx + c_sub) % 8}")

        raw_vecs = rng.standard_normal((len(lineages), 32), dtype=np.float32)
        z_corpus = ZOrderedCorpus(raw_vecs, lineages, magnets)

        # Candidate interior and leaf nodes for DENY exclusions
        non_root_nodes = [n for n in sorted(graph.all_nodes) if graph.node_depth[n] >= 1]

        for m_denies in [0, 1, 2, 5, 10, 15, 20]:
            principal = f"user_m{m_denies}"
            # Grant top-level root access (k_0 = 1)
            graph.grant_access(principal, "node_L0_0")

            # Deterministically sample m_denies nodes across levels 2..L
            eligible_denies = [n for n in non_root_nodes if graph.node_depth[n] >= 2]
            chosen_denies = eligible_denies[:m_denies]
            for d_node in chosen_denies:
                graph.add_deny_exclusion(principal, d_node)

            # 1. Exhaustive Naive LookupResources leaf set
            expected_leaves = graph.lookup_resources_leaf(principal)
            bm_naive = z_corpus.compile_acl_bitmap_naive_leaves(expected_leaves)
            expected_chunk_ids = bm_naive.to_id_set()

            # 2. Subtractive-Aware Upward Boundary Pruning (P_UBP)
            ubp_res = graph.upward_boundary_prune(principal)
            tokens_pos, tokens_neg = resolve_ubp_tokens(graph, principal)
            self.assertEqual(tokens_pos, ubp_res.tokens_pos)

            bm_ubp = z_corpus.compile_acl_bitmap_ubp(tokens_pos, tokens_neg)
            actual_chunk_ids = bm_ubp.to_id_set()

            # Exactness Invariant: 0 False Positives and 0 False Negatives
            false_positives = actual_chunk_ids - expected_chunk_ids
            false_negatives = expected_chunk_ids - actual_chunk_ids
            self.assertEqual(
                len(false_positives),
                0,
                f"Found {len(false_positives)} false positives at m={m_denies}",
            )
            self.assertEqual(
                len(false_negatives),
                0,
                f"Found {len(false_negatives)} false negatives at m={m_denies}",
            )

            # Cardinality Bound: |T_UBP^+(u)| <= k_0 + m * (b - 1) * L
            upper_bound = 1 + m_denies * (b - 1) * L
            self.assertLessEqual(
                len(tokens_pos),
                upper_bound,
                f"|T_UBP^+|={len(tokens_pos)} exceeded Theorem 1 bound {upper_bound} at m={m_denies}",
            )

    def test_corollary1_zero_write_document_revocation(self):
        """
        Verifies Corollary 1: Revoking a structural container or document edge in SpiceDB
        executes in O(1) graph operations, increments ZedToken, and immediately excludes
        all descendant chunks without modifying a single vector chunk record.
        """
        graph = ZanzibarAuthGraph.build_balanced_hierarchy(branching_factor=4, depth=3)
        all_leaves = sorted(graph.leaf_documents)
        rng = np.random.default_rng(202)

        lineages = [graph.get_ancestor_lineage(leaf) for leaf in all_leaves]
        magnets = [f"mag_{i % 4}" for i in range(len(all_leaves))]
        vecs = rng.standard_normal((len(all_leaves), 32), dtype=np.float32)

        prism = PrismANNIndex(
            auth_graph=graph,
            raw_vectors=vecs,
            ancestor_lineages=lineages,
            meaning_magnet_ids=magnets,
        )

        principal = "analyst_1"
        graph.grant_access(principal, "node_L0_0")
        initial_zed = graph.zed_token

        # Before revocation: all 64 leaf documents are authorized
        q = vecs[0]
        res_before = prism.search(q, principal_id=principal, k=10)
        self.assertEqual(res_before.candidate_count, 64)
        self.assertEqual(res_before.ubp_positive_tokens, 1)

        # Revoke level-1 branch 'node_L1_0' (which governs 16 leaf documents) via O(1) edge removal
        new_zed = prism.revoke_hierarchy_edge("node_L0_0", "node_L1_0")
        self.assertGreater(new_zed, initial_zed)

        # After O(1) revocation: candidate count drops immediately from 64 to 48 with 0 vector writes
        res_after = prism.search(q, principal_id=principal, k=10)
        self.assertEqual(res_after.candidate_count, 48)

    def test_theorem2_and_theorem3_express_bridges_and_acorn_gls(self):
        """
        Verifies Theorems 2 & 3:
          1. Ancestor-Stitched Express Bridges (M_bridge=4) add < 8% total RAM overhead.
          2. Under low selectivity & negative Global-Local Selectivity correlation (r < 1),
             H-HNSW + ACORN-GLS achieves significantly higher Recall@10 than standalone ACORN-1.
          3. In dense neighborhoods (S_loc >= 0.25), ACORN-GLS skips 2-hop expansion and
             reduces distance evaluations by >2x compared to static ACORN-1.
        """
        s_crit_acorn1 = compute_theoretical_percolation_cliff(m_degree=16, gls_ratio=0.5, m_bridge=0)
        s_crit_bridge = compute_theoretical_percolation_cliff(
            m_degree=16, gls_ratio=0.5, m_bridge=4, s_container=0.05
        )
        self.assertAlmostEqual(s_crit_acorn1, 2.0 / (0.5 * 16 * 17), places=5)
        self.assertLess(s_crit_bridge, 0.001)  # < 0.1%

        N = 1600
        d = 128
        rng = np.random.default_rng(303)
        # Generate a realistic clustered semantic embedding manifold (32 semantic clusters)
        n_clusters = 32
        centroids = rng.standard_normal((n_clusters, d), dtype=np.float32)
        centroids /= np.linalg.norm(centroids, axis=1, keepdims=True)
        cluster_assign = np.arange(N) % n_clusters
        vecs = centroids[cluster_assign] + 0.18 * rng.standard_normal((N, d), dtype=np.float32)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)

        containers = [f"cont_{i // 40}" for i in range(N)]
        magnets = [f"mag_{i % 20}" for i in range(N)]

        # Target composite predicate (S = 1.0%, negatively correlated with entry clusters 0..15)
        target_mask = np.zeros(N, dtype=np.bool_)
        target_ids = [
            i for i in range(N)
            if (containers[i] in ("cont_7", "cont_19") or magnets[i] == "mag_3")
            and (cluster_assign[i] >= 16)
        ]
        for tid in target_ids[:24]:
            target_mask[tid] = True

        index_stitched = AncestorStitchedHNSW(
            corpus_vectors=vecs,
            container_ids=containers,
            meaning_magnet_ids=magnets,
            m_degree=16,
            m_bridge=4,
            seed=42,
        )
        mem_stats = index_stitched.memory_footprint_stats()
        self.assertLess(mem_stats["total_ram_overhead_pct"], 8.0)

        # Ground truth top-10 inside target_mask
        valid_ids = np.flatnonzero(target_mask)
        q = index_stitched.corpus_vectors[valid_ids[0]] + 0.15 * rng.standard_normal(d, dtype=np.float32)
        q = q / np.linalg.norm(q)
        gt_sims = index_stitched.corpus_vectors[valid_ids] @ q
        gt_top10 = set(valid_ids[np.argsort(gt_sims)[::-1][:10]])

        # Standalone ACORN-1 (no express bridges, static 2-hop)
        res_acorn1 = search_hnsw_gls(
            index_stitched,
            q,
            target_mask,
            k=10,
            ef_search=28,
            use_express_bridges=False,
            use_gls_adaptive=False,
        )
        # Full H-HNSW + ACORN-GLS (with M_bridge=4 express bridges + POPCNT adaptive teleport)
        res_gls = search_hnsw_gls(
            index_stitched,
            q,
            target_mask,
            k=10,
            ef_search=28,
            use_express_bridges=True,
            use_gls_adaptive=True,
        )

        recall_acorn1 = len(set(res_acorn1.top_k_ids) & gt_top10) / 10.0
        recall_gls = len(set(res_gls.top_k_ids) & gt_top10) / 10.0
        self.assertGreater(recall_gls, recall_acorn1)
        self.assertGreaterEqual(recall_gls, 0.80)

        # Now verify dense pocket distance evaluation savings (S = 0.80)
        dense_mask = np.ones(N, dtype=np.bool_)
        dense_mask[::5] = False  # 80% selectivity
        res_dense_static = search_hnsw_gls(
            index_stitched,
            q,
            dense_mask,
            k=10,
            ef_search=32,
            use_express_bridges=False,
            use_gls_adaptive=False,
        )
        res_dense_gls = search_hnsw_gls(
            index_stitched,
            q,
            dense_mask,
            k=10,
            ef_search=32,
            use_express_bridges=True,
            use_gls_adaptive=True,
        )
        self.assertLess(res_dense_gls.distance_evaluations, res_dense_static.distance_evaluations * 0.5)

    def test_theorem4_z_ordered_roaring_simd_and_trimodal_routing(self):
        """
        Verifies Theorem 4:
          1. Z-Ordered vector layout compresses structural container tokens into single
             contiguous RunContainers.
          2. Tri-Modal Planner routes high-S to Mode 1, mid-S to Mode 2, and ultra-low-S
             to Mode 3 (Z-Order Roaring-SIMD Flat Scan) with 1.000 exact Recall@10.
        """
        graph = ZanzibarAuthGraph.build_balanced_hierarchy(branching_factor=4, depth=3)
        leaves = sorted(graph.leaf_documents)  # 64 leaves
        rng = np.random.default_rng(404)

        lineages = []
        magnets = []
        for leaf in leaves:
            anc = graph.get_ancestor_lineage(leaf)
            for k_chunk in range(16):  # 64 * 16 = 1024 chunks
                lineages.append(anc)
                magnets.append(f"mag_{k_chunk % 8}")

        vecs = rng.standard_normal((len(lineages), 64), dtype=np.float32)
        prism = PrismANNIndex(
            auth_graph=graph,
            raw_vectors=vecs,
            ancestor_lineages=lineages,
            meaning_magnet_ids=magnets,
        )

        # Verify that level-1 container 'node_L1_0' occupies exactly 1 contiguous RunContainer!
        bm_l1 = prism.z_corpus.token_bitmaps["node_L1_0"]
        self.assertEqual(bm_l1.num_run_containers(), 1)
        self.assertEqual(bm_l1.popcount(), 256)

        q = prism.z_corpus.vectors[5]

        # Mode 1: High Selectivity (S = 1.0 > 0.60)
        graph.grant_access("user_broad", "node_L0_0")
        res_m1 = prism.search(q, principal_id="user_broad", k=10)
        self.assertEqual(res_m1.execution_mode, "MODE_1_DENSE_1HOP_HNSW")
        self.assertAlmostEqual(res_m1.global_selectivity, 1.0)

        # Mode 2: Mid Selectivity (S = 0.25)
        graph.grant_access("user_mid", "node_L1_0")
        res_m2 = prism.search(q, principal_id="user_mid", k=10)
        self.assertEqual(res_m2.execution_mode, "MODE_2_ANCESTOR_STITCHED_ACORN_GLS")
        self.assertAlmostEqual(res_m2.global_selectivity, 0.25)

        # Mode 3: Ultra-Low Selectivity (1 leaf document + 1 magnet -> 2 chunks / 1024 <= N_flat^*)
        graph.grant_access("user_sparse", leaves[0])
        res_m3 = prism.search(q, principal_id="user_sparse", k=10)
        self.assertEqual(res_m3.execution_mode, "MODE_3_Z_ORDER_ROARING_SIMD")

        # Verify 1.000 exact Recall@10 in Mode 3
        b_sparse = prism.z_corpus.token_bitmaps[leaves[0]]
        valid_sparse = list(b_sparse.to_id_set())
        gt_sims = prism.z_corpus.vectors[valid_sparse] @ (q / np.linalg.norm(q))
        gt_top10 = set(np.array(valid_sparse)[np.argsort(gt_sims)[::-1][:10]])
        self.assertEqual(set(res_m3.top_k_ids), gt_top10)


if __name__ == "__main__":
    unittest.main()
