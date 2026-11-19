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


if __name__ == "__main__":
    unittest.main()
