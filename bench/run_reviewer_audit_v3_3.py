#!/usr/bin/env python3
"""
Prism-ANN v3.3 Reviewer Audit Suite (Experiments R9a, R9b, R10, R11)
====================================================================
Pre-registered in `experiments/v3/PROTOCOL_v3_3.md`:
  R9a: 1,000 genuinely independent multi-parent DAGs (zero graph reuse) with dynamic
       post-index structural edge additions, surviving-path unlinks, final-path
       unlinks, deny removals, and grant revocations + re-grants (5,000 checkpoints).
  R9b: 9-scenario live native SpiceDB v1.57.1 multi-parent mutation matrix checked
       against LookupResources & CheckPermission at exact opaque ZedTokens.
  R10: Directly timed (unmodeled, single-timer) end-to-end same-query requests wrapping
       live SpiceDB auth + filter construction + in-timer SQ8 quantization + C++
       search/rerank, plus matched-recall efSearch sweep (32..512).
  R11: 8-thread concurrent live SpiceDB ZedToken consistency stress test using real
       opaque at_exact_snapshot(zt_pre) & at_least_as_fresh(zt_post) Consistency.

Usage:
  /Users/tejap/memory_paper/.venv-bench/bin/python -u -m bench.run_reviewer_audit_v3_3
"""

from __future__ import annotations

import concurrent.futures
import ctypes
import gc
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import faiss
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
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from bench.dataset import build_overlay  # noqa: E402
from bench.dataset_v3 import load_corpus_v3  # noqa: E402
from bench.engines import SpiceDBService, _node_type, _rel  # noqa: E402
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
from bench.recompute_v3_3 import freeze_v3_3_status, recompute_v3_3_summary  # noqa: E402
from bench.run_reviewer_audit_v3_1 import RawAuditLogger, _repo_is_dirty  # noqa: E402
from bench.run_reviewer_audit_v3_2 import _dag_oracle_authorized_leaves  # noqa: E402
from bench.run_v3_dev_exploratory import _compile_ranges_from_tokens  # noqa: E402
from bench.systems import Acorn1System, FaissHNSWSystem  # noqa: E402
from src.modules.prism_ann.trimodal_planner import ZOrderedCorpus  # noqa: E402
from src.modules.prism_ann.ubp_resolver import ZanzibarAuthGraph, resolve_ubp_tokens  # noqa: E402
from src.modules.prism_ann_v3.ckernel_bridge import (  # noqa: E402
    mode3_scan_ranges_f32,
    mode3_scan_ranges_sq8,
    ranges_clear_bitset,
    ranges_set_bitset,
    search_hhnsw_gls_cpp,
)
from src.modules.prism_ann_v3.dynamic_dag_ubp import (  # noqa: E402
    DynamicMultiParentAuthGraph,
    DynamicPrismANNIndex,
    VersionedLineageCorpus,
)
from src.modules.prism_ann_v3.geometric_hhnsw import (  # noqa: E402
    GeometricBridgeConfig,
    GeometricHHNSW,
)
from src.modules.prism_ann_v3.trimodal_v3 import bool_mask_to_range_arrays, runs_to_range_arrays  # noqa: E402

RAW_OUT_PATH = os.path.join(REPO_ROOT, "results", "v3_3_audit", "raw", "v3_3_reviewer_audit.jsonl")
SUMMARY_OUT_PATH = os.path.join(REPO_ROOT, "results", "v3", "reviewer_audit_v3_3.json")


# ---------------------------------------------------------------------------
# Helpers for SpiceDB exact snapshot & CheckPermission queries
# ---------------------------------------------------------------------------
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


def _spicedb_lookup_docs(client, principal_id: str, consistency: Consistency) -> Set[str]:
    req = LookupResourcesRequest(
        consistency=consistency,
        resource_object_type="document",
        permission="view",
        subject=SubjectReference(object=ObjectReference(object_type="user", object_id=principal_id)),
    )
    return {r.resource_object_id for r in client.LookupResources(req)}


def _copy_to_dynamic_graph(src: ZanzibarAuthGraph) -> DynamicMultiParentAuthGraph:
    dg = DynamicMultiParentAuthGraph(branching_factor=src.b, depth=src.L)
    dg.all_nodes = set(src.all_nodes)
    dg.node_depth = dict(src.node_depth)
    dg.leaf_documents = set(src.leaf_documents)
    dg.children = {k: list(v) for k, v in src.children.items()}
    dg.parents = {k: set(v) for k, v in src.parents.items()}
    dg.positive_grants = {k: set(v) for k, v in src.positive_grants.items()}
    dg.explicit_denies = {k: set(v) for k, v in src.explicit_denies.items()}
    dg.revoked_subtrees = set(src.revoked_subtrees)
    return dg


# ===========================================================================
# R9a — 1,000 Genuinely Independent Multi-Parent DAGs + Dynamic Mutations
# ===========================================================================
def _generate_independent_multiparent_dag(
    b: int, L: int, rng: np.random.Generator
) -> Tuple[DynamicMultiParentAuthGraph, List[List[str]], int]:
    base = ZanzibarAuthGraph.build_balanced_hierarchy(branching_factor=b, depth=L)
    g = _copy_to_dynamic_graph(base)
    levels: List[List[str]] = [[] for _ in range(L + 1)]
    for nid in g.all_nodes:
        levels[g.node_depth[nid]].append(nid)
    for arr in levels:
        arr.sort()

    n_sec = 0
    for lvl in range(2, L + 1):
        cand_parents = levels[lvl - 1]
        for child_id in levels[lvl]:
            if float(rng.random()) < 0.30 and len(cand_parents) >= 3:
                extra_k = int(rng.integers(1, 3))
                picks = rng.choice(len(cand_parents), size=min(len(cand_parents), extra_k + 1), replace=False)
                added = 0
                for pi in picks:
                    pid = cand_parents[int(pi)]
                    if pid not in g.parents[child_id]:
                        g.add_hierarchy_edge(pid, child_id)
                        n_sec += 1
                        added += 1
                        if added >= extra_k:
                            break
    return g, levels, n_sec


def run_r9a_independent_dag_mutations(logger: RawAuditLogger) -> None:
    print("\n=== [R9a] 1,000 INDEPENDENT MULTI-PARENT DAGS + DYNAMIC MUTATIONS ===", flush=True)
    t0 = time.perf_counter()
    rng = np.random.default_rng(20261124)
    topos = [(4, 4), (4, 5), (6, 4)]

    for dag_id in range(1000):
        b, L = topos[dag_id % len(topos)]
        g, levels, n_sec = _generate_independent_multiparent_dag(b, L, rng)
        leaves = levels[L]
        n_docs = len(leaves)

        # Build lightweight indexed VersionedLineageCorpus (1 vector per leaf doc)
        vecs = rng.standard_normal((n_docs, 8)).astype(np.float32)
        vcorpus = VersionedLineageCorpus(g, vecs, leaf_doc_ids=leaves)
        doc_to_orig = {d: i for i, d in enumerate(leaves)}

        u = f"u_{dag_id}"
        # Two disjoint upper-container branches if available for structured mutation checks
        c_a = levels[1][0]
        c_b = levels[1][1] if len(levels[1]) > 1 else levels[1][0]
        g.grant_access(u, c_a)
        if len(levels[1]) > 2:
            g.add_deny_exclusion(u, levels[1][2])
        # Additional random grant + denies across DAG
        lvl_ex = int(rng.integers(1, L))
        g_extra = levels[lvl_ex][int(rng.integers(0, len(levels[lvl_ex])))]
        g.grant_access(u, g_extra)
        for _ in range(int(rng.integers(1, 5))):
            dl = int(rng.integers(2, L + 1))
            g.add_deny_exclusion(u, levels[dl][int(rng.integers(0, len(levels[dl])))])
        vcorpus.sync_to_revision(g)

        def _check_checkpoint(mut_label: str) -> None:
            snap = vcorpus.get_snapshot(g)
            t_pos, t_neg = resolve_ubp_tokens(snap.auth_snapshot, u)
            b_acl = vcorpus.compile_acl_bitmap_ubp(t_pos, t_neg, snapshot=snap)
            starts, ends, _ = runs_to_range_arrays(b_acl)
            # Materialize allowed doc set from VersionedLineageCorpus ranges (exact Mode-3 mask)
            allowed_z: Set[int] = set()
            for s_i, e_i in zip(starts.tolist(), ends.tolist()):
                allowed_z.update(range(s_i, e_i))
            ubp_docs = {vcorpus.z_leaf_doc_ids[z] for z in allowed_z}
            oracle_docs = _dag_oracle_authorized_leaves(g, u)
            fp = len(ubp_docs - oracle_docs)
            fn = len(oracle_docs - ubp_docs)
            # Also execute actual vector top-k check over Mode-3 scan to prove search hits 0 leaks
            qv = vecs[0]
            q_norm = np.ascontiguousarray(qv / max(1e-9, float(np.linalg.norm(qv))), dtype=np.float32)
            ids_m3, _, _ = mode3_scan_ranges_f32(vcorpus.z_corpus.vectors, q_norm, starts, ends, k=5)
            hit_docs = {vcorpus.z_leaf_doc_ids[int(zid)] for zid in ids_m3.tolist() if zid >= 0}
            search_leaks = len(hit_docs - oracle_docs)
            logger.log("R9a_independent_dag", {
                "dag_id": dag_id,
                "b": b,
                "L": L,
                "n_secondary_edges": n_sec,
                "mutation": mut_label,
                "fp": fp,
                "fn": fn,
                "search_leaks": search_leaks,
                "oracle_count": len(oracle_docs),
            })

        # Mutation 1: Post-index add_hierarchy_edge from a denied branch onto an allowed leaf!
        oracle_now = sorted(_dag_oracle_authorized_leaves(g, u))
        if oracle_now and len(levels[1]) > 2:
            d_victim = oracle_now[int(rng.integers(0, len(oracle_now)))]
            g.add_hierarchy_edge(levels[1][2], d_victim)
            vcorpus.sync_to_revision(g)
        _check_checkpoint("M1_add_denied_parent_edge")

        # Mutation 2: Unlink one parent edge from a multi-parent leaf while preserving another active parent path
        leaf_target = f"doc_L{L}_0"
        parent_extra_ok = levels[1][0]
        parent_extra_alt = c_b
        g.add_hierarchy_edge(parent_extra_ok, leaf_target)
        g.add_hierarchy_edge(parent_extra_alt, leaf_target)
        g.grant_access(u, parent_extra_alt)
        vcorpus.sync_to_revision(g)
        g.remove_hierarchy_edge(parent_extra_ok, leaf_target)  # other path(s) remain!
        vcorpus.sync_to_revision(g)
        _check_checkpoint("M2_unlink_one_parent_surviving_path")

        # Mutation 3: Unlink ALL remaining parents from leaf_target (final path removed!)
        for pid in list(g.parents.get(leaf_target, ())):
            g.remove_hierarchy_edge(pid, leaf_target)
        vcorpus.sync_to_revision(g)
        _check_checkpoint("M3_unlink_final_parent_path")

        # Mutation 4: Remove one active explicit DENY wall
        denies_u = sorted(g.explicit_denies.get(u, set()))
        if denies_u:
            g.remove_deny_exclusion(u, denies_u[0])
            vcorpus.sync_to_revision(g)
        _check_checkpoint("M4_remove_deny_exclusion")

        # Mutation 5: Revoke grant and re-grant
        grants_u = sorted(g.positive_grants.get(u, set()))
        if grants_u:
            g.revoke_access(u, grants_u[0])
            vcorpus.sync_to_revision(g)
            g.grant_access(u, grants_u[0])
            vcorpus.sync_to_revision(g)
        _check_checkpoint("M5_revoke_and_regrant")

        if (dag_id + 1) % 250 == 0:
            print(f"  [R9a] {dag_id + 1}/1,000 independent DAGs completed ({time.perf_counter()-t0:.1f}s)", flush=True)

    print(f"[R9a] DONE 1,000 independent DAGs (5,000 checkpoints) in {time.perf_counter()-t0:.2f}s", flush=True)


# ===========================================================================
# R9b & R11 — Live Native SpiceDB v1.57.1 Schema Matrix & Opaque ZedToken Concurrency
# ===========================================================================
def run_r9b_and_r11_live_spicedb(logger: RawAuditLogger) -> None:
    print("\n=== [R9b & R11] LIVE SPICEDB v1.57.1 MULTI-PARENT MATRIX & CONCURRENT ZEDTOKEN TEST ===", flush=True)
    t0 = time.perf_counter()

    with SpiceDBService() as sp:
        assert sp.client is not None
        rng = np.random.default_rng(911)

        # Construct deterministic multi-parent test graph with 6 containers + 12 docs (64 chunks for HNSW + Mode 3)
        g = DynamicMultiParentAuthGraph(branching_factor=3, depth=3)
        for cid, lvl in (("c_root", 0), ("c_A", 1), ("c_B", 1), ("c_deny", 1), ("c_subA", 2), ("c_subB", 2)):
            g.add_node(cid, depth_level=lvl, is_leaf=False)
        doc_ids = [f"doc_{i}" for i in range(12)]
        for d_id in doc_ids:
            g.add_node(d_id, depth_level=3, is_leaf=True)

        g.add_hierarchy_edge("c_root", "c_A")
        g.add_hierarchy_edge("c_root", "c_B")
        g.add_hierarchy_edge("c_root", "c_deny")
        g.add_hierarchy_edge("c_A", "c_subA")
        g.add_hierarchy_edge("c_B", "c_subB")
        # Multi-parent doc_0 shared under c_subA and c_subB
        g.add_hierarchy_edge("c_subA", "doc_0")
        g.add_hierarchy_edge("c_subB", "doc_0")
        # Other docs
        for i in range(1, 6):
            g.add_hierarchy_edge("c_subA", f"doc_{i}")
        for i in range(6, 12):
            g.add_hierarchy_edge("c_subB", f"doc_{i}")

        # 60 chunks (5 per document)
        chunk_docs = [doc_ids[i // 5] for i in range(60)]
        vecs = rng.standard_normal((60, 16)).astype(np.float32)
        idx = DynamicPrismANNIndex(
            g, vecs, leaf_doc_ids=chunk_docs, M=8, m_bridge=4, ef_construction=32, ef_search=32,
            n_guard=100, mode3_precision="f32", seed=11,
        )

        # Helper to sync initial edges to live SpiceDB
        def _sync_sp_all() -> Any:
            return sp.load_hierarchy(g)

        _sync_sp_all()
        u = "alice"
        zt = sp.write_principal_policy(u, grants=["c_subA", "c_subB"], denies=[])
        g.grant_access(u, "c_subA")
        g.grant_access(u, "c_subB")
        idx.sync()

        def _verify_scenario(name: str, zed_tok_sp, local_zt: Optional[int] = None, check_mode: str = "at_least_as_fresh") -> None:
            cons = (
                Consistency(at_exact_snapshot=zed_tok_sp)
                if check_mode == "exact"
                else Consistency(at_least_as_fresh=zed_tok_sp)
            )
            sp_docs = _spicedb_lookup_docs(sp.client, u, cons)
            # Also verify individual CheckPermission for all 12 docs!
            chk_mismatches = 0
            for d_id in doc_ids:
                has_p = _spicedb_check_permission(sp.client, d_id, u, cons)
                if has_p != (d_id in sp_docs):
                    chk_mismatches += 1

            # Verify compiled mask in VersionedLineageCorpus snapshot
            snap = idx.vcorpus.get_snapshot(g, zed_token=local_zt)
            t_pos, t_neg = resolve_ubp_tokens(snap.auth_snapshot, u)
            b_acl = idx.vcorpus.compile_acl_bitmap_ubp(t_pos, t_neg, snapshot=snap)
            starts, ends, _ = runs_to_range_arrays(b_acl)
            mask_ids: Set[int] = set()
            for s_i, e_i in zip(starts.tolist(), ends.tolist()):
                mask_ids.update(range(s_i, e_i))
            mask_docs = {idx.vcorpus.z_leaf_doc_ids[zid] for zid in mask_ids}
            mask_mm = int(mask_docs != sp_docs)

            # Verify DynamicPrismANNIndex.search(k=60) returns identical doc set
            res = idx.search(vecs[0], u, k=60, zed_token=local_zt)
            search_docs = {idx.vcorpus.z_leaf_doc_ids[zid] for zid in res.top_k_ids}
            search_mm = int(search_docs != sp_docs)

            logger.log("R9b_spicedb_matrix", {
                "scenario": name,
                "spicedb_docs": len(sp_docs),
                "index_docs": len(search_docs),
                "mask_mismatch": mask_mm,
                "search_mismatch": search_mm,
                "check_perm_mismatch": chk_mismatches,
            })

        # Scenario 1: Unlink c_subA -> doc_0 while c_subB -> doc_0 survives (Finding 2)
        zt1 = sp.delete_parent_edge("c_subA", "doc_0")
        idx.remove_hierarchy_edge("c_subA", "doc_0")
        _verify_scenario("S1_surviving_path_after_unlink", zt1)

        # Scenario 2: Remove grant on c_subB and unlink remaining c_subB -> doc_0 (final path removed)
        zt_unB = sp.delete_parent_edge("c_subB", "doc_0")
        idx.remove_hierarchy_edge("c_subB", "doc_0")
        _verify_scenario("S2_final_path_removed", zt_unB)

        # Scenario 3: Direct child grant on doc_0 + attach denied parent c_deny -> doc_0
        zt_dg = sp.write_principal_policy(u, grants=["doc_0"], denies=["c_deny"])
        g.grant_access(u, "doc_0")
        g.add_deny_exclusion(u, "c_deny")
        idx.sync()
        _verify_scenario("S3a_direct_child_grant", zt_dg)

        zt_dp = sp.restore_parent_edge("c_deny", "doc_0")
        idx.add_hierarchy_edge("c_deny", "doc_0")
        _verify_scenario("S3b_deny_parent_added_to_direct_grant", zt_dp)

        zt_dp_rm = sp.delete_parent_edge("c_deny", "doc_0")
        idx.remove_hierarchy_edge("c_deny", "doc_0")
        _verify_scenario("S3c_denied_parent_unlinked_restores_direct", zt_dp_rm)

        # Scenario 4 & 5 (Finding 1 live against SpiceDB!): Index doc_1 under c_subA, add c_deny -> doc_1 post-index!
        zt_add_deny = sp.restore_parent_edge("c_deny", "doc_1")
        local_zt_before_deny_rm = idx.add_hierarchy_edge("c_deny", "doc_1")
        _verify_scenario("S5_postindex_add_denied_parent_doc1", zt_add_deny)

        # Scenario 6: Explicit deny removal on c_deny
        resp_del_d = sp.client.DeleteRelationships(
            DeleteRelationshipsRequest(
                relationship_filter=RelationshipFilter(
                    resource_type="container",
                    optional_resource_id="c_deny",
                    optional_relation="ethical_wall_deny",
                    optional_subject_filter=SubjectFilter(subject_type="user", optional_subject_id=u),
                )
            )
        )
        zt_deny_rm = resp_del_d.deleted_at
        g.remove_deny_exclusion(u, "c_deny")
        idx.sync()
        _verify_scenario("S6_explicit_deny_removed", zt_deny_rm)

        # Scenario 7: Grant revocation + re-grant
        resp_rev_g = sp.client.DeleteRelationships(
            DeleteRelationshipsRequest(
                relationship_filter=RelationshipFilter(
                    resource_type="container",
                    optional_resource_id="c_subA",
                    optional_relation="viewer",
                    optional_subject_filter=SubjectFilter(subject_type="user", optional_subject_id=u),
                )
            )
        )
        zt_rev_g = resp_rev_g.deleted_at
        g.revoke_access(u, "c_subA")
        local_zt_pre_regrant = idx.sync().zed_token
        _verify_scenario("S7a_grant_revoked", zt_rev_g)

        zt_regrant = sp.write_principal_policy(u, grants=["c_subA"], denies=[])
        g.grant_access(u, "c_subA")
        local_zt_post_regrant = idx.sync().zed_token
        _verify_scenario("S7b_grant_regranted", zt_regrant)

        # Scenario 8: Pre-mutation opaque SpiceDB ZedToken exact snapshot read after mutation!
        _verify_scenario("S8_pre_mutation_exact_spicedb_snapshot", zt_rev_g, local_zt=local_zt_pre_regrant, check_mode="exact")

        # -------------------------------------------------------------------
        # R11: 8-Thread Concurrent Live SpiceDB Opaque ZedToken Reader Stress
        # -------------------------------------------------------------------
        # Restore clean c_subA + c_subB state and capture real opaque zt_pre
        zt_pre_sp = zt_regrant
        zt_pre_local = local_zt_post_regrant
        expected_pre_docs = _spicedb_lookup_docs(sp.client, u, Consistency(at_exact_snapshot=zt_pre_sp))

        revoked_docs = {"doc_6", "doc_7", "doc_8", "doc_9", "doc_10", "doc_11"}  # all under c_subB
        rev_state: Dict[str, Any] = {
            "revoked": False,
            "zt_post_sp": None,
            "zt_post_local": None,
            "expected_post_docs": set(),
        }
        state_lock = threading.Lock()
        conc_logs: List[Dict[str, Any]] = []
        log_lock = threading.Lock()

        def _worker(tid: int, n_iters: int = 220) -> None:
            local_buf: List[Dict[str, Any]] = []
            for it in range(n_iters):
                with state_lock:
                    is_post = bool(rev_state["revoked"])
                    zt_sp = rev_state["zt_post_sp"] if is_post else zt_pre_sp
                    zt_loc = rev_state["zt_post_local"] if is_post else zt_pre_local
                    exp_docs = rev_state["expected_post_docs"] if is_post else expected_pre_docs
                    mode_lbl = "post_revocation_at_least_as_fresh" if is_post else "pre_revocation_exact_snapshot"

                cons = Consistency(at_least_as_fresh=zt_sp) if is_post else Consistency(at_exact_snapshot=zt_sp)
                probe_doc = "doc_7"  # revoked after c_subB grant removal
                tr0 = time.perf_counter_ns()
                sp_has_doc7 = _spicedb_check_permission(sp.client, probe_doc, u, cons)
                sp_ms = (time.perf_counter_ns() - tr0) / 1e6

                ti0 = time.perf_counter_ns()
                res_s = idx.search(vecs[it % len(vecs)], u, k=60, zed_token=zt_loc)
                idx_ms = (time.perf_counter_ns() - ti0) / 1e6

                hit_docs = {idx.vcorpus.z_leaf_doc_ids[zid] for zid in res_s.top_k_ids}
                oracle_mm = int((hit_docs != exp_docs) or (sp_has_doc7 != (probe_doc in exp_docs)))
                rev_leaks = len(hit_docs & revoked_docs) if is_post else 0
                stale_err = int(is_post and (hit_docs != exp_docs or rev_leaks > 0 or sp_has_doc7))
                local_buf.append({
                    "tid": tid,
                    "iter": it,
                    "consistency_mode": mode_lbl,
                    "oracle_mismatch": oracle_mm,
                    "revoked_hit_leaks": rev_leaks,
                    "stale_snapshot_error": stale_err,
                    "spicedb_rpc_ms": round(sp_ms, 4),
                    "index_search_ms": round(idx_ms, 4),
                })
            with log_lock:
                conc_logs.extend(local_buf)

        def _writer() -> None:
            time.sleep(0.08)
            resp_w = sp.client.DeleteRelationships(
                DeleteRelationshipsRequest(
                    relationship_filter=RelationshipFilter(
                        resource_type="container",
                        optional_resource_id="c_subB",
                        optional_relation="viewer",
                        optional_subject_filter=SubjectFilter(subject_type="user", optional_subject_id=u),
                    )
                )
            )
            zt_p_sp = resp_w.deleted_at
            g.revoke_access(u, "c_subB")
            zt_p_loc = idx.sync().zed_token
            exp_p = _spicedb_lookup_docs(sp.client, u, Consistency(at_exact_snapshot=zt_p_sp))
            with state_lock:
                rev_state["zt_post_sp"] = zt_p_sp
                rev_state["zt_post_local"] = zt_p_loc
                rev_state["expected_post_docs"] = exp_p
                rev_state["revoked"] = True

        w_thread = threading.Thread(target=_writer)
        w_thread.start()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            futs = [ex.submit(_worker, t, 220) for t in range(8)]
            for f in futs:
                f.result()
        w_thread.join()

        for row in conc_logs:
            logger.log("R11_live_spicedb_zedtoken", row)

    print(f"[R9b & R11] DONE in {time.perf_counter()-t0:.2f}s ({len(conc_logs)} concurrent SpiceDB+Index reads)", flush=True)


# ===========================================================================
# R10 — Directly Timed Same-Query E2E Requests + Matched-Recall efSearch Sweep
# ===========================================================================
def _make_quora_policy_and_mask(
    s_target: float, rng: np.random.Generator, overlay, N: int
) -> Tuple[List[str], List[str], np.ndarray]:
    """
    Constructs a hierarchical SpiceDB container grant + DENY policy matching s_target
    on depth L=5, b=8 (32,768 leaf docs over 522,931 Quora chunks).
    Returns (grants, denies, exact_allowed_bool_mask).
    """
    g = overlay.auth_graph
    if abs(s_target - 0.0001) < 1e-6:
        # 3 leaf docs (~48 chunks)
        picks = rng.choice(32768, size=3, replace=False)
        grants = [f"doc_L5_{int(i)}" for i in picks]
        denies: List[str] = []
    elif abs(s_target - 0.001) < 1e-6:
        # 1 L3 dept (64 docs) minus 4 L4 folders (32 docs -> 32 active docs, ~510 chunks)
        l3 = int(rng.integers(0, 512))
        l4_children = list(range(l3 * 8, l3 * 8 + 8))
        drop_l4 = rng.choice(l4_children, size=4, replace=False)
        grants = [f"node_L3_{l3}"]
        denies = [f"node_L4_{int(x)}" for x in drop_l4]
    elif abs(s_target - 0.005) < 1e-6:
        # 3 L3 depts (192 docs) minus 4 L4 folders (32 docs -> 160 active docs, ~2,553 chunks)
        l3s = rng.choice(512, size=3, replace=False)
        cands_l4 = [int(l3s[0]) * 8 + j for j in range(8)]
        drop_l4 = rng.choice(cands_l4, size=4, replace=False)
        grants = [f"node_L3_{int(x)}" for x in l3s]
        denies = [f"node_L4_{int(x)}" for x in drop_l4]
    elif abs(s_target - 0.01) < 1e-6:
        # 1 L2 lob (512 docs) minus 3 L3 depts (192 docs -> 320 active docs, ~5,107 chunks)
        l2 = int(rng.integers(0, 64))
        cands_l3 = [l2 * 8 + j for j in range(8)]
        drop_l3 = rng.choice(cands_l3, size=3, replace=False)
        grants = [f"node_L2_{l2}"]
        denies = [f"node_L3_{int(x)}" for x in drop_l3]
    else:
        # 4 L2 lobs (2,048 docs) minus 6 L3 depts (384 docs -> 1,664 active docs, ~26,554 chunks)
        l2s = rng.choice(64, size=4, replace=False)
        cands_l3 = [int(l2) * 8 + j for l2 in l2s[:2] for j in range(8)]
        drop_l3 = rng.choice(cands_l3, size=6, replace=False)
        grants = [f"node_L2_{int(x)}" for x in l2s]
        denies = [f"node_L3_{int(x)}" for x in drop_l3]

    # Resolve exact allowed leaf docs from graph descendants
    g.positive_grants["__tmp"] = set(grants)
    g.explicit_denies["__tmp"] = set(denies)
    allowed_docs = g.lookup_resources_leaf("__tmp")
    g.positive_grants.pop("__tmp", None)
    g.explicit_denies.pop("__tmp", None)

    mask = np.zeros(N, dtype=np.bool_)
    for doc_id in allowed_docs:
        mask[overlay.doc_to_chunks[doc_id]] = True
    return grants, denies, mask


def run_r10_direct_e2e_and_ef_sweep(
    X_q: np.ndarray, Q_q: np.ndarray, logger: RawAuditLogger
) -> None:
    print("\n=== [R10] DIRECTLY TIMED E2E SAME-QUERY REQUESTS & EFSEARCH SWEEP (QUORA 523K) ===", flush=True)
    t0 = time.perf_counter()
    N, d = X_q.shape
    b, L, seed = 8, 5, 0
    overlay = build_overlay(X_q, "random", seed=seed, b=b, L=L)
    z_corpus = ZOrderedCorpus(X_q, overlay.ancestor_lineages, overlay.meaning_magnet_ids)
    l2_ids = [lin[-3] if len(lin) >= 3 else lin[-2] for lin in z_corpus.ancestor_lineages]

    rng = np.random.default_rng(20261125)
    faiss_sys = FaissHNSWSystem(X_q, M=V3_M, ef_construction=V3_EF_CONSTRUCTION, ef_search=V3_EF_SEARCH, seed=seed)
    idx_geom_m8 = GeometricHHNSW(
        z_corpus.vectors, z_corpus.primary_containers, l2_ids, z_corpus.meaning_magnet_ids,
        bridge_config=GeometricBridgeConfig.for_m_bridge(V3_M_BRIDGE, "geometric"),
        M=V3_M, seed=seed, prebuilt_faiss=(faiss_sys.index, faiss_sys.perm),
    )
    ac1 = Acorn1System(X_q, M=V3_M, ef_construction=V3_EF_CONSTRUCTION, ef_search=V3_EF_SEARCH, seed=seed, name="acorn-1", gamma=1, m_beta=32)

    # Load depth-5 hierarchy once into live native SpiceDBService
    with SpiceDBService() as sp:
        assert sp.client is not None
        print("  [R10] Loading 32,768-doc depth-5 hierarchy into live SpiceDBService...", flush=True)
        sp.load_hierarchy(overlay.auth_graph)

        # Pre-write 5 * 25 = 125 distinct principals into SpiceDB & mirror graph so each query uses real tuples
        selectivities = (0.0001, 0.001, 0.005, 0.01, 0.05)
        n_q = 25
        k = 10
        workload: List[Tuple[float, int, str, np.ndarray, np.ndarray, Set[int]]] = []
        updates_all: List[RelationshipUpdate] = []

        for s_val in selectivities:
            q_picks = rng.choice(len(Q_q), size=n_q, replace=False)
            s_slug = str(s_val).replace(".", "_")
            for qi_loc, qi in enumerate(q_picks):
                pid = f"r10_s{s_slug}_q{qi_loc}"
                grants, denies, mask = _make_quora_policy_and_mask(s_val, rng, overlay, N)
                overlay.auth_graph.positive_grants[pid] = set(grants)
                overlay.auth_graph.explicit_denies[pid] = set(denies)
                for gr in grants:
                    updates_all.append(RelationshipUpdate(
                        operation=RelationshipUpdate.OPERATION_TOUCH,
                        relationship=_rel(_node_type(gr), gr, "viewer", "user", pid),
                    ))
                for dn in denies:
                    updates_all.append(RelationshipUpdate(
                        operation=RelationshipUpdate.OPERATION_TOUCH,
                        relationship=_rel(_node_type(dn), dn, "ethical_wall_deny", "user", pid),
                    ))
                qv = np.ascontiguousarray(Q_q[int(qi)], dtype=np.float32)
                gt = set(_exact_top_k(X_q, qv, mask, k=k))
                workload.append((s_val, qi_loc, pid, qv, mask, gt))

        sp._write_updates(updates_all)
        zt_ready = sp.last_zed_token
        doc_to_orig_arr = overlay.doc_to_chunks  # doc_id -> np.ndarray of orig chunk IDs

        # Brief warmup across all systems (gRPC connection + C++ page residency) prior to timing
        _w_pid = workload[0][2]
        _ = sp.lookup_resources_docs(_w_pid, zed_token=zt_ready)
        _ = sp.read_principal_grants_and_denies(_w_pid, zed_token=zt_ready)
        _ws = np.asarray([0], dtype=np.int32)
        _we = np.asarray([64], dtype=np.int32)
        _wq8 = np.zeros(d, dtype=np.int8)
        _ = mode3_scan_ranges_f32(z_corpus.vectors, Q_q[0], _ws, _we, k=k)
        _ = mode3_scan_ranges_sq8(z_corpus.sq8_vectors, z_corpus.vectors, _wq8, Q_q[0], _ws, _we, k=k, rerank_k=64)

        # -------------------------------------------------------------------
        # Track A: Directly Timed Single-Timer E2E Same-Query Execution
        # -------------------------------------------------------------------
        for s_val, qi_loc, pid, qv, mask, gt in workload:
            denom = float(len(gt)) if gt else 1.0
            s_actual = float(mask.mean())

            # 1. FAISS HNSW M=16 E2E: LookupResources -> mask + packbits + IDSelectorBitmap -> FAISS C++
            te0 = time.perf_counter_ns()
            sp_docs = sp.lookup_resources_docs(pid, zed_token=zt_ready)
            m_f = np.zeros(N, dtype=np.bool_)
            for doc_id in sp_docs:
                m_f[doc_to_orig_arr[doc_id]] = True
            int_mask = m_f[faiss_sys.internal_to_orig]
            packed = np.packbits(int_mask, bitorder="little")
            sel = faiss.IDSelectorBitmap(N, faiss.swig_ptr(packed))
            params = faiss.SearchParametersHNSW(efSearch=V3_EF_SEARCH, sel=sel)
            q_mat = np.ascontiguousarray(qv.reshape(1, -1), dtype=np.float32)
            faiss.cvar.hnsw_stats.reset()
            _, I_f = faiss_sys.index.search(q_mat, k, params=params)
            e2e_f_ms = (time.perf_counter_ns() - te0) / 1e6
            ndis_f = int(faiss.cvar.hnsw_stats.ndis)
            ids_f = [int(faiss_sys.internal_to_orig[i]) for i in I_f[0] if i >= 0]
            leaks_f = sum(1 for nid in ids_f if nid < 0 or nid >= N or not bool(mask[nid]))
            logger.log("R10_direct_e2e", {
                "S_target": s_val, "S_actual": s_actual, "query_idx": qi_loc,
                "system": "faiss-hnsw-M16", "recall": len(set(ids_f) & gt) / denom,
                "leaks": leaks_f, "dist": ndis_f, "e2e_live_ms": e2e_f_ms, "e2e_mirror_ms": None,
            })

            # 2. ACORN-1 E2E: LookupResources -> uint8 perm map -> C++ acorn_search_one
            te0 = time.perf_counter_ns()
            sp_docs = sp.lookup_resources_docs(pid, zed_token=zt_ready)
            m_a = np.zeros(N, dtype=np.bool_)
            for doc_id in sp_docs:
                m_a[doc_to_orig_arr[doc_id]] = True
            fmap = np.ascontiguousarray(m_a[ac1.perm], dtype=np.uint8)
            out_ids_a = np.full(k, -1, dtype=np.int64)
            out_dists_a = np.zeros(k, dtype=np.float32)
            ndis_a = int(ac1.lib.acorn_search_one(
                ac1.handle, qv.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                k, V3_EF_SEARCH, fmap.ctypes.data_as(ctypes.c_char_p),
                out_ids_a.ctypes.data_as(ctypes.POINTER(ctypes.c_int64)),
                out_dists_a.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            ))
            e2e_a_ms = (time.perf_counter_ns() - te0) / 1e6
            ids_a = [int(ac1.perm[i]) for i in out_ids_a if i >= 0]
            leaks_a = sum(1 for nid in ids_a if nid < 0 or nid >= N or not bool(mask[nid]))
            logger.log("R10_direct_e2e", {
                "S_target": s_val, "S_actual": s_actual, "query_idx": qi_loc,
                "system": "acorn-1", "recall": len(set(ids_a) & gt) / denom,
                "leaks": leaks_a, "dist": ndis_a, "e2e_live_ms": e2e_a_ms, "e2e_mirror_ms": None,
            })

            # 3. RACORN-1-Fallback E2E: LookupResources -> Z-order mask ranges -> C++ rejected-node fallback
            te0 = time.perf_counter_ns()
            sp_docs = sp.lookup_resources_docs(pid, zed_token=zt_ready)
            m_r = np.zeros(N, dtype=np.bool_)
            for doc_id in sp_docs:
                m_r[doc_to_orig_arr[doc_id]] = True
            st_r_s, en_r_s, _ = bool_mask_to_range_arrays(m_r[z_corpus.z_to_orig])
            ranges_set_bitset(st_r_s, en_r_s, idx_geom_m8._mask_bits, N)
            ep_r = idx_geom_m8._next_epoch()
            z_ids_r, _, st_r = search_hhnsw_gls_cpp(
                vectors=idx_geom_m8.vectors, entry_point=idx_geom_m8.entry_point, max_level=idx_geom_m8.max_level,
                upper_offsets=idx_geom_m8.upper_offsets, upper_neighbors=idx_geom_m8.upper_neighbors,
                cum_nn_per_lvl=idx_geom_m8.cum_nn_per_lvl, base_neighbors=idx_geom_m8.base_neighbors,
                express_bridges=None, mask_bits=idx_geom_m8._mask_bits,
                starts=st_r_s, ends=en_r_s, query=qv, k=k, ef_search=V3_EF_SEARCH,
                tau_high=1.1, tau_low=0.05, use_express_bridges=False, use_portals=False,
                max_portals=0, use_gls_adaptive=True, faiss_style_1hop=False,
                tau_stall=0.0, stall_check_hops=16,
                visited_epoch=idx_geom_m8._visited_epoch, current_epoch=ep_r,
            )
            ranges_clear_bitset(st_r_s, en_r_s, idx_geom_m8._mask_bits, N)
            e2e_rac_ms = (time.perf_counter_ns() - te0) / 1e6
            ids_r = [int(z_corpus.z_to_orig[zid]) for zid in z_ids_r if zid >= 0]
            leaks_r = sum(1 for nid in ids_r if nid < 0 or nid >= N or not bool(mask[nid]))
            logger.log("R10_direct_e2e", {
                "S_target": s_val, "S_actual": s_actual, "query_idx": qi_loc,
                "system": "racorn-1-fallback", "recall": len(set(ids_r) & gt) / denom,
                "leaks": leaks_r, "dist": int(st_r.dist_computations), "e2e_live_ms": e2e_rac_ms, "e2e_mirror_ms": None,
            })

            # Helper running UBP directly timed (both live ReadRelationships RPC + mirror mode)
            def _run_prism_e2e(mode_kind: str, use_live_rpc: bool) -> Tuple[List[int], int, float]:
                t_start = time.perf_counter_ns()
                if use_live_rpc:
                    gr_rpc, dn_rpc = sp.read_principal_grants_and_denies(pid, zed_token=zt_ready)
                    overlay.auth_graph.positive_grants["__rpc_tmp"] = gr_rpc
                    overlay.auth_graph.explicit_denies["__rpc_tmp"] = dn_rpc
                    t_pos, t_neg = resolve_ubp_tokens(overlay.auth_graph, "__rpc_tmp")
                else:
                    t_pos, t_neg = resolve_ubp_tokens(overlay.auth_graph, pid)
                b_acl = z_corpus.compile_acl_bitmap_ubp(t_pos, t_neg)
                starts, ends, n_cand = runs_to_range_arrays(b_acl)
                s_loc = n_cand / float(N)

                if mode_kind == "v3-geom-M8" or (s_loc > 0.015 and n_cand > 500):
                    ranges_set_bitset(starts, ends, idx_geom_m8._mask_bits, N)
                    ep = idx_geom_m8._next_epoch()
                    tau_st = V3_TAU_STALL if (mode_kind != "v3-geom-M8" and n_cand <= V3_N_GUARD) else 0.0
                    z_ids, _, st = search_hhnsw_gls_cpp(
                        vectors=idx_geom_m8.vectors, entry_point=idx_geom_m8.entry_point, max_level=idx_geom_m8.max_level,
                        upper_offsets=idx_geom_m8.upper_offsets, upper_neighbors=idx_geom_m8.upper_neighbors,
                        cum_nn_per_lvl=idx_geom_m8.cum_nn_per_lvl, base_neighbors=idx_geom_m8.base_neighbors,
                        express_bridges=idx_geom_m8.express_bridges, mask_bits=idx_geom_m8._mask_bits,
                        starts=starts, ends=ends, query=qv, k=k, ef_search=V3_EF_SEARCH,
                        tau_high=V3_TAU_HIGH, tau_low=V3_TAU_LOW, use_express_bridges=True, use_portals=True,
                        max_portals=V3_MAX_PORTALS, use_gls_adaptive=True, faiss_style_1hop=False,
                        tau_stall=tau_st, stall_check_hops=16,
                        visited_epoch=idx_geom_m8._visited_epoch, current_epoch=ep,
                    )
                    ranges_clear_bitset(starts, ends, idx_geom_m8._mask_bits, N)
                    ev = int(st.dist_computations)
                    if tau_st > 0.0 and st.stalled:
                        if mode_kind == "v3-full-guard-f32":
                            z_ids, _, m3ev = mode3_scan_ranges_f32(z_corpus.vectors, qv, starts, ends, k=k)
                        else:
                            q_sq8 = np.ascontiguousarray(np.clip(np.round(qv * 127.0), -127, 127).astype(np.int8))
                            z_ids, _, m3ev = mode3_scan_ranges_sq8(
                                z_corpus.sq8_vectors, z_corpus.vectors, q_sq8, qv, starts, ends, k=k, rerank_k=64
                            )
                        ev += int(m3ev)
                elif mode_kind == "v3-full-guard-f32":
                    z_ids, _, ev = mode3_scan_ranges_f32(z_corpus.vectors, qv, starts, ends, k=k)
                else:
                    # Include query SQ8 quantization INSIDE the single E2E timer!
                    q_sq8 = np.ascontiguousarray(np.clip(np.round(qv * 127.0), -127, 127).astype(np.int8))
                    z_ids, _, ev = mode3_scan_ranges_sq8(
                        z_corpus.sq8_vectors, z_corpus.vectors, q_sq8, qv, starts, ends, k=k, rerank_k=64
                    )

                ms_tot = (time.perf_counter_ns() - t_start) / 1e6
                orig_ids = [int(z_corpus.z_to_orig[zid]) for zid in z_ids if zid >= 0]
                return orig_ids, int(ev), float(ms_tot)

            for m_sys in ("v3-geom-M8", "v3-full-guard-f32", "v3-full-guard-sq8"):
                ids_live, ev_l, ms_live = _run_prism_e2e(m_sys, use_live_rpc=True)
                ids_mir, _, ms_mir = _run_prism_e2e(m_sys, use_live_rpc=False)
                leaks_p = sum(1 for nid in ids_live if nid < 0 or nid >= N or not bool(mask[nid]))
                logger.log("R10_direct_e2e", {
                    "S_target": s_val, "S_actual": s_actual, "query_idx": qi_loc,
                    "system": m_sys, "recall": len(set(ids_live) & gt) / denom,
                    "leaks": leaks_p, "dist": ev_l, "e2e_live_ms": ms_live, "e2e_mirror_ms": ms_mir,
                })

            if qi_loc == n_q - 1:
                print(f"  [R10-E2E] S={s_val} done ({n_q} direct E2E queries)", flush=True)

        # -------------------------------------------------------------------
        # Track B: Matched-Recall efSearch Sweep (32, 64, 128, 256, 512)
        # -------------------------------------------------------------------
        ef_values = (32, 64, 128, 256, 512)
        for s_target in (0.005, 0.05):
            sub_wl = [w for w in workload if abs(w[0] - s_target) < 1e-6]
            for ef_val in ef_values:
                for _, qi_loc, pid, qv, mask, gt in sub_wl:
                    denom = float(len(gt)) if gt else 1.0

                    # FAISS M=16
                    int_mask = mask[faiss_sys.internal_to_orig]
                    packed = np.packbits(int_mask, bitorder="little")
                    sel = faiss.IDSelectorBitmap(N, faiss.swig_ptr(packed))
                    params = faiss.SearchParametersHNSW(efSearch=ef_val, sel=sel)
                    q_mat = np.ascontiguousarray(qv.reshape(1, -1), dtype=np.float32)
                    faiss.cvar.hnsw_stats.reset()
                    t1_0 = time.perf_counter_ns()
                    _, I_f = faiss_sys.index.search(q_mat, k, params=params)
                    c_ms = (time.perf_counter_ns() - t1_0) / 1e6
                    ids_f = [int(faiss_sys.internal_to_orig[i]) for i in I_f[0] if i >= 0]
                    logger.log("R10_ef_sweep", {
                        "S_target": s_target, "ef_search": ef_val, "query_idx": qi_loc,
                        "system": "faiss-hnsw-M16", "recall": len(set(ids_f) & gt) / denom,
                        "leaks": sum(1 for nid in ids_f if nid < 0 or nid >= N or not bool(mask[nid])),
                        "dist": int(faiss.cvar.hnsw_stats.ndis), "cpp_ms": c_ms,
                    })

                    # ACORN-1
                    fmap = np.ascontiguousarray(mask[ac1.perm], dtype=np.uint8)
                    out_ids_a = np.full(k, -1, dtype=np.int64)
                    out_dists_a = np.zeros(k, dtype=np.float32)
                    t1_0 = time.perf_counter_ns()
                    ndis_a = int(ac1.lib.acorn_search_one(
                        ac1.handle, qv.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                        k, ef_val, fmap.ctypes.data_as(ctypes.c_char_p),
                        out_ids_a.ctypes.data_as(ctypes.POINTER(ctypes.c_int64)),
                        out_dists_a.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                    ))
                    c_ms = (time.perf_counter_ns() - t1_0) / 1e6
                    ids_a = [int(ac1.perm[i]) for i in out_ids_a if i >= 0]
                    logger.log("R10_ef_sweep", {
                        "S_target": s_target, "ef_search": ef_val, "query_idx": qi_loc,
                        "system": "acorn-1", "recall": len(set(ids_a) & gt) / denom,
                        "leaks": sum(1 for nid in ids_a if nid < 0 or nid >= N or not bool(mask[nid])),
                        "dist": ndis_a, "cpp_ms": c_ms,
                    })

                    # Prepare pre-compiled bitset for RACORN-1 proxy & v3-geom-M8
                    t_pos, t_neg = resolve_ubp_tokens(overlay.auth_graph, pid)
                    b_acl = z_corpus.compile_acl_bitmap_ubp(t_pos, t_neg)
                    starts, ends, _ = runs_to_range_arrays(b_acl)
                    ranges_set_bitset(starts, ends, idx_geom_m8._mask_bits, N)
                    try:
                        # RACORN-1 proxy
                        ep_r = idx_geom_m8._next_epoch()
                        t1_0 = time.perf_counter_ns()
                        z_ids_r, _, st_r = search_hhnsw_gls_cpp(
                            vectors=idx_geom_m8.vectors, entry_point=idx_geom_m8.entry_point, max_level=idx_geom_m8.max_level,
                            upper_offsets=idx_geom_m8.upper_offsets, upper_neighbors=idx_geom_m8.upper_neighbors,
                            cum_nn_per_lvl=idx_geom_m8.cum_nn_per_lvl, base_neighbors=idx_geom_m8.base_neighbors,
                            express_bridges=None, mask_bits=idx_geom_m8._mask_bits,
                            starts=starts, ends=ends, query=qv, k=k, ef_search=ef_val,
                            tau_high=1.1, tau_low=0.05, use_express_bridges=False, use_portals=False,
                            max_portals=0, use_gls_adaptive=True, faiss_style_1hop=False,
                            tau_stall=0.0, stall_check_hops=16,
                            visited_epoch=idx_geom_m8._visited_epoch, current_epoch=ep_r,
                        )
                        c_ms = (time.perf_counter_ns() - t1_0) / 1e6
                        ids_r = [int(z_corpus.z_to_orig[zid]) for zid in z_ids_r if zid >= 0]
                        logger.log("R10_ef_sweep", {
                            "S_target": s_target, "ef_search": ef_val, "query_idx": qi_loc,
                            "system": "racorn-1-fallback", "recall": len(set(ids_r) & gt) / denom,
                            "leaks": sum(1 for nid in ids_r if nid < 0 or nid >= N or not bool(mask[nid])),
                            "dist": int(st_r.dist_computations), "cpp_ms": c_ms,
                        })

                        # v3-geom-M8
                        ep_g = idx_geom_m8._next_epoch()
                        t1_0 = time.perf_counter_ns()
                        z_ids_g, _, st_g = search_hhnsw_gls_cpp(
                            vectors=idx_geom_m8.vectors, entry_point=idx_geom_m8.entry_point, max_level=idx_geom_m8.max_level,
                            upper_offsets=idx_geom_m8.upper_offsets, upper_neighbors=idx_geom_m8.upper_neighbors,
                            cum_nn_per_lvl=idx_geom_m8.cum_nn_per_lvl, base_neighbors=idx_geom_m8.base_neighbors,
                            express_bridges=idx_geom_m8.express_bridges, mask_bits=idx_geom_m8._mask_bits,
                            starts=starts, ends=ends, query=qv, k=k, ef_search=ef_val,
                            tau_high=V3_TAU_HIGH, tau_low=V3_TAU_LOW, use_express_bridges=True, use_portals=True,
                            max_portals=V3_MAX_PORTALS, use_gls_adaptive=True, faiss_style_1hop=False,
                            tau_stall=0.0, stall_check_hops=16,
                            visited_epoch=idx_geom_m8._visited_epoch, current_epoch=ep_g,
                        )
                        c_ms = (time.perf_counter_ns() - t1_0) / 1e6
                        ids_g = [int(z_corpus.z_to_orig[zid]) for zid in z_ids_g if zid >= 0]
                        logger.log("R10_ef_sweep", {
                            "S_target": s_target, "ef_search": ef_val, "query_idx": qi_loc,
                            "system": "v3-geom-M8", "recall": len(set(ids_g) & gt) / denom,
                            "leaks": sum(1 for nid in ids_g if nid < 0 or nid >= N or not bool(mask[nid])),
                            "dist": int(st_g.dist_computations), "cpp_ms": c_ms,
                        })
                    finally:
                        ranges_clear_bitset(starts, ends, idx_geom_m8._mask_bits, N)

                print(f"  [R10-ef] S={s_target} ef={ef_val} done", flush=True)

    del ac1, idx_geom_m8, z_corpus, overlay
    gc.collect()
    print(f"[R10] DONE in {time.perf_counter()-t0:.2f}s", flush=True)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-dirty", action="store_true")
    args = ap.parse_args()

    t_all = time.perf_counter()
    fz3 = freeze_v3_status()
    assert fz3["match"], f"FREEZE_v3 mismatch! {fz3}"
    fz31 = freeze_v3_1_status()
    assert fz31["match"], f"FREEZE_v3_1 mismatch! {fz31}"
    fz33 = freeze_v3_3_status()
    assert fz33["match"], f"FREEZE_v3_3 mismatch! {fz33}"

    sha_now = git_sha()
    is_dirty = _repo_is_dirty()
    if is_dirty and not args.allow_dirty:
        raise RuntimeError("Refusing v3.3 audit on dirty working tree; commit changes first or pass --allow-dirty")

    print(
        f"[audit_v3.3] git_sha={sha_now[:10]} git_dirty={is_dirty} "
        f"freeze_v3_3=INTACT ({fz33['n_files']}/9)",
        flush=True,
    )

    X_q, Q_q, _, _ = load_corpus_v3("quora")

    logger = RawAuditLogger(RAW_OUT_PATH)
    try:
        logger.log("R0_meta", {
            "git_sha": sha_now,
            "git_dirty": bool(is_dirty),
            "freeze_v3_3_match": fz33["match"],
            "freeze_v3_3_files": fz33["n_files"],
            "quora_N": int(X_q.shape[0]),
            "r11_threads": 8,
        })
        run_r9a_independent_dag_mutations(logger)
        run_r9b_and_r11_live_spicedb(logger)
        run_r10_direct_e2e_and_ef_sweep(X_q, Q_q, logger)
    finally:
        logger.close()

    summary = recompute_v3_3_summary(RAW_OUT_PATH)
    os.makedirs(os.path.dirname(SUMMARY_OUT_PATH), exist_ok=True)
    with open(SUMMARY_OUT_PATH, "w", encoding="utf-8") as f:
        f.write(dumps_summary(summary))
    print(
        f"\n[audit_v3.3] COMPLETE in {time.perf_counter()-t_all:.2f}s | recs={summary['raw_records_total']} | "
        f"verdicts={ {k: v['verdict'] for k, v in summary['verdicts'].items()} } -> {SUMMARY_OUT_PATH}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
