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


if __name__ == "__main__":
    unittest.main()
