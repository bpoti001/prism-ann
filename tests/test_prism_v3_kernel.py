"""
Unit & Parity Tests for Prism-ANN v3 C++ NEON Kernel & Geometric H-HNSW v2
==========================================================================
Verifies (ADR-0005, Phase 17-01 & 17-02):
  1. `prism_mode3_scan_ranges_f32` == 100.0% Recall@10 & 0 unauthorized leaks
  2. `prism_mode3_scan_ranges_sq8` + top-4k FP32 rerank >= 99.5% Recall@10 & 0 leaks
  3. `prism_search_hhnsw_gls` returns 0 unauthorized IDs across 100 randomized
     filtered queries and matches pure-Python reference `search_hhnsw_gls_py_ref`
  4. Local-Stall Mode-3 Escalation Guard recovers 100% recall on depleted pockets
  5. `PrismANNIndexV3` end-to-end UBP + O(1) revocation + search invariant
"""

from __future__ import annotations

import unittest
import numpy as np

from src.modules.prism_ann.trimodal_planner import RoaringRunBitmap, ZOrderedCorpus
from src.modules.prism_ann.ubp_resolver import ZanzibarAuthGraph
from src.modules.prism_ann_v3.ckernel_bridge import (
    load_ckernel,
    mode3_scan_ranges_f32,
    mode3_scan_ranges_sq8,
)
from src.modules.prism_ann_v3.geometric_hhnsw import (
    GeometricBridgeConfig,
    GeometricHHNSW,
    search_hhnsw_gls_py_ref,
)
from src.modules.prism_ann_v3.index import PrismANNIndexV3
from src.modules.prism_ann_v3.trimodal_v3 import (
    TriModalPlannerV3,
    bool_mask_to_range_arrays,
    runs_to_range_arrays,
)


def _exact_top_k(X: np.ndarray, q: np.ndarray, mask: np.ndarray, k: int = 10) -> np.ndarray:
    valid = np.flatnonzero(mask)
    if len(valid) == 0:
        return np.empty(0, dtype=np.int32)
    sims = X[valid] @ q
    order = np.argsort(-sims, kind="stable")[:k]
    return valid[order].astype(np.int32)


class TestPrismV3KernelAndGeometricHHNSW(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rng = np.random.default_rng(2026)
        cls.N = 4096
        cls.d = 384
        # Build realistic clustered unit-normalized 384-d embeddings
        n_clusters = 32
        centers = cls.rng.standard_normal((n_clusters, cls.d)).astype(np.float32)
        centers /= np.linalg.norm(centers, axis=1, keepdims=True)
        labels = cls.rng.integers(0, n_clusters, size=cls.N)
        noise = cls.rng.standard_normal((cls.N, cls.d)).astype(np.float32) * 0.35
        X = centers[labels] + noise
        X /= np.linalg.norm(X, axis=1, keepdims=True)
        cls.X = np.ascontiguousarray(X, dtype=np.float32)
        cls.X_sq8 = np.ascontiguousarray(
            np.clip(np.round(cls.X * 127.0), -127, 127).astype(np.int8)
        )

        # Build balanced Zanzibar tree (b=4, L=3 -> 64 leaf docs, 16 L2 folders, 4 L1)
        cls.graph = ZanzibarAuthGraph.build_balanced_hierarchy(branching_factor=4, depth=3)
        leaf_docs = sorted(cls.graph.leaf_documents)
        lineages = [cls.graph.get_ancestor_lineage(leaf_docs[i % len(leaf_docs)]) for i in range(cls.N)]
        magnets = [f"magnet_{int(labels[i])}" for i in range(cls.N)]

        cls.z_corpus = ZOrderedCorpus(cls.X, lineages, magnets)
        cls.l2_ids = [lin[-3] if len(lin) >= 3 else lin[-1] for lin in cls.z_corpus.ancestor_lineages]
        cls.hhnsw = GeometricHHNSW(
            vectors=cls.z_corpus.vectors,
            l3_container_ids=cls.z_corpus.primary_containers,
            l2_container_ids=cls.l2_ids,
            meaning_magnet_ids=cls.z_corpus.meaning_magnet_ids,
            bridge_config=GeometricBridgeConfig.for_m_bridge(8, "geometric"),
            M=16,
            ef_construction=64,
            seed=7,
        )

    def test_ckernel_loads_and_reports_simd(self) -> None:
        lib = load_ckernel()
        self.assertIn(int(lib.prism_kernel_has_neon()), (0, 1))
        self.assertIn(int(lib.prism_kernel_has_dotprod()), (0, 1))

    def test_mode3_f32_exact_recall_and_zero_leaks(self) -> None:
        rng = np.random.default_rng(101)
        k = 10
        for qi in range(100):
            q = rng.standard_normal(self.d).astype(np.float32)
            q /= np.linalg.norm(q)
            n_runs = int(rng.integers(1, 25))
            mask = np.zeros(self.N, dtype=np.bool_)
            for _ in range(n_runs):
                s = int(rng.integers(0, self.N - 1))
                length = int(rng.integers(1, 120))
                mask[s : min(self.N, s + length)] = True
            if qi == 0:
                # Edge case: fewer than k authorized vectors
                mask[:] = False
                mask[[5, 100, 2000]] = True
            elif qi == 1:
                # Edge case: empty filter
                mask[:] = False

            starts, ends, n_cand = bool_mask_to_range_arrays(mask)
            ids, scores, evals = mode3_scan_ranges_f32(self.X, q, starts, ends, k=k)
            gt = _exact_top_k(self.X, q, mask, k=k)

            self.assertEqual(evals, n_cand)
            self.assertEqual(len(ids), len(gt))
            for nid in ids:
                self.assertTrue(mask[int(nid)], f"Unauthorized leak in Mode-3 f32: {nid}")
            if len(gt) > 0:
                recall = len(set(ids.tolist()) & set(gt.tolist())) / float(len(gt))
                self.assertEqual(recall, 1.0, f"Mode-3 f32 recall < 1.0 on query {qi}")
                # Check score agreement with FP32 dot product
                np.testing.assert_allclose(scores, self.X[ids] @ q, atol=1e-5)

    def test_mode3_sq8_high_recall_and_zero_leaks(self) -> None:
        rng = np.random.default_rng(202)
        k = 10
        recalls = []
        for _ in range(100):
            q = rng.standard_normal(self.d).astype(np.float32)
            q /= np.linalg.norm(q)
            q_sq8 = np.ascontiguousarray(np.clip(np.round(q * 127.0), -127, 127).astype(np.int8))
            mask = np.zeros(self.N, dtype=np.bool_)
            for _ in range(int(rng.integers(1, 15))):
                s = int(rng.integers(0, self.N - 1))
                mask[s : min(self.N, s + int(rng.integers(15, 250)))] = True
            starts, ends, n_cand = bool_mask_to_range_arrays(mask)
            ids, _, evals = mode3_scan_ranges_sq8(
                self.X_sq8, self.X, q_sq8, q, starts, ends, k=k, rerank_k=max(4 * k, 64)
            )
            gt = _exact_top_k(self.X, q, mask, k=k)
            self.assertEqual(evals, n_cand)
            for nid in ids:
                self.assertTrue(mask[int(nid)], f"Unauthorized leak in Mode-3 sq8: {nid}")
            recalls.append(len(set(ids.tolist()) & set(gt.tolist())) / float(len(gt)))

        mean_recall = float(np.mean(recalls))
        self.assertGreaterEqual(mean_recall, 0.995, f"SQ8+rerank mean recall {mean_recall:.4f} < 0.995")

    def test_hhnsw_gls_zero_leaks_and_python_parity(self) -> None:
        rng = np.random.default_rng(303)
        k = 10
        n_total_queries = 100
        parity_checks = 20

        for qi in range(n_total_queries):
            q = rng.standard_normal(self.d).astype(np.float32)
            q /= np.linalg.norm(q)
            # Sample realistic container-contiguous Z-order masks across selectivities
            sel_s = [0.005, 0.02, 0.10, 0.50][qi % 4]
            n_runs = max(1, int(rng.integers(1, 8)))
            run_len = max(1, int((self.N * sel_s) / n_runs))
            mask = np.zeros(self.N, dtype=np.bool_)
            for _ in range(n_runs):
                s = int(rng.integers(0, self.N - 1))
                mask[s : min(self.N, s + run_len)] = True
            starts, ends, _ = bool_mask_to_range_arrays(mask)

            use_bridges = (qi % 3 != 0)
            use_portals = (qi % 2 == 0)
            use_gls = (qi % 5 != 0)
            faiss_1hop = (qi >= 80)

            res_cpp = self.hhnsw.search_ranges(
                query_vec=q,
                starts=starts,
                ends=ends,
                k=k,
                ef_search=48,
                tau_high=0.50,
                tau_low=0.02,
                use_express_bridges=use_bridges,
                use_portals=use_portals,
                max_portals=4,
                use_gls_adaptive=use_gls,
                faiss_style_1hop=faiss_1hop,
                tau_stall=0.0,
            )

            # Strict 0-leak & uniqueness invariant
            self.assertEqual(len(res_cpp.top_k_ids), len(set(res_cpp.top_k_ids)))
            for nid in res_cpp.top_k_ids:
                self.assertTrue(0 <= nid < self.N and mask[nid], f"Unauthorized leak in C++ H-HNSW: {nid}")

            # Verify exact parity with Python reference implementation on first 20 non-faiss queries
            if qi < parity_checks and not faiss_1hop:
                res_py = search_hhnsw_gls_py_ref(
                    index=self.hhnsw,
                    query_vec=q,
                    mask=mask,
                    k=k,
                    ef_search=48,
                    tau_high=0.50,
                    tau_low=0.02,
                    use_express_bridges=use_bridges,
                    use_portals=use_portals,
                    max_portals=4,
                    use_gls_adaptive=use_gls,
                )
                self.assertEqual(
                    res_cpp.top_k_ids,
                    res_py.top_k_ids,
                    f"C++ vs Python top-k mismatch on q={qi} (bridges={use_bridges}, portals={use_portals}, gls={use_gls})",
                )
                self.assertEqual(res_cpp.distance_evaluations, res_py.distance_evaluations)
                self.assertEqual(res_cpp.hops_1hop, res_py.hops_1hop)
                self.assertEqual(res_cpp.hops_2hop, res_py.hops_2hop)
                self.assertEqual(res_cpp.hops_teleport, res_py.hops_teleport)

    def test_local_stall_mode3_guard_recovers_depleted_pocket(self) -> None:
        # Force a query whose semantic neighborhood is strictly disjoint from authorized Z-slice
        planner = TriModalPlannerV3(
            auth_graph=self.graph,
            z_corpus=self.z_corpus,
            hhnsw=self.hhnsw,
            s_sparse_threshold=0.005,  # force S=0.03 into Mode 2 initially
            ef_search=32,
            tau_high=0.55,
            tau_low=0.02,
            tau_stall=0.08,            # trigger guard when early local selectivity < 0.08
            stall_check_hops=8,
            n_guard=500,
            mode3_precision="f32",
            use_portals=False,
        )
        # Authorize only a tiny 120-node slice (~3%) far from vector 0's semantic cluster
        mask = np.zeros(self.N, dtype=np.bool_)
        q = -self.z_corpus.vectors[0]  # opposite direction from cluster of node 0
        sims_all = self.z_corpus.vectors @ q
        worst_idx = np.argsort(sims_all)[:120]
        mask[worst_idx] = True
        starts, ends, n_cand = bool_mask_to_range_arrays(mask)
        res = planner.query_with_ranges(q, starts, ends, n_cand=n_cand, k=10)
        gt = _exact_top_k(self.z_corpus.vectors, q, mask, k=10)

        self.assertTrue(res.stalled_escalated, "Expected Local-Stall Guard to escalate to Mode 3")
        self.assertTrue(res.execution_mode.startswith("MODE_3_STALL_GUARD"))
        self.assertEqual(set(res.top_k_ids), set(gt.tolist()))
        for nid in res.top_k_ids:
            self.assertTrue(mask[nid])

    def test_prism_v3_index_end_to_end_and_revocation(self) -> None:
        graph = ZanzibarAuthGraph.build_balanced_hierarchy(branching_factor=4, depth=3)
        leaf_docs = sorted(graph.leaf_documents)
        N_small = 512
        rng = np.random.default_rng(777)
        X = rng.standard_normal((N_small, 64)).astype(np.float32)
        X /= np.linalg.norm(X, axis=1, keepdims=True)
        lineages = [graph.get_ancestor_lineage(leaf_docs[i % len(leaf_docs)]) for i in range(N_small)]
        magnets = [f"mag_{i % 8}" for i in range(N_small)]

        graph.grant_access("alice", "node_L0_0")
        graph.add_deny_exclusion("alice", "node_L1_0")

        idx = PrismANNIndexV3(
            auth_graph=graph,
            raw_vectors=X,
            ancestor_lineages=lineages,
            meaning_magnet_ids=magnets,
            M=16,
            m_bridge=8,
            seed=11,
        )
        q = rng.standard_normal(64).astype(np.float32)
        q /= np.linalg.norm(q)
        res = idx.search(q, principal_id="alice", k=10)
        self.assertEqual(len(res.top_k_ids), 10)
        for zid in res.top_k_ids:
            self.assertNotIn("node_L1_0", idx.z_corpus.ancestor_lineages[zid])

        # O(1) zero-write revocation of node_L1_1
        idx.revoke_hierarchy_edge("node_L0_0", "node_L1_1")
        res2 = idx.search(q, principal_id="alice", k=10)
        for zid in res2.top_k_ids:
            self.assertNotIn("node_L1_0", idx.z_corpus.ancestor_lineages[zid])
            self.assertNotIn("node_L1_1", idx.z_corpus.ancestor_lineages[zid])


if __name__ == "__main__":
    unittest.main()
