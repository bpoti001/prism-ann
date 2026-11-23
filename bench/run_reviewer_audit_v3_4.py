#!/usr/bin/env python3
"""
Prism-ANN v3.4 Reviewer Audit Suite (Experiment R12: Concurrency & Unsynced Mirror)
===================================================================================
Pre-registered in `experiments/v3/PROTOCOL_v3_4.md` (strictly additive; preserves
all frozen prior datasets v2, v3, v3.1, v3.2, and v3.3 untouched):

  R12a: Deterministic Snapshot-Publication Race Injection (Frozen v3.3 Control vs.
        v3.4 Atomic Fix) — injects mutations immediately after revision capture /
        before posting computation AND immediately after posting computation /
        before copying authorization state, plus concurrent out-of-order
        multi-publisher monotonic-ordering trials.
  R12b: Live Native SpiceDB v1.57.1 Unsynced-Mirror & Opaque-ZedToken Matrix
        (10 scenarios) — mutates live SpiceDB externally while the local mirror
        lags, verifying fail-closed StaleOrMissingSnapshotError refusal, live
        SpiceDB LookupResources authoritative fallback (`spicedb_leaf_fallback`),
        missing-provider guard, `at_least_as_fresh` newer-revision serving vs.
        `at_exact_snapshot` GC expiration, and catch-up resync.
  R12c: Multi-Threaded Concurrent DAG Mutation, Atomic Snapshot Publication, and
        Public `ConsistentDynamicPrismANNIndex.search_with_metadata()` Stress
        (4 writer/publisher threads + 4 reader threads, >=1,000 reads).

Usage:
  /Users/tejap/memory_paper/.venv-bench/bin/python -u -m bench.run_reviewer_audit_v3_4
"""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from authzed.api.v1 import (
    CheckPermissionRequest,
    CheckPermissionResponse,
    Consistency,
    DeleteRelationshipsRequest,
    LookupResourcesRequest,
    ObjectReference,
    RelationshipFilter,
    RelationshipUpdate,
    SubjectFilter,
    SubjectReference,
    ZedToken,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from bench.engines import SpiceDBService, _node_type, _rel  # noqa: E402
from bench.harness import git_sha  # noqa: E402
from bench.harness_v3 import freeze_v3_status  # noqa: E402
from bench.recompute import dumps_summary  # noqa: E402
from bench.recompute_v3_1 import freeze_v3_1_status  # noqa: E402
from bench.recompute_v3_3 import freeze_v3_3_status  # noqa: E402
from bench.recompute_v3_4 import freeze_v3_4_status, recompute_v3_4_summary  # noqa: E402
from bench.run_reviewer_audit_v3_1 import RawAuditLogger, _repo_is_dirty  # noqa: E402
from bench.run_reviewer_audit_v3_2 import _dag_oracle_authorized_leaves  # noqa: E402
from src.modules.prism_ann_v3.consistent_snapshot_index import (  # noqa: E402
    AtomicRevisionSnapshot,
    AtomicVersionedLineageCorpus,
    ConsistentDynamicPrismANNIndex,
)
from src.modules.prism_ann_v3.dynamic_dag_ubp import (  # noqa: E402
    DynamicMultiParentAuthGraph,
    StaleOrMissingSnapshotError,
    VersionedLineageCorpus,
)

RAW_OUT_PATH = os.path.join(REPO_ROOT, "results", "v3_4_audit", "raw", "v3_4_reviewer_audit.jsonl")
SUMMARY_OUT_PATH = os.path.join(REPO_ROOT, "results", "v3", "reviewer_audit_v3_4.json")


def _spicedb_check_permission(
    client, doc_id: str, principal_id: str, consistency: Consistency
) -> bool:
    resp = client.CheckPermission(
        CheckPermissionRequest(
            consistency=consistency,
            resource=ObjectReference(object_type="document", object_id=doc_id),
            permission="view",
            subject=SubjectReference(object=ObjectReference(object_type="user", object_id=principal_id)),
        )
    )
    return resp.permissionship == CheckPermissionResponse.PERMISSIONSHIP_HAS_PERMISSION


def _spicedb_lookup_docs_with_revision(
    client, principal_id: str, consistency: Consistency
) -> Tuple[Set[str], Optional[str]]:
    """
    Executes SpiceDB LookupResources and returns `(doc_ids, evaluated_zed_token)`,
    where `evaluated_zed_token` is populated strictly from SpiceDB's
    `LookupResourcesResponse.looked_up_at.token` when returned, else `None` (unknown).
    """
    req = LookupResourcesRequest(
        consistency=consistency,
        resource_object_type="document",
        permission="view",
        subject=SubjectReference(object=ObjectReference(object_type="user", object_id=principal_id)),
    )
    docs: Set[str] = set()
    evaluated_tok: Optional[str] = None
    for r in client.LookupResources(req):
        docs.add(r.resource_object_id)
        if getattr(r, "looked_up_at", None) is not None and r.looked_up_at.token:
            evaluated_tok = str(r.looked_up_at.token)
    return docs, evaluated_tok


def _spicedb_lookup_docs(client, principal_id: str, consistency: Consistency) -> Set[str]:
    docs, _ = _spicedb_lookup_docs_with_revision(client, principal_id, consistency)
    return docs


def _build_small_dag(rng: np.random.Generator) -> Tuple[DynamicMultiParentAuthGraph, List[str], np.ndarray]:
    """Builds a 4-container, 8-document (24-chunk) multi-parent DAG for R12a/R12c."""
    g = DynamicMultiParentAuthGraph(branching_factor=3, depth=3)
    for cid, lvl in (("c_root", 0), ("c_A", 1), ("c_B", 1), ("c_C", 1), ("c_X", 2)):
        g.add_node(cid, depth_level=lvl, is_leaf=False)
    docs = [f"doc_{i}" for i in range(8)]
    for d in docs:
        g.add_node(d, depth_level=3, is_leaf=True)

    g.add_hierarchy_edge("c_root", "c_A")
    g.add_hierarchy_edge("c_root", "c_B")
    g.add_hierarchy_edge("c_root", "c_C")
    g.add_hierarchy_edge("c_A", "c_X")
    for i in range(4):
        g.add_hierarchy_edge("c_A", f"doc_{i}")
    g.add_hierarchy_edge("c_X", "doc_0")
    for i in range(4, 8):
        g.add_hierarchy_edge("c_B", f"doc_{i}")
    g.add_hierarchy_edge("c_B", "doc_1")  # shared multi-parent doc_1

    g.grant_access("alice", "c_A")
    g.add_deny_exclusion("alice", "c_C")

    chunk_docs = [docs[i // 3] for i in range(24)]
    vecs = rng.standard_normal((24, 16)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    return g, chunk_docs, vecs


class _V33RaceProbeCorpus(VersionedLineageCorpus):
    """
    Non-modifying test probe wrapping frozen `v3.3` `VersionedLineageCorpus`:
    triggers the exact two reviewer-specified concurrent mutation injections
    inside `_compute_token_bitmaps` while executing the unmodified frozen
    `VersionedLineageCorpus.sync_to_revision()` method.
    """

    def __init__(self, *args, **kwargs):
        self._inject_before = None
        self._inject_after = None
        super().__init__(*args, **kwargs)

    def _compute_token_bitmaps(self, auth_graph: DynamicMultiParentAuthGraph):
        if self._inject_before is not None:
            fn = self._inject_before
            self._inject_before = None
            fn()
        bitmaps = super()._compute_token_bitmaps(auth_graph)
        if self._inject_after is not None:
            fn = self._inject_after
            self._inject_after = None
            fn()
        return bitmaps


def _verify_v33_snapshot(corpus: VersionedLineageCorpus, snap) -> Dict[str, Any]:
    recomputed = VersionedLineageCorpus._compute_token_bitmaps(corpus, snap.auth_snapshot)
    zt_ok = snap.zed_token == snap.auth_snapshot.zed_token
    hv_ok = snap.hierarchy_version == snap.auth_snapshot.hierarchy_version
    keys_ok = set(snap.token_bitmaps.keys()) == set(recomputed.keys())
    bm_mm = 0
    if keys_ok:
        for k, bm in recomputed.items():
            if snap.token_bitmaps[k].to_id_set() != bm.to_id_set():
                bm_mm += 1
    else:
        bm_mm = len(set(snap.token_bitmaps.keys()) ^ set(recomputed.keys()))
    return {
        "consistent": bool(zt_ok and hv_ok and keys_ok and bm_mm == 0),
        "zt_match": zt_ok,
        "hv_match": hv_ok,
        "bitmap_mismatches": bm_mm,
    }


# ===========================================================================
# R12a — Deterministic Race Injection (Frozen v3.3 Control vs. v3.4 Atomic Fix)
# ===========================================================================
def run_r12a_race_injection(logger: RawAuditLogger) -> None:
    print("\n=== [R12a] SNAPSHOT-PUBLICATION RACE INJECTION (v3.3 CONTROL vs. v3.4 FIX) ===", flush=True)
    t0 = time.perf_counter()
    rng = np.random.default_rng(1201)

    # Part 1: 100 double-injection trials on BOTH frozen v3.3 control and v3.4 fix
    for trial in range(100):
        target_doc_1 = f"doc_{int(rng.integers(0, 4))}"
        target_doc_2 = f"doc_{int(rng.integers(4, 8))}"

        # --- Control: Frozen v3.3 VersionedLineageCorpus ---
        g_ctrl, chunk_docs, vecs = _build_small_dag(rng)
        c_ctrl = _V33RaceProbeCorpus(g_ctrl, vecs, leaf_doc_ids=chunk_docs)
        # Trigger a structural change so sync_to_revision enters _compute_token_bitmaps
        g_ctrl.add_hierarchy_edge("c_B", target_doc_1)

        def _ctrl_inj_1(g=g_ctrl, d1=target_doc_1) -> None:
            # Mutation 1: immediately after capturing revision, before computing postings
            g.add_hierarchy_edge("c_C", d1)

        def _ctrl_inj_2(g=g_ctrl, d2=target_doc_2) -> None:
            # Mutation 2: immediately after computing postings, before copying auth state
            g.add_hierarchy_edge("c_A", d2)
            g.grant_access("alice", "c_B")

        c_ctrl._inject_before = _ctrl_inj_1
        c_ctrl._inject_after = _ctrl_inj_2
        snap_ctrl = c_ctrl.sync_to_revision(g_ctrl)
        chk_ctrl = _verify_v33_snapshot(c_ctrl, snap_ctrl)
        logger.log(
            "R12a",
            {
                "variant": "v3_3_control",
                "subtest": "double_injection",
                "trial": trial,
                "snapshot_consistent": chk_ctrl["consistent"],
                "zt_match": chk_ctrl["zt_match"],
                "hv_match": chk_ctrl["hv_match"],
                "bitmap_mismatches": chk_ctrl["bitmap_mismatches"],
                "ordering_regression": 0,
                "search_leaks": 0,
                "search_fn": 0,
            },
        )

        # --- Treatment: v3.4 AtomicVersionedLineageCorpus + ConsistentDynamicPrismANNIndex ---
        g_fix, chunk_docs_f, vecs_f = _build_small_dag(rng)
        idx_fix = ConsistentDynamicPrismANNIndex(
            g_fix, vecs_f, leaf_doc_ids=chunk_docs_f,
            M=8, m_bridge=4, ef_construction=32, ef_search=32,
            n_guard=100, mode3_precision="f32", seed=12 + trial,
        )
        g_fix.add_hierarchy_edge("c_B", target_doc_1)

        def _fix_inj_1(_zt: int, _hv: int, g=g_fix, d1=target_doc_1) -> None:
            g.add_hierarchy_edge("c_C", d1)

        def _fix_inj_2(_zt: int, _hv: int, g=g_fix, d2=target_doc_2) -> None:
            g.add_hierarchy_edge("c_A", d2)
            g.grant_access("alice", "c_B")

        snap_fix = idx_fix.sync(on_after_capture=_fix_inj_1, on_after_postings=_fix_inj_2)
        chk_fix = idx_fix.vcorpus.verify_snapshot_internal_consistency(snap_fix)

        # Verify public search() at the published revision matches snap_fix.auth_snapshot oracle
        res_meta = idx_fix.search_with_metadata(
            vecs_f[0], "alice", k=24, zed_token=snap_fix.zed_token,
            consistency_mode="at_exact_snapshot", on_unavailable="fail_closed",
        )
        got_docs = {idx_fix.vcorpus.z_leaf_doc_ids[zid] for zid in res_meta.result.top_k_ids}
        oracle_docs = _dag_oracle_authorized_leaves(snap_fix.auth_snapshot, "alice")
        leaks = len(got_docs - oracle_docs)
        fn = len(oracle_docs - got_docs)

        logger.log(
            "R12a",
            {
                "variant": "v3_4_atomic",
                "subtest": "double_injection",
                "trial": trial,
                "snapshot_consistent": chk_fix["consistent"],
                "zt_match": chk_fix["zt_match"],
                "hv_match": chk_fix["hv_match"],
                "bitmap_mismatches": chk_fix["bitmap_mismatches"],
                "ordering_regression": 0,
                "search_leaks": leaks,
                "search_fn": fn,
            },
        )

    # Part 2: 100 concurrent out-of-order multi-publisher monotonic ordering trials
    for trial in range(100):
        g_mp, chunk_docs_m, vecs_m = _build_small_dag(rng)
        idx_mp = ConsistentDynamicPrismANNIndex(
            g_mp, vecs_m, leaf_doc_ids=chunk_docs_m,
            M=8, m_bridge=4, ef_construction=32, ef_search=32,
            n_guard=100, mode3_precision="f32", seed=500 + trial,
        )
        g_mp.add_hierarchy_edge("c_B", "doc_2")

        captured_older = threading.Event()
        newer_published = threading.Event()
        older_snap_box: List[AtomicRevisionSnapshot] = []
        newer_snap_box: List[AtomicRevisionSnapshot] = []

        def _older_publisher() -> None:
            def _pause_after_capture(_zt: int, _hv: int) -> None:
                captured_older.set()
                newer_published.wait(timeout=5.0)

            s_old = idx_mp.sync(on_after_capture=_pause_after_capture)
            older_snap_box.append(s_old)

        t_old = threading.Thread(target=_older_publisher)
        t_old.start()
        assert captured_older.wait(timeout=5.0)

        # Newer writer mutates graph & finishes publishing BEFORE older publisher resumes!
        g_mp.add_hierarchy_edge("c_C", "doc_0")
        g_mp.grant_access("alice", "c_B")
        s_new = idx_mp.sync()
        newer_snap_box.append(s_new)
        newer_published.set()
        t_old.join(timeout=5.0)

        s_old = older_snap_box[0]
        chk_old = idx_mp.vcorpus.verify_snapshot_internal_consistency(s_old)
        chk_new = idx_mp.vcorpus.verify_snapshot_internal_consistency(s_new)
        latest = idx_mp.vcorpus._latest_snapshot
        ordering_reg = int(latest is None or latest.zed_token != s_new.zed_token or s_old.zed_token >= s_new.zed_token)

        # Verify both historical at_exact_snapshot(s_old) and latest at_least_as_fresh(s_new)
        r_old = idx_mp.search_with_metadata(vecs_m[0], "alice", k=24, zed_token=s_old.zed_token, consistency_mode="at_exact_snapshot")
        r_new = idx_mp.search_with_metadata(vecs_m[0], "alice", k=24, zed_token=s_new.zed_token, consistency_mode="at_least_as_fresh")
        got_old = {idx_mp.vcorpus.z_leaf_doc_ids[zid] for zid in r_old.result.top_k_ids}
        got_new = {idx_mp.vcorpus.z_leaf_doc_ids[zid] for zid in r_new.result.top_k_ids}
        ora_old = _dag_oracle_authorized_leaves(s_old.auth_snapshot, "alice")
        ora_new = _dag_oracle_authorized_leaves(s_new.auth_snapshot, "alice")

        logger.log(
            "R12a",
            {
                "variant": "v3_4_atomic",
                "subtest": "multipublisher_ordering",
                "trial": trial,
                "snapshot_consistent": bool(chk_old["consistent"] and chk_new["consistent"]),
                "zt_match": bool(chk_old["zt_match"] and chk_new["zt_match"]),
                "hv_match": bool(chk_old["hv_match"] and chk_new["hv_match"]),
                "bitmap_mismatches": int(chk_old["bitmap_mismatches"] + chk_new["bitmap_mismatches"]),
                "ordering_regression": ordering_reg,
                "search_leaks": len(got_old - ora_old) + len(got_new - ora_new),
                "search_fn": len(ora_old - got_old) + len(ora_new - got_new),
            },
        )

    print(f"[R12a] DONE (100 v3.3 control + 200 v3.4 atomic trials) in {time.perf_counter()-t0:.2f}s", flush=True)


# ===========================================================================
# R12b — Live Native SpiceDB v1.57.1 Unsynced Mirror & Opaque ZedToken Matrix
# ===========================================================================
def run_r12b_live_spicedb_unsynced_mirror(logger: RawAuditLogger) -> None:
    print("\n=== [R12b] LIVE SPICEDB v1.57.1 UNSYNCED-MIRROR & OPAQUE ZEDTOKEN MATRIX ===", flush=True)
    t0 = time.perf_counter()

    with SpiceDBService() as sp:
        assert sp.client is not None
        rng = np.random.default_rng(1202)

        g = DynamicMultiParentAuthGraph(branching_factor=3, depth=3)
        for cid, lvl in (("c_root", 0), ("c_A", 1), ("c_B", 1), ("c_deny", 1), ("c_subA", 2), ("c_subB", 2)):
            g.add_node(cid, depth_level=lvl, is_leaf=False)
        doc_ids = [f"doc_{i}" for i in range(10)]
        for d in doc_ids:
            g.add_node(d, depth_level=3, is_leaf=True)

        g.add_hierarchy_edge("c_root", "c_A")
        g.add_hierarchy_edge("c_root", "c_B")
        g.add_hierarchy_edge("c_root", "c_deny")
        g.add_hierarchy_edge("c_A", "c_subA")
        g.add_hierarchy_edge("c_B", "c_subB")
        g.add_hierarchy_edge("c_subA", "doc_0")
        g.add_hierarchy_edge("c_subB", "doc_0")  # multi-parent shared doc
        for i in range(1, 5):
            g.add_hierarchy_edge("c_subA", f"doc_{i}")
        for i in range(5, 10):
            g.add_hierarchy_edge("c_subB", f"doc_{i}")

        u = "alice"
        g.grant_access(u, "c_subA")
        g.add_deny_exclusion(u, "c_deny")

        # Initial full load into live native SpiceDB v1.57.1
        sp.load_hierarchy(g)
        zt_0_obj = sp.write_principal_policy(u, grants=["c_subA"], denies=["c_deny"])
        zt_0 = str(zt_0_obj.token)

        chunk_docs = [doc_ids[i // 4] for i in range(40)]
        vecs = rng.standard_normal((40, 16)).astype(np.float32)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)

        def _live_spicedb_lookup(
            principal_id: str, consistency_mode: str, ext_zt: Optional[str]
        ) -> Tuple[Set[str], Optional[str]]:
            if ext_zt is None:
                cons = Consistency(fully_consistent=True)
            elif consistency_mode == "at_exact_snapshot":
                cons = Consistency(at_exact_snapshot=ZedToken(token=ext_zt))
            else:
                cons = Consistency(at_least_as_fresh=ZedToken(token=ext_zt))
            # Return SpiceDB's actual `looked_up_at.token` when established, or None (unknown);
            # never blindly echo the requested minimum token `ext_zt`.
            docs, evaluated_tok = _spicedb_lookup_docs_with_revision(sp.client, principal_id, cons)
            return docs, evaluated_tok

        idx = ConsistentDynamicPrismANNIndex(
            g, vecs, leaf_doc_ids=chunk_docs,
            initial_external_zed_token=zt_0,
            external_auth_lookup=_live_spicedb_lookup,
            M=8, m_bridge=4, ef_construction=32, ef_search=32,
            n_guard=100, mode3_precision="f32", seed=1202,
        )

        def _sp_consistency(mode: str, ext_tok: str) -> Consistency:
            if mode == "at_exact_snapshot":
                return Consistency(at_exact_snapshot=ZedToken(token=ext_tok))
            return Consistency(at_least_as_fresh=ZedToken(token=ext_tok))

        def _oracle_and_checkperm(mode: str, ext_tok: str) -> Tuple[Set[str], int]:
            cons = _sp_consistency(mode, ext_tok)
            docs = _spicedb_lookup_docs(sp.client, u, cons)
            chk_mm = 0
            for d_id in doc_ids:
                if _spicedb_check_permission(sp.client, d_id, u, cons) != (d_id in docs):
                    chk_mm += 1
            return docs, chk_mm

        def _run_expect_success(
            name: str,
            ext_tok: str,
            consistency_mode: str,
            on_unavailable: str,
            expected_fallback: Optional[str],
            oracle_tok_override: Optional[str] = None,
            oracle_mode_override: Optional[str] = None,
        ) -> None:
            t_s = time.perf_counter_ns()
            res_meta = idx.search_with_metadata(
                vecs[0], u, k=40,
                external_zed_token=ext_tok,
                consistency_mode=consistency_mode,
                on_unavailable=on_unavailable,
            )
            lat_ms = (time.perf_counter_ns() - t_s) / 1e6
            got_docs = {idx.vcorpus.z_leaf_doc_ids[zid] for zid in res_meta.result.top_k_ids}

            o_tok = oracle_tok_override or res_meta.selected_external_zed_token or ext_tok
            o_mode = oracle_mode_override or (
                "at_exact_snapshot" if (oracle_tok_override or res_meta.selected_external_zed_token) else consistency_mode
            )
            sp_docs, chk_mm = _oracle_and_checkperm(o_mode, o_tok)

            fb_mm = int(res_meta.fallback_used != expected_fallback)
            search_mm = int(got_docs != sp_docs) + fb_mm
            logger.log(
                "R12b",
                {
                    "scenario": name,
                    "spicedb_docs": len(sp_docs),
                    "index_docs": len(got_docs),
                    "mask_mismatch": int(got_docs != sp_docs),
                    "search_mismatch": search_mm,
                    "check_perm_mismatch": chk_mm,
                    "consistency_mode": consistency_mode,
                    "on_unavailable": on_unavailable,
                    "requested_external_zed_token": res_meta.requested_external_zed_token,
                    "evaluated_external_zed_token": res_meta.selected_external_zed_token,
                    "evaluated_external_revision_status": res_meta.evaluated_external_revision_status,
                    "selected_external_zed_token": res_meta.selected_external_zed_token,
                    "selected_local_revision": res_meta.selected_local_revision,
                    "fallback_used": res_meta.fallback_used,
                    "fail_closed_refusal_verified": False,
                    "latency_ms": lat_ms,
                },
            )
            print(
                f"  [R12b] {name}: sp={len(sp_docs)} idx={len(got_docs)} "
                f"fb={res_meta.fallback_used} mm={search_mm}/{chk_mm}",
                flush=True,
            )

        def _run_expect_fail_closed(
            name: str,
            ext_tok: str,
            consistency_mode: str,
            on_unavailable: str = "fail_closed",
            target_idx: Optional[ConsistentDynamicPrismANNIndex] = None,
        ) -> None:
            t_s = time.perf_counter_ns()
            use_idx = target_idx or idx
            refused = False
            try:
                use_idx.search_with_metadata(
                    vecs[0], u, k=40,
                    external_zed_token=ext_tok,
                    consistency_mode=consistency_mode,
                    on_unavailable=on_unavailable,
                )
            except StaleOrMissingSnapshotError:
                refused = True
            lat_ms = (time.perf_counter_ns() - t_s) / 1e6
            logger.log(
                "R12b",
                {
                    "scenario": name,
                    "spicedb_docs": None,
                    "index_docs": None,
                    "mask_mismatch": int(not refused),
                    "search_mismatch": int(not refused),
                    "check_perm_mismatch": 0,
                    "consistency_mode": consistency_mode,
                    "on_unavailable": on_unavailable,
                    "requested_external_zed_token": ext_tok,
                    "evaluated_external_zed_token": None,
                    "evaluated_external_revision_status": "refused_fail_closed",
                    "selected_external_zed_token": None,
                    "selected_local_revision": None,
                    "fallback_used": None,
                    "fail_closed_refusal_verified": refused,
                    "latency_ms": lat_ms,
                },
            )
            print(f"  [R12b] {name}: fail_closed_refused={refused}", flush=True)

        # C1: Synced baseline using opaque external ZedToken zt_0 (at_exact_snapshot)
        _run_expect_success("C1_synced_opaque_exact_zt0", zt_0, "at_exact_snapshot", "fail_closed", None)

        # External SpiceDB write #1 (mirror NOT updated!): deny doc_2 directly in SpiceDB
        zt_1_obj = sp._write_updates(
            [
                RelationshipUpdate(
                    operation=RelationshipUpdate.OPERATION_TOUCH,
                    relationship=_rel("document", "doc_2", "ethical_wall_deny", "user", u),
                )
            ]
        )
        zt_1_ext = str(zt_1_obj.token)

        # C2: Mirror lags behind external deny zt_1_ext -> fail_closed MUST refuse
        _run_expect_fail_closed("C2_ext_deny_mirror_lag_fail_closed", zt_1_ext, "at_least_as_fresh", "fail_closed")

        # C3: Same lagging mirror -> spicedb_leaf_fallback MUST query live SpiceDB and exclude doc_2
        _run_expect_success(
            "C3_ext_deny_mirror_lag_spicedb_fallback",
            zt_1_ext, "at_least_as_fresh", "spicedb_leaf_fallback", "spicedb_leaf_fallback",
        )

        # External SpiceDB write #2 (mirror STILL lagging!): attach c_deny -> doc_3 in SpiceDB
        zt_2_obj = sp._write_updates(
            [
                RelationshipUpdate(
                    operation=RelationshipUpdate.OPERATION_TOUCH,
                    relationship=_rel("document", "doc_3", "parent", "container", "c_deny"),
                )
            ]
        )
        zt_2_ext = str(zt_2_obj.token)

        # C4: Mirror lags behind external structural edge to denied container -> fail_closed refuses
        _run_expect_fail_closed("C4_ext_edge_deny_mirror_lag_fail_closed", zt_2_ext, "at_least_as_fresh", "fail_closed")

        # C5: Same lagging mirror -> spicedb_leaf_fallback queries live SpiceDB and excludes doc_2 & doc_3
        _run_expect_success(
            "C5_ext_edge_deny_mirror_lag_spicedb_fallback",
            zt_2_ext, "at_least_as_fresh", "spicedb_leaf_fallback", "spicedb_leaf_fallback",
        )

        # C6: Guard test — requesting spicedb_leaf_fallback WITHOUT an external SpiceDB provider MUST fail closed!
        idx_no_provider = ConsistentDynamicPrismANNIndex(
            g.snapshot_graph_copy(), vecs, leaf_doc_ids=chunk_docs,
            initial_external_zed_token=zt_0,
            external_auth_lookup=None,
            M=8, m_bridge=4, ef_construction=32, ef_search=32,
            n_guard=100, mode3_precision="f32", seed=1203,
        )
        _run_expect_fail_closed(
            "C6_missing_spicedb_provider_guard_fail_closed",
            zt_2_ext, "at_least_as_fresh", "spicedb_leaf_fallback", target_idx=idx_no_provider,
        )

        # Mirror catches up to zt_2_ext (applies both external changes and binds opaque zt_2_ext)
        g.add_deny_exclusion(u, "doc_2")
        g.add_hierarchy_edge("c_deny", "doc_3")
        idx.sync(external_zed_token=zt_2_ext)

        # C7: After mirror catch-up, fast UBP snapshot serves zt_2_ext with fallback_used=None
        _run_expect_success("C7_mirror_catchup_ubp_resumes_zt2", zt_2_ext, "at_exact_snapshot", "fail_closed", None)

        # C8: at_least_as_fresh(zt_0) AFTER mirror advanced to zt_2_ext validly serves newer zt_2_ext
        _run_expect_success(
            "C8_at_least_as_fresh_zt0_serves_newer_zt2",
            zt_0, "at_least_as_fresh", "fail_closed", None,
            oracle_tok_override=zt_2_ext, oracle_mode_override="at_exact_snapshot",
        )

        # C9: Evict snapshots older than zt_2_ext -> at_exact_snapshot(zt_0) fails closed,
        # while spicedb_leaf_fallback queries live SpiceDB at_exact_snapshot(zt_0) accurately!
        evicted = idx.vcorpus.evict_snapshots_before_external_token(zt_2_ext)
        assert evicted >= 1, f"Expected >=1 evicted snapshot, got {evicted}"
        _run_expect_fail_closed("C9a_evicted_exact_zt0_fail_closed", zt_0, "at_exact_snapshot", "fail_closed")
        _run_expect_success(
            "C9b_evicted_exact_zt0_spicedb_fallback",
            zt_0, "at_exact_snapshot", "spicedb_leaf_fallback", "spicedb_leaf_fallback",
        )

        # External SpiceDB write #3 (mirror lags): grant alice c_subB (adds doc_5..doc_9!)
        zt_3_obj = sp._write_updates(
            [
                RelationshipUpdate(
                    operation=RelationshipUpdate.OPERATION_TOUCH,
                    relationship=_rel("container", "c_subB", "viewer", "user", u),
                )
            ]
        )
        zt_3_ext = str(zt_3_obj.token)

        # C10a: Mirror lags behind external grant -> fail_closed refuses;
        # C10b: spicedb_leaf_fallback immediately returns newly granted docs (0 FN);
        # C10c: mirror catches up -> fast UBP resumes with 0 mismatches!
        _run_expect_fail_closed("C10a_ext_grant_mirror_lag_fail_closed", zt_3_ext, "at_least_as_fresh", "fail_closed")
        _run_expect_success(
            "C10b_ext_grant_mirror_lag_spicedb_fallback",
            zt_3_ext, "at_least_as_fresh", "spicedb_leaf_fallback", "spicedb_leaf_fallback",
        )
        g.grant_access(u, "c_subB")
        idx.sync(external_zed_token=zt_3_ext)
        _run_expect_success("C10c_ext_grant_catchup_ubp_resumes_zt3", zt_3_ext, "at_exact_snapshot", "fail_closed", None)

    print(f"[R12b] DONE live SpiceDB unsynced-mirror matrix in {time.perf_counter()-t0:.2f}s", flush=True)


# ===========================================================================
# R12c — Multi-Threaded Concurrent DAG Mutation, Publication & Public search()
# ===========================================================================
def run_r12c_multithreaded_stress(logger: RawAuditLogger) -> None:
    print("\n=== [R12c] MULTI-THREADED CONCURRENT MUTATION, PUBLICATION & PUBLIC SEARCH STRESS ===", flush=True)
    t0 = time.perf_counter()
    rng = np.random.default_rng(1203)
    g, chunk_docs, vecs = _build_small_dag(rng)
    idx = ConsistentDynamicPrismANNIndex(
        g, vecs, leaf_doc_ids=chunk_docs,
        M=8, m_bridge=4, ef_construction=32, ef_search=32,
        n_guard=100, mode3_precision="f32", seed=1203,
    )

    published_lock = threading.Lock()
    published_zts: List[int] = [idx.vcorpus._latest_snapshot.zed_token]
    start_barrier = threading.Barrier(8)
    stop_writers = threading.Event()
    read_records: List[Dict[str, Any]] = []
    read_lock = threading.Lock()
    snap_audit_records: List[Dict[str, Any]] = []

    def _writer_worker(wid: int) -> None:
        lrng = np.random.default_rng(7000 + wid)
        start_barrier.wait(timeout=10.0)
        for step in range(45):
            if stop_writers.is_set() and step >= 25:
                break
            op = step % 5
            d_i = f"doc_{int(lrng.integers(0, 8))}"
            if op == 0:
                g.add_hierarchy_edge("c_C", d_i)
            elif op == 1:
                g.remove_hierarchy_edge("c_C", d_i)
            elif op == 2:
                g.add_hierarchy_edge("c_A", d_i)
            elif op == 3:
                g.grant_access("alice", "c_B")
            else:
                g.revoke_access("alice", "c_B")
            snap = idx.sync()
            with published_lock:
                published_zts.append(snap.zed_token)

    def _reader_worker(rid: int) -> None:
        lrng = np.random.default_rng(8000 + rid)
        local_recs: List[Dict[str, Any]] = []
        start_barrier.wait(timeout=10.0)
        for q_i in range(300):
            if q_i % 10 == 0:
                time.sleep(0.0002)
            with published_lock:
                known_zt = int(published_zts[int(lrng.integers(0, len(published_zts)))])
            mode = "at_exact_snapshot" if (q_i % 2 == 0) else "at_least_as_fresh"
            qv = vecs[int(lrng.integers(0, len(vecs)))]
            t_q = time.perf_counter_ns()
            res_meta = idx.search_with_metadata(
                qv, "alice", k=24,
                zed_token=known_zt,
                consistency_mode=mode,
                on_unavailable="fail_closed",
                auto_sync=False,
            )
            lat_ms = (time.perf_counter_ns() - t_q) / 1e6
            sel_zt = res_meta.selected_local_revision
            assert sel_zt is not None
            with idx.vcorpus._lock:
                sel_snap = idx.vcorpus._snapshots[sel_zt]
            got_docs = {idx.vcorpus.z_leaf_doc_ids[zid] for zid in res_meta.result.top_k_ids}
            ora_docs = _dag_oracle_authorized_leaves(sel_snap.auth_snapshot, "alice")
            leaks = len(got_docs - ora_docs)
            fn = len(ora_docs - got_docs)
            mode_ok = (sel_zt == known_zt) if mode == "at_exact_snapshot" else (sel_zt >= known_zt)
            local_recs.append(
                {
                    "experiment": "R12c",
                    "record_kind": "read",
                    "reader_id": rid,
                    "query_idx": q_i,
                    "consistency_mode": mode,
                    "requested_local_zt": known_zt,
                    "selected_local_zt": sel_zt,
                    "oracle_mismatch": int(leaks > 0 or fn > 0 or not mode_ok),
                    "search_leaks": leaks,
                    "search_fn": fn,
                    "latency_ms": lat_ms,
                }
            )
        with read_lock:
            read_records.extend(local_recs)

    writers = [threading.Thread(target=_writer_worker, args=(w,)) for w in range(4)]
    readers = [threading.Thread(target=_reader_worker, args=(r,)) for r in range(4)]
    for t in writers + readers:
        t.start()
    for t in readers:
        t.join(timeout=60.0)
    stop_writers.set()
    for t in writers:
        t.join(timeout=60.0)

    # Audit EVERY published snapshot in the corpus for full internal consistency & monotonic latest
    with idx.vcorpus._lock:
        all_snaps = sorted(idx.vcorpus._snapshots.items(), key=lambda kv: kv[0])
        max_zt = max(kv[0] for kv in all_snaps)
        latest_zt = idx.vcorpus._latest_snapshot.zed_token if idx.vcorpus._latest_snapshot is not None else -1

    for zt_key, snap in all_snaps:
        chk = idx.vcorpus.verify_snapshot_internal_consistency(snap)
        snap_audit_records.append(
            {
                "experiment": "R12c",
                "record_kind": "snapshot_audit",
                "zed_token": zt_key,
                "snapshot_consistent": chk["consistent"],
                "zt_match": chk["zt_match"],
                "hv_match": chk["hv_match"],
                "bitmap_mismatches": chk["bitmap_mismatches"],
                "ordering_regression": int(latest_zt != max_zt),
            }
        )

    for rec in read_records:
        logger.log("R12c", {k: v for k, v in rec.items() if k != "experiment"})
    for rec in snap_audit_records:
        logger.log("R12c", {k: v for k, v in rec.items() if k != "experiment"})

    print(
        f"[R12c] DONE ({len(read_records)} concurrent reads across {len(snap_audit_records)} "
        f"audited snapshots) in {time.perf_counter()-t0:.2f}s",
        flush=True,
    )


def main() -> int:
    t_all = time.perf_counter()
    f3 = freeze_v3_status()
    f31 = freeze_v3_1_status()
    f33 = freeze_v3_3_status()
    f34 = freeze_v3_4_status()
    dirty = _repo_is_dirty()

    print(
        f"[v3.4 Audit] git_sha={git_sha()[:10]} dirty={dirty} "
        f"FREEZE_v3={f3['match']} FREEZE_v3_1={f31['match']} "
        f"FREEZE_v3_3={f33['match']} FREEZE_v3_4={f34['match']} ({f34['n_files']}/10)",
        flush=True,
    )
    if not (f3["match"] and f31["match"] and f33["match"] and f34["match"]):
        print("[v3.4 Audit] ABORT: freeze mismatch!", file=sys.stderr)
        return 2

    os.makedirs(os.path.dirname(RAW_OUT_PATH), exist_ok=True)
    if os.path.exists(RAW_OUT_PATH):
        os.remove(RAW_OUT_PATH)

    logger = RawAuditLogger(RAW_OUT_PATH)
    logger.log(
        "META",
        {
            "run_id": "v3.4-reviewer-audit-002",
            "git_sha": git_sha(),
            "git_dirty": dirty,
            "freeze_v3_match": f3["match"],
            "freeze_v3_1_match": f31["match"],
            "freeze_v3_3_match": f33["match"],
            "freeze_v3_4_match": f34["match"],
            "freeze_v3_4_files": f34["n_files"],
        },
    )

    run_r12a_race_injection(logger)
    run_r12b_live_spicedb_unsynced_mirror(logger)
    run_r12c_multithreaded_stress(logger)
    logger.close()

    summary = recompute_v3_4_summary(RAW_OUT_PATH)
    os.makedirs(os.path.dirname(SUMMARY_OUT_PATH), exist_ok=True)
    with open(SUMMARY_OUT_PATH, "w", encoding="utf-8") as f:
        f.write(dumps_summary(summary))

    print(
        f"\n[v3.4 Audit] COMPLETE in {time.perf_counter()-t_all:.2f}s | "
        f"records={summary['raw_records_total']} | verdicts="
        f"{ {k: v['verdict'] for k, v in summary['verdicts'].items()} }",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
