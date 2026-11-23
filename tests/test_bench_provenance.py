"""
Provenance tests for the v2 benchmark harness (ADR-0004)
========================================================
  * raw records carry every ADR-0004 field and are emitted only via run_condition
  * bench.recompute is deterministic and byte-for-byte reproducible
  * tampering with a raw record changes the recomputed summary (check fails)
  * results/v2/summary.json (once it exists) is exactly what recompute produces
  * the frozen Prism-ANN files still match FREEZE.md
  * Brake 2/3 scripts contain no literal scores or verdicts
  * `research_factory.py init-prism-ann` refuses to overwrite without --force
"""

import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from bench import harness, recompute  # noqa: E402
from bench.harness import QuerySpec, RawWriter, RunContext, SearchOutput, run_condition  # noqa: E402


class _Exact:
    """Toy exact filtered brute force (test fixture only)."""

    def __init__(self, name, X):
        self.name, self.X = name, X

    def search(self, q, k):
        ids = np.flatnonzero(q.mask)
        sims = self.X[ids] @ q.vector
        top = ids[np.argsort(-sims)[:k]]
        return SearchOutput(ids=[int(i) for i in top], distance_computations=len(ids))


class _Half(_Exact):
    def search(self, q, k):
        out = super().search(q, k)
        return SearchOutput(ids=out.ids[: k // 2], distance_computations=7, extra={"mode": "half"})


def _make_queries(X, rng, n, hyp):
    out = []
    for i in range(n):
        v = rng.standard_normal(X.shape[1]).astype(np.float32)
        v /= np.linalg.norm(v)
        mask = rng.random(X.shape[0]) < 0.2
        ids = np.flatnonzero(mask)
        gt = ids[np.argsort(-(X[ids] @ v))[:10]]
        cond = {"S_target": 0.2, "S_actual": float(mask.mean())}
        if hyp == "H3":
            cond.update({"r_measured": [0.1, 1.0, 3.0][i % 3], "regime": ["far", "random", "near"][i % 3]})
        out.append(QuerySpec(f"q{i}", v, mask, [int(g) for g in gt], cond))
    return out


def _write_synthetic_run(raw_dir, run_id="v2-test-0"):
    rng = np.random.default_rng(0)
    X = rng.standard_normal((500, 16)).astype(np.float32)
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    w = RawWriter(raw_dir, run_id)
    for hyp in ("H2", "H3"):
        for seed in (0, 1, 2):
            ctx = RunContext(run_id, "smoke", "deadbeef", True, hyp)
            qs = _make_queries(X, rng, 9, hyp)
            for system in (_Exact("prism-graph-only", X), _Half("faiss-hnsw-M16", X),
                           _Exact("prism-static-2hop", X), _Exact("prism-full", X)):
                w.write_all(run_condition(system, qs, 10, seed, ctx))
    for seed in (0, 1, 2):
        for p in range(70):
            base = dict(run_id=run_id, run_type="smoke", git_sha="deadbeef", freeze_match=True,
                        hypothesis="H1", seed=seed, query_id=f"p{p}")
            n_docs = 1200 if p % 2 else 40
            w.write(harness.RawRecord(system="H1-oracle-check", wall_ns=1000 + p, result_ids=[1, 2],
                                      gt_ids=[1, 2], extra={"mismatch_docs": 0, "mismatch_chunks": 0,
                                                            "within_bound": True, "tokens_pos": 3,
                                                            "n_auth_docs": n_docs, "m_denies": p % 21}, **base))
            for sysname, ns in (("UBP+bitmap", 2000 + p), ("SpiceDB-LookupResources+leaf-bitmap", 90000 + p)):
                w.write(harness.RawRecord(system=sysname, wall_ns=ns, extra={"n_auth_docs": n_docs}, **base))
    for t in range(3):
        base = dict(run_id=run_id, run_type="smoke", git_sha="deadbeef", freeze_match=True,
                    hypothesis="H4", seed=0, query_id=f"t{t}", condition={"docs_covered": 512})
        w.write(harness.RawRecord(system="P4a-path(SpiceDB-Delete+mirror+UBP+bitmap)", wall_ns=5_000_000 + t,
                                  extra={"vector_writes": 0}, **base))
        w.write(harness.RawRecord(system="pgvector-UPDATE-acl", wall_ns=900_000_000 + t,
                                  extra={"rows_affected": 65000}, **base))
    w.close()
    return run_id


class TestRawRecords(unittest.TestCase):
    def test_record_has_all_adr0004_fields(self):
        rec = harness.RawRecord("r", "smoke", "sha", True, "H2", "sys", 0, "q0", 123)
        d = json.loads(rec.to_json())
        for f in harness.REQUIRED_FIELDS:
            self.assertIn(f, d)

    def test_run_condition_times_and_scores_each_query(self):
        rng = np.random.default_rng(1)
        X = rng.standard_normal((200, 8)).astype(np.float32)
        qs = _make_queries(X, rng, 5, "H2")
        ctx = RunContext("r", "smoke", "sha", True, "H2")
        recs = list(run_condition(_Half("half", X), qs, 10, 3, ctx))
        self.assertEqual(len(recs), 5)
        for r, q in zip(recs, qs):
            self.assertGreater(r.wall_ns, 0)
            self.assertEqual(r.gt_ids, q.gt_ids)
            self.assertAlmostEqual(r.recall, len(set(r.result_ids) & set(q.gt_ids)) / len(q.gt_ids))
            self.assertEqual(r.distance_computations, 7)
            self.assertEqual(r.seed, 3)


class TestRecompute(unittest.TestCase):
    def test_deterministic_and_check_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            raw = os.path.join(d, "raw")
            _write_synthetic_run(raw)
            a = recompute.dumps_summary(recompute.recompute_summary(raw))
            b = recompute.dumps_summary(recompute.recompute_summary(raw))
            self.assertEqual(a, b)
            out = os.path.join(d, "summary.json")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(recompute.main(["--raw-dir", raw, "--out", out]), 0)
                self.assertEqual(recompute.main(["--raw-dir", raw, "--check", out]), 0)
            s = json.loads(a)
            g = s["hypotheses"]["H2"]["by_condition"]["S=0.2"]
            self.assertAlmostEqual(g["prism-graph-only"]["recall_mean"]["mean"], 1.0)
            self.assertAlmostEqual(g["faiss-hnsw-M16"]["recall_mean"]["mean"], 0.5)
            self.assertEqual(s["verdicts"]["P1a"]["verdict"], "supported")
            self.assertEqual(s["verdicts"]["P4b"]["verdict"], "supported")
            self.assertEqual(s["verdicts"]["P2b"]["verdict"], "untestable")

    def test_tampered_raw_record_fails_check(self):
        with tempfile.TemporaryDirectory() as d:
            raw = os.path.join(d, "raw")
            run_id = _write_synthetic_run(raw)
            out = os.path.join(d, "summary.json")
            with redirect_stdout(io.StringIO()):
                recompute.main(["--raw-dir", raw, "--out", out])
            p = os.path.join(raw, f"{run_id}__H2.jsonl")
            lines = open(p).read().splitlines()
            rec = json.loads(lines[0])
            rec["recall"] = 0.0 if rec["recall"] else 1.0
            lines[0] = json.dumps(rec, sort_keys=True, separators=(",", ":"))
            open(p, "w").write("\n".join(lines) + "\n")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(recompute.main(["--raw-dir", raw, "--check", out]), 1)

    def test_mixed_run_ids_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            raw = os.path.join(d, "raw")
            _write_synthetic_run(raw, "v2-test-a")
            _write_synthetic_run(raw, "v2-test-b")
            with self.assertRaises(ValueError):
                recompute.recompute_summary(raw)
            self.assertEqual(recompute.recompute_summary(raw, "v2-test-a")["run_id"], "v2-test-a")

    def test_committed_summary_matches_raw_exactly(self):
        """results/v2/summary.json must be exactly reproducible from results/v2/raw."""
        raw = os.path.join(REPO_ROOT, "results", "v2", "raw")
        summ = os.path.join(REPO_ROOT, "results", "v2", "summary.json")
        if not (os.path.isdir(raw) and os.path.exists(summ)):
            self.skipTest("confirmatory raw records / summary.json not produced yet")
        with open(summ, "r", encoding="utf-8") as f:
            committed = f.read()
        self.assertEqual(committed, recompute.dumps_summary(recompute.recompute_summary(raw)))


class TestFreezeAndAudits(unittest.TestCase):
    def test_frozen_files_match_freeze_md(self):
        st = harness.freeze_status()
        self.assertEqual(st["n_files"], 5)
        self.assertTrue(st["match"], st["mismatches"])

    def test_brake_scripts_have_no_literal_scores_or_verdicts(self):
        pat = re.compile(r"(STRONG ACCEPT|ACCEPT\b|\b\d{1,3}\.\d+\s*/\s*100|\b\d\.\d\s*/\s*10\b|"
                         r"\"(faithfulness|conciseness|readability|aesthetics)\"\s*:\s*\d)", re.I)
        for script in ("run_prism_paperviz_audit.py", "run_prism_scholarpeer_review.py"):
            with open(os.path.join(REPO_ROOT, script), "r", encoding="utf-8") as f:
                src = f.read()
            self.assertIsNone(pat.search(src), f"{script} contains a literal score/verdict")

    def test_init_prism_ann_refuses_overwrite_without_force(self):
        import research_factory as rf

        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "CONTEXT.md"), "w") as f:
                f.write("sentinel")
            with redirect_stdout(io.StringIO()):
                ok = rf.init_prism_ann(root=d, force=False)
            self.assertFalse(ok)
            with open(os.path.join(d, "CONTEXT.md")) as f:
                self.assertEqual(f.read(), "sentinel")
            with redirect_stdout(io.StringIO()):
                self.assertTrue(rf.init_prism_ann(root=d, force=True))
            with open(os.path.join(d, "CONTEXT.md")) as f:
                self.assertNotEqual(f.read(), "sentinel")

    def test_frozen_files_match_freeze_v3_and_v3_1_md(self):
        from bench import harness_v3, recompute_v3_1

        st3 = harness_v3.freeze_v3_status()
        self.assertEqual(st3["n_files"], 7)
        self.assertTrue(st3["match"], st3["mismatches"])

        st31 = recompute_v3_1.freeze_v3_1_status()
        self.assertEqual(st31["n_files"], 8)
        self.assertTrue(st31["match"], st31["mismatches"])

    def test_v3_and_reviewer_audit_summaries_match_raw_exactly(self):
        from bench import recompute_v3, recompute_v3_1, recompute_v3_2

        raw_v3 = os.path.join(REPO_ROOT, "results", "v3", "raw")
        sum_v3 = os.path.join(REPO_ROOT, "results", "v3", "summary.json")
        if os.path.isdir(raw_v3) and os.path.exists(sum_v3):
            with open(sum_v3, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), recompute.dumps_summary(recompute_v3.recompute_v3_summary(raw_v3)))

        raw_v31 = os.path.join(REPO_ROOT, "results", "v3_1_audit", "raw", "v3_1_reviewer_audit.jsonl")
        sum_v31 = os.path.join(REPO_ROOT, "results", "v3", "reviewer_audit_v3_1.json")
        if os.path.exists(raw_v31) and os.path.exists(sum_v31):
            with open(sum_v31, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), recompute.dumps_summary(recompute_v3_1.recompute_v3_1_summary(raw_v31)))

        raw_v32 = os.path.join(REPO_ROOT, "results", "v3_2_audit", "raw", "v3_2_reviewer_audit.jsonl")
        sum_v32 = os.path.join(REPO_ROOT, "results", "v3", "reviewer_audit_v3_2.json")
        if os.path.exists(raw_v32) and os.path.exists(sum_v32):
            with open(sum_v32, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), recompute.dumps_summary(recompute_v3_2.recompute_v3_2_summary(raw_v32)))

    def test_theorem2_multiparent_diamond_dag_deny_dominates_grant(self):
        """Theorem 2: UBP achieves 0 FP and 0 FN on multi-parent diamond DAGs with conflicting GRANT/DENY paths."""
        from src.modules.prism_ann.ubp_resolver import ZanzibarAuthGraph

        g = ZanzibarAuthGraph(branching_factor=3, depth=3)
        for nid, lvl in (("org_root", 0), ("dept_A", 1), ("dept_B", 1),
                         ("proj_clean", 2), ("proj_shared", 2), ("proj_b_only", 2)):
            g.add_node(nid, depth_level=lvl, is_leaf=False)
        for doc_id in ("doc_clean_1", "doc_clean_2", "doc_shared_1", "doc_b_1", "doc_multiparent_conflict"):
            g.add_node(doc_id, depth_level=3, is_leaf=True)

        # Diamond topology: org_root -> {dept_A, dept_B}; both dept_A and dept_B are parents of proj_shared!
        g.add_hierarchy_edge("org_root", "dept_A")
        g.add_hierarchy_edge("org_root", "dept_B")
        g.add_hierarchy_edge("dept_A", "proj_clean")
        g.add_hierarchy_edge("dept_A", "proj_shared")
        g.add_hierarchy_edge("dept_B", "proj_shared")  # secondary parent edge creating diamond
        g.add_hierarchy_edge("dept_B", "proj_b_only")
        # Documents with single and multiple container parents
        g.add_hierarchy_edge("proj_clean", "doc_clean_1")
        g.add_hierarchy_edge("proj_clean", "doc_clean_2")
        g.add_hierarchy_edge("proj_shared", "doc_shared_1")
        g.add_hierarchy_edge("proj_b_only", "doc_b_1")
        # Multi-parent document attached to both proj_clean (granted) and proj_b_only (denied)
        g.add_hierarchy_edge("proj_clean", "doc_multiparent_conflict")
        g.add_hierarchy_edge("proj_b_only", "doc_multiparent_conflict")

        # Principal u1 has GRANT on dept_A and DENY on dept_B:
        # Under Deny-Dominates-Grant, proj_shared and doc_multiparent_conflict are reachable from dept_B (DENY),
        # so ONLY {doc_clean_1, doc_clean_2} may be authorized!
        g.grant_access("u1", "dept_A")
        g.add_deny_exclusion("u1", "dept_B")

        oracle_docs = g.lookup_resources_leaf("u1")
        self.assertEqual(oracle_docs, {"doc_clean_1", "doc_clean_2"})

        ubp_res = g.upward_boundary_prune("u1")
        ubp_docs = (g.get_descendants(ubp_res.tokens_pos) - g.get_descendants(ubp_res.tokens_neg)) & g.leaf_documents
        self.assertEqual(ubp_docs, oracle_docs)
        self.assertEqual(ubp_res.tokens_pos, {"dept_A"})
        self.assertIn("dept_B", ubp_res.tokens_neg)

        # Case B: Principal u2 has GRANT on org_root and DENY on diamond child proj_shared
        # Both dept_A and dept_B are ancestors of proj_shared, so both are tainted and split!
        g.grant_access("u2", "org_root")
        g.add_deny_exclusion("u2", "proj_shared")
        oracle_u2 = g.lookup_resources_leaf("u2")
        self.assertEqual(oracle_u2, {"doc_clean_1", "doc_clean_2", "doc_b_1", "doc_multiparent_conflict"})
        ubp_u2 = g.upward_boundary_prune("u2")
        ubp_u2_docs = (g.get_descendants(ubp_u2.tokens_pos) - g.get_descendants(ubp_u2.tokens_neg)) & g.leaf_documents
        self.assertEqual(ubp_u2_docs, oracle_u2)
        self.assertEqual(ubp_u2.tainted_containers, {"org_root", "dept_A", "dept_B"})
        self.assertEqual(ubp_u2.tokens_pos, {"proj_clean", "proj_b_only"})

    def test_governance_and_gsd_alignment_100_percent(self):
        import research_factory as rf

        report = rf.validate_gsd_planning()
        self.assertTrue(report["aligned"], report["errors"])
        self.assertEqual(report["phase_count"], 22)
        self.assertEqual(report["completed_phases"], 22)
        self.assertEqual(report["progress_percent"], 100)
        with redirect_stdout(io.StringIO()):
            self.assertTrue(rf.verify_governance())

    def test_theorem2_adversarial_transitivity_and_zedtoken_snapshot_consistency(self):
        """Adversarial verification of Theorem 2 reachability transitivity and Corollary 1 ZedToken monotonicity."""
        from src.modules.prism_ann.ubp_resolver import ZanzibarAuthGraph

        g = ZanzibarAuthGraph(branching_factor=4, depth=4)
        for nid, lvl in (
            ("root", 0),
            ("lob_1", 1), ("lob_2", 1),
            ("dept_1", 2), ("dept_2", 2), ("dept_shared", 2),
            ("folder_clean", 3), ("folder_tainted", 3), ("folder_denied_via_d2", 3),
        ):
            g.add_node(nid, depth_level=lvl, is_leaf=False)
        for doc, lvl in (("doc_ok", 4), ("doc_blocked_direct", 4), ("doc_blocked_transitive", 4)):
            g.add_node(doc, depth_level=lvl, is_leaf=True)

        # Build multi-parent DAG with transitive diamond path:
        # root -> lob_1 -> dept_1 -> {folder_clean, folder_tainted, folder_denied_via_d2}
        # root -> lob_2 -> dept_2 -> dept_shared -> folder_denied_via_d2 -> doc_blocked_transitive
        g.add_hierarchy_edge("root", "lob_1")
        g.add_hierarchy_edge("root", "lob_2")
        g.add_hierarchy_edge("lob_1", "dept_1")
        g.add_hierarchy_edge("lob_2", "dept_2")
        g.add_hierarchy_edge("dept_2", "dept_shared")
        g.add_hierarchy_edge("dept_1", "folder_clean")
        g.add_hierarchy_edge("dept_1", "folder_tainted")
        g.add_hierarchy_edge("dept_1", "folder_denied_via_d2")
        g.add_hierarchy_edge("dept_shared", "folder_denied_via_d2")  # multi-parent diamond join
        g.add_hierarchy_edge("folder_clean", "doc_ok")
        g.add_hierarchy_edge("folder_tainted", "doc_blocked_direct")
        g.add_hierarchy_edge("folder_denied_via_d2", "doc_blocked_transitive")

        # Redundant positive grants (lob_1 AND descendant folder_denied_via_d2) + denies on lob_2 and doc_blocked_direct
        z1 = g.grant_access("u_adv", "lob_1")
        z2 = g.grant_access("u_adv", "folder_denied_via_d2")
        z3 = g.add_deny_exclusion("u_adv", "lob_2")
        z4 = g.add_deny_exclusion("u_adv", "doc_blocked_direct")
        self.assertTrue(z1 < z2 < z3 < z4)

        # Even though u_adv holds a direct positive grant on folder_denied_via_d2,
        # lob_2 (DENY) -> dept_2 -> dept_shared -> folder_denied_via_d2 -> doc_blocked_transitive
        # transitively denies doc_blocked_transitive under Deny-Dominates-Grant!
        oracle_pre = g.lookup_resources_leaf("u_adv")
        self.assertEqual(oracle_pre, {"doc_ok"})
        ubp_pre = g.upward_boundary_prune("u_adv")
        ubp_docs_pre = (g.get_descendants(ubp_pre.tokens_pos) - g.get_descendants(ubp_pre.tokens_neg)) & g.leaf_documents
        self.assertEqual(ubp_docs_pre, oracle_pre)
        self.assertEqual(ubp_pre.zed_token, z4)

        # Now execute O(1) subtree unlink (Corollary 1) at ZedToken zeta_rev:
        zeta_rev = g.remove_hierarchy_edge("dept_1", "folder_clean")
        self.assertGreater(zeta_rev, ubp_pre.zed_token)
        ubp_post = g.upward_boundary_prune("u_adv")
        self.assertEqual(ubp_post.zed_token, zeta_rev)
        ubp_docs_post = (g.get_descendants(ubp_post.tokens_pos) - g.get_descendants(ubp_post.tokens_neg)) & g.leaf_documents
        self.assertEqual(ubp_docs_post, set())
        self.assertEqual(g.lookup_resources_leaf("u_adv"), set())

    def test_dynamic_dag_priority_finding_1_postindex_add_edge_with_deny(self):
        """Priority Finding 1: Post-index add_hierarchy_edge(B, D) with deny on B must leak 0 docs."""
        from src.modules.prism_ann_v3.dynamic_dag_ubp import (
            DynamicMultiParentAuthGraph,
            DynamicPrismANNIndex,
        )

        g = DynamicMultiParentAuthGraph(branching_factor=4, depth=2)
        g.add_node("A", depth_level=0, is_leaf=False)
        g.add_node("B", depth_level=0, is_leaf=False)
        g.add_node("D", depth_level=1, is_leaf=True)
        g.add_hierarchy_edge("A", "D")
        g.grant_access("u", "A")
        g.add_deny_exclusion("u", "B")

        rng = np.random.default_rng(7)
        X = rng.standard_normal((4, 16)).astype(np.float32)
        X /= np.linalg.norm(X, axis=1, keepdims=True)
        idx = DynamicPrismANNIndex(
            auth_graph=g,
            raw_vectors=X,
            leaf_doc_ids=["D", "D", "D", "D"],
            ancestor_lineages=[["A", "D"] for _ in range(4)],
            meaning_magnet_ids=["m0", "m0", "m0", "m0"],
            M=4,
            m_bridge=2,
            ef_construction=16,
            ef_search=16,
            seed=7,
        )
        # Before adding edge B -> D, user u sees D
        res_pre = idx.search(X[0], principal_id="u", k=4)
        self.assertEqual(len(res_pre.top_k_ids), 4)

        # Dynamically add denied parent B -> D after index construction
        zt_after = idx.add_hierarchy_edge("B", "D")
        self.assertEqual(g.lookup_resources_leaf("u"), set())
        res_post = idx.search(X[0], principal_id="u", k=4, zed_token=zt_after)
        self.assertEqual(res_post.top_k_ids, [])

    def test_dynamic_dag_priority_finding_2_shared_child_unlink_preserves_surviving_path(self):
        """Priority Finding 2: Unlinking A->C on A->C<-B preserves access via B->C; snapshot pins isolate pre-unlink reads."""
        from src.modules.prism_ann_v3.dynamic_dag_ubp import (
            DynamicMultiParentAuthGraph,
            DynamicPrismANNIndex,
        )

        g = DynamicMultiParentAuthGraph(branching_factor=4, depth=2)
        for nid in ("A", "B"):
            g.add_node(nid, depth_level=0, is_leaf=False)
        g.add_node("C", depth_level=1, is_leaf=True)
        g.add_hierarchy_edge("A", "C")
        g.add_hierarchy_edge("B", "C")
        g.grant_access("u", "B")

        rng = np.random.default_rng(11)
        X = rng.standard_normal((4, 16)).astype(np.float32)
        X /= np.linalg.norm(X, axis=1, keepdims=True)
        idx = DynamicPrismANNIndex(
            auth_graph=g,
            raw_vectors=X,
            leaf_doc_ids=["C", "C", "C", "C"],
            ancestor_lineages=[["A", "B", "C"] for _ in range(4)],
            meaning_magnet_ids=["m0", "m0", "m0", "m0"],
            M=4,
            m_bridge=2,
            ef_construction=16,
            ef_search=16,
            seed=11,
        )
        zt_pre = g.zed_token

        # Unlink A -> C; B -> C survives, so C must remain accessible
        zt_unlink = idx.remove_hierarchy_edge("A", "C")
        self.assertEqual(g.lookup_resources_leaf("u"), {"C"})
        res_unlink = idx.search(X[0], principal_id="u", k=4, zed_token=zt_unlink)
        self.assertEqual(len(res_unlink.top_k_ids), 4)

        # Grant only on A (revoking B): after A->C unlink, u at zt_pre saw A->C if A granted,
        # and after zt_unlink no path through A reaches C.
        g.revoke_access("u", "B")
        zt_grant_a = g.grant_access("u", "A")
        idx.sync()
        self.assertEqual(g.lookup_resources_leaf("u"), set())
        self.assertEqual(idx.search(X[0], principal_id="u", k=4, zed_token=zt_grant_a).top_k_ids, [])

        # Whole-subtree quarantine (decommission_subtree) excludes C across all parents
        g.grant_access("u", "B")
        zt_regrant_b = idx.sync().zed_token
        self.assertEqual(len(idx.search(X[0], principal_id="u", k=4, zed_token=zt_regrant_b).top_k_ids), 4)
        zt_decomm = idx.decommission_subtree("C")
        self.assertEqual(g.lookup_resources_leaf("u"), set())
        self.assertEqual(idx.search(X[0], principal_id="u", k=4, zed_token=zt_decomm).top_k_ids, [])
        # Historical ZedToken pinned before decommission retains pre-decommission view under at_exact_snapshot
        self.assertEqual(
            len(idx.search(X[0], principal_id="u", k=4, zed_token=zt_regrant_b, consistency_mode="at_exact_snapshot").top_k_ids),
            4,
        )

    def test_freeze_v3_3_and_recompute_v3_3_parity(self):
        from bench.recompute_v3_3 import freeze_v3_3_status, recompute_v3_3_summary

        fz = freeze_v3_3_status()
        self.assertTrue(fz["match"], fz["mismatches"])
        self.assertEqual(fz["n_files"], 9)
        committed_path = os.path.join(REPO_ROOT, "results", "v3", "reviewer_audit_v3_3.json")
        raw_path = os.path.join(REPO_ROOT, "results", "v3_3_audit", "raw", "v3_3_reviewer_audit.jsonl")
        with open(committed_path, "r", encoding="utf-8") as f:
            committed = f.read()
        self.assertEqual(recompute.dumps_summary(recompute_v3_3_summary(raw_path)), committed)

    def test_dynamic_dag_same_parent_alternate_path_and_upstream_propagation(self):
        """P->C and P->X->C under upstream A->P: unlinking P->C preserves C in B_P & B_A; unlinking X->C removes C upstream."""
        from src.modules.prism_ann_v3.dynamic_dag_ubp import (
            DynamicMultiParentAuthGraph,
            DynamicPrismANNIndex,
        )

        g = DynamicMultiParentAuthGraph(branching_factor=4, depth=3)
        for nid, lvl in (("A", 0), ("P", 1), ("X", 2)):
            g.add_node(nid, depth_level=lvl, is_leaf=False)
        g.add_node("doc_c", depth_level=3, is_leaf=True)
        g.add_hierarchy_edge("A", "P")
        g.add_hierarchy_edge("P", "doc_c")
        g.add_hierarchy_edge("P", "X")
        g.add_hierarchy_edge("X", "doc_c")
        g.grant_access("u_up", "A")
        g.grant_access("u_p", "P")

        rng = np.random.default_rng(19)
        X = rng.standard_normal((4, 16)).astype(np.float32)
        X /= np.linalg.norm(X, axis=1, keepdims=True)
        idx = DynamicPrismANNIndex(
            auth_graph=g,
            raw_vectors=X,
            leaf_doc_ids=["doc_c", "doc_c", "doc_c", "doc_c"],
            ancestor_lineages=[["A", "P", "X", "doc_c"] for _ in range(4)],
            meaning_magnet_ids=["m0", "m0", "m0", "m0"],
            M=4, m_bridge=2, ef_construction=16, ef_search=16, seed=19,
        )

        # Unlink direct P -> doc_c; alternate path P -> X -> doc_c survives for BOTH P and upstream A
        zt1 = idx.remove_hierarchy_edge("P", "doc_c")
        self.assertEqual(g.lookup_resources_leaf("u_p"), {"doc_c"})
        self.assertEqual(g.lookup_resources_leaf("u_up"), {"doc_c"})
        self.assertEqual(len(idx.search(X[0], "u_p", k=4, zed_token=zt1).top_k_ids), 4)
        self.assertEqual(len(idx.search(X[0], "u_up", k=4, zed_token=zt1).top_k_ids), 4)
        snap1 = idx.vcorpus.get_snapshot(g, zed_token=zt1)
        self.assertEqual(snap1.token_bitmaps["P"].popcount(), 4)
        self.assertEqual(snap1.token_bitmaps["A"].popcount(), 4)

        # Now unlink X -> doc_c: upstream A and P must both drop doc_c (no stale ancestor retention)
        zt2 = idx.remove_hierarchy_edge("X", "doc_c")
        self.assertEqual(g.lookup_resources_leaf("u_up"), set())
        self.assertEqual(idx.search(X[0], "u_up", k=4, zed_token=zt2).top_k_ids, [])
        snap2 = idx.vcorpus.get_snapshot(g, zed_token=zt2)
        self.assertNotIn("A", snap2.token_bitmaps)
        self.assertNotIn("P", snap2.token_bitmaps)

    def test_dynamic_dag_postindex_add_grant_edge_no_stale_omission(self):
        """A -> D; add B -> D; grant B -> D becomes immediately accessible with 0 stale-posting omissions."""
        from src.modules.prism_ann_v3.dynamic_dag_ubp import (
            DynamicMultiParentAuthGraph,
            DynamicPrismANNIndex,
        )

        g = DynamicMultiParentAuthGraph(branching_factor=4, depth=2)
        g.add_node("A", depth_level=0, is_leaf=False)
        g.add_node("B", depth_level=0, is_leaf=False)
        g.add_node("doc_d", depth_level=1, is_leaf=True)
        g.add_hierarchy_edge("A", "doc_d")

        rng = np.random.default_rng(23)
        X = rng.standard_normal((4, 16)).astype(np.float32)
        X /= np.linalg.norm(X, axis=1, keepdims=True)
        idx = DynamicPrismANNIndex(
            auth_graph=g,
            raw_vectors=X,
            leaf_doc_ids=["doc_d", "doc_d", "doc_d", "doc_d"],
            ancestor_lineages=[["A", "doc_d"] for _ in range(4)],
            meaning_magnet_ids=["m0", "m0", "m0", "m0"],
            M=4, m_bridge=2, ef_construction=16, ef_search=16, seed=23,
        )
        self.assertEqual(idx.search(X[0], "u", k=4).top_k_ids, [])

        # Dynamically add B -> doc_d and grant B to u
        idx.add_hierarchy_edge("B", "doc_d")
        zt_g = g.grant_access("u", "B")
        idx.sync()
        self.assertEqual(g.lookup_resources_leaf("u"), {"doc_d"})
        self.assertEqual(len(idx.search(X[0], "u", k=4, zed_token=zt_g).top_k_ids), 4)

    def test_dynamic_dag_snapshot_consistency_fail_closed_and_fallback(self):
        """Expired at_exact_snapshot & unsynced at_least_as_fresh fail closed or fall back safely to live leaf oracle."""
        from src.modules.prism_ann_v3.dynamic_dag_ubp import (
            DynamicMultiParentAuthGraph,
            DynamicPrismANNIndex,
            StaleOrMissingSnapshotError,
        )

        g = DynamicMultiParentAuthGraph(branching_factor=4, depth=2)
        g.add_node("A", depth_level=0, is_leaf=False)
        g.add_node("B", depth_level=0, is_leaf=False)
        g.add_node("doc_1", depth_level=1, is_leaf=True)
        g.add_hierarchy_edge("A", "doc_1")
        g.grant_access("u", "A")
        g.add_deny_exclusion("u", "B")

        rng = np.random.default_rng(29)
        X = rng.standard_normal((4, 16)).astype(np.float32)
        X /= np.linalg.norm(X, axis=1, keepdims=True)
        idx = DynamicPrismANNIndex(
            auth_graph=g,
            raw_vectors=X,
            leaf_doc_ids=["doc_1", "doc_1", "doc_1", "doc_1"],
            ancestor_lineages=[["A", "doc_1"] for _ in range(4)],
            meaning_magnet_ids=["m0", "m0", "m0", "m0"],
            M=4, m_bridge=2, ef_construction=16, ef_search=16, seed=29,
        )
        zt_initial = idx.sync().zed_token
        zt_mut = idx.add_hierarchy_edge("B", "doc_1")

        # Pre-mutation exact snapshot works before eviction, then fails closed after eviction
        self.assertEqual(len(idx.search(X[0], "u", k=4, zed_token=zt_initial, consistency_mode="at_exact_snapshot").top_k_ids), 4)
        evicted = idx.vcorpus.evict_snapshots_before(zt_mut)
        self.assertGreaterEqual(evicted, 1)
        with self.assertRaises(StaleOrMissingSnapshotError):
            idx.search(X[0], "u", k=4, zed_token=zt_initial, consistency_mode="at_exact_snapshot", on_unavailable="fail_closed")

        # Unsynced graph mutation with auto_sync=False: fail_closed refuses, safe_leaf_fallback returns exact live oracle!
        g.remove_hierarchy_edge("B", "doc_1")
        with self.assertRaises(StaleOrMissingSnapshotError):
            idx.search(X[0], "u", k=4, consistency_mode="at_least_as_fresh", on_unavailable="fail_closed", auto_sync=False)
        res_fb = idx.search(X[0], "u", k=4, consistency_mode="at_least_as_fresh", on_unavailable="safe_leaf_fallback", auto_sync=False)
        self.assertEqual(len(res_fb.top_k_ids), 4)
        # Future un-committed token always fails closed even with safe_leaf_fallback
        with self.assertRaises(StaleOrMissingSnapshotError):
            idx.search(X[0], "u", k=4, zed_token=g.zed_token + 99, consistency_mode="at_least_as_fresh", on_unavailable="safe_leaf_fallback")

    def test_v3_4_atomic_snapshot_eliminates_sync_race_and_preserves_monotonic_order(self):
        """R12a unit proof: frozen v3.3 tears under mid-sync mutations while v3.4 AtomicVersionedLineageCorpus stays 100% consistent."""
        import threading
        from src.modules.prism_ann_v3.consistent_snapshot_index import (
            ConsistentDynamicPrismANNIndex,
        )
        from src.modules.prism_ann_v3.dynamic_dag_ubp import (
            DynamicMultiParentAuthGraph,
            VersionedLineageCorpus,
        )

        def _make_graph():
            g = DynamicMultiParentAuthGraph(branching_factor=3, depth=2)
            for cid in ("A", "B", "C"):
                g.add_node(cid, depth_level=0, is_leaf=False)
            for did in ("doc_0", "doc_1"):
                g.add_node(did, depth_level=1, is_leaf=True)
            g.add_hierarchy_edge("A", "doc_0")
            g.add_hierarchy_edge("B", "doc_1")
            g.grant_access("u", "A")
            g.add_deny_exclusion("u", "C")
            return g

        rng = np.random.default_rng(1212)
        X = rng.standard_normal((6, 16)).astype(np.float32)
        X /= np.linalg.norm(X, axis=1, keepdims=True)
        leaf_docs = ["doc_0", "doc_0", "doc_0", "doc_1", "doc_1", "doc_1"]

        # 1. Confirm frozen v3.3 VersionedLineageCorpus tears under mid-sync mutations
        class _Probe(VersionedLineageCorpus):
            def _compute_token_bitmaps(self, auth_graph):
                if getattr(self, "_armed", False):
                    self._armed = False
                    auth_graph.add_hierarchy_edge("C", "doc_0")
                    bm = super()._compute_token_bitmaps(auth_graph)
                    auth_graph.add_hierarchy_edge("A", "doc_1")
                    return bm
                return super()._compute_token_bitmaps(auth_graph)

        g_old = _make_graph()
        c_old = _Probe(g_old, X, leaf_doc_ids=leaf_docs)
        g_old.add_hierarchy_edge("B", "doc_0")
        c_old._armed = True
        s_old = c_old.sync_to_revision(g_old)
        self.assertNotEqual(s_old.zed_token, s_old.auth_snapshot.zed_token)

        # 2. Confirm v3.4 AtomicVersionedLineageCorpus stays 100% consistent under identical double injection
        g_new = _make_graph()
        idx_new = ConsistentDynamicPrismANNIndex(
            g_new, X, leaf_doc_ids=leaf_docs, M=4, m_bridge=2, ef_construction=16, ef_search=16, seed=12,
        )
        g_new.add_hierarchy_edge("B", "doc_0")
        s_fix = idx_new.sync(
            on_after_capture=lambda _z, _h: g_new.add_hierarchy_edge("C", "doc_0"),
            on_after_postings=lambda _z, _h: g_new.add_hierarchy_edge("A", "doc_1"),
        )
        chk = idx_new.vcorpus.verify_snapshot_internal_consistency(s_fix)
        self.assertTrue(chk["consistent"], f"Expected atomic snapshot consistency: {chk}")

        # 3. Monotonic ordering: slower older publisher never overwrites newer _latest_snapshot
        captured = threading.Event()
        newer_done = threading.Event()
        box = []

        def _slow_pub():
            box.append(
                idx_new.sync(
                    on_after_capture=lambda _z, _h: (captured.set(), newer_done.wait(timeout=5.0))
                )
            )

        t = threading.Thread(target=_slow_pub)
        t.start()
        self.assertTrue(captured.wait(timeout=5.0))
        g_new.grant_access("u", "B")
        s_newer = idx_new.sync()
        newer_done.set()
        t.join(timeout=5.0)
        self.assertEqual(idx_new.vcorpus._latest_snapshot.zed_token, s_newer.zed_token)
        self.assertLess(box[0].zed_token, s_newer.zed_token)

    def test_v3_4_opaque_external_zedtoken_lag_fail_closed_and_authoritative_fallback(self):
        """R12b unit proof: un-ingested external ZedTokens fail closed or use authoritative external lookup, never stale mirror."""
        from src.modules.prism_ann_v3.consistent_snapshot_index import (
            ConsistentDynamicPrismANNIndex,
            StaleOrMissingSnapshotError,
        )
        from src.modules.prism_ann_v3.dynamic_dag_ubp import DynamicMultiParentAuthGraph

        g = DynamicMultiParentAuthGraph(branching_factor=3, depth=2)
        g.add_node("A", depth_level=0, is_leaf=False)
        g.add_node("doc_0", depth_level=1, is_leaf=True)
        g.add_node("doc_1", depth_level=1, is_leaf=True)
        g.add_hierarchy_edge("A", "doc_0")
        g.add_hierarchy_edge("A", "doc_1")
        g.grant_access("u", "A")

        rng = np.random.default_rng(1213)
        X = rng.standard_normal((4, 16)).astype(np.float32)
        X /= np.linalg.norm(X, axis=1, keepdims=True)
        leaf_docs = ["doc_0", "doc_0", "doc_1", "doc_1"]

        # Simulated external SpiceDB state ahead of mirror (doc_1 revoked at ext_zt_1)
        ext_state = {"ext_zt_0": {"doc_0", "doc_1"}, "ext_zt_1": {"doc_0"}}

        def _mock_spicedb(principal: str, mode: str, ext_zt: str):
            return set(ext_state[ext_zt]), ext_zt

        idx = ConsistentDynamicPrismANNIndex(
            g, X, leaf_doc_ids=leaf_docs,
            initial_external_zed_token="ext_zt_0",
            external_auth_lookup=_mock_spicedb,
            M=4, m_bridge=2, ef_construction=16, ef_search=16, seed=13,
        )

        # Synced ext_zt_0 succeeds via fast UBP snapshot
        r0 = idx.search_with_metadata(X[0], "u", k=4, external_zed_token="ext_zt_0", consistency_mode="at_exact_snapshot")
        self.assertIsNone(r0.fallback_used)
        self.assertEqual({idx.vcorpus.z_leaf_doc_ids[i] for i in r0.result.top_k_ids}, {"doc_0", "doc_1"})

        # Mirror lags behind ext_zt_1 -> fail_closed MUST refuse!
        with self.assertRaises(StaleOrMissingSnapshotError):
            idx.search_with_metadata(X[0], "u", k=4, external_zed_token="ext_zt_1", consistency_mode="at_least_as_fresh", on_unavailable="fail_closed")

        # Authoritative spicedb_leaf_fallback queries external provider (NOT stale mirror!) and excludes doc_1
        r1 = idx.search_with_metadata(X[0], "u", k=4, external_zed_token="ext_zt_1", consistency_mode="at_least_as_fresh", on_unavailable="spicedb_leaf_fallback")
        self.assertEqual(r1.fallback_used, "spicedb_leaf_fallback")
        self.assertEqual({idx.vcorpus.z_leaf_doc_ids[i] for i in r1.result.top_k_ids}, {"doc_0"})

        # Without an external provider, spicedb_leaf_fallback MUST fail closed rather than consulting stale local mirror
        idx_no_ext = ConsistentDynamicPrismANNIndex(
            g.snapshot_graph_copy(), X, leaf_doc_ids=leaf_docs,
            initial_external_zed_token="ext_zt_0",
            external_auth_lookup=None,
            M=4, m_bridge=2, ef_construction=16, ef_search=16, seed=14,
        )
        with self.assertRaises(StaleOrMissingSnapshotError):
            idx_no_ext.search_with_metadata(X[0], "u", k=4, external_zed_token="ext_zt_1", consistency_mode="at_least_as_fresh", on_unavailable="spicedb_leaf_fallback")

    def test_v3_4_recompute_parity(self):
        """Verify results/v3/reviewer_audit_v3_4.json matches recompute_v3_4.py & FREEZE_v3_4.md (10/10)."""
        from bench.recompute import dumps_summary
        from bench.recompute_v3_4 import freeze_v3_4_status, recompute_v3_4_summary

        f34 = freeze_v3_4_status()
        self.assertTrue(f34["match"], f"FREEZE_v3_4 mismatch: {f34}")
        self.assertEqual(f34["n_files"], 10)
        summary_path = os.path.join(REPO_ROOT, "results", "v3", "reviewer_audit_v3_4.json")
        raw_path = os.path.join(REPO_ROOT, "results", "v3_4_audit", "raw", "v3_4_reviewer_audit.jsonl")
        self.assertTrue(os.path.exists(summary_path))
        self.assertTrue(os.path.exists(raw_path))
        recomp = recompute_v3_4_summary(raw_path)
        with open(summary_path, "r", encoding="utf-8") as f:
            stored = f.read()
        self.assertEqual(dumps_summary(recomp), stored)
        self.assertFalse(recomp["git_dirty"])
        self.assertEqual(recomp["verdicts"]["PR12a"]["verdict"], "supported")
        self.assertEqual(recomp["verdicts"]["PR12b"]["verdict"], "supported")
        self.assertEqual(recomp["verdicts"]["PR12c"]["verdict"], "supported")


if __name__ == "__main__":
    unittest.main()
