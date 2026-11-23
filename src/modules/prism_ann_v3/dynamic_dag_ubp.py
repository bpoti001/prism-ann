"""
Versioned Multi-Parent DAG Ancestry & Dynamic Structural Mutation Support for Prism-ANN
=======================================================================================
Governing ADRs: ADR-0001, ADR-0005, ADR-0006.
Addresses two critical dynamic-hierarchy invariants identified in external review:
  1. Post-index hierarchy edge additions (`add_hierarchy_edge(B, D)` where B carries an
     exclusion) atomically refresh descendant posting bitmaps B_v(zeta) for revision
     zeta without touching vector storage, preventing stale-ancestry leaks in Modes 1-3.
  2. Structural edge unlinking (`remove_hierarchy_edge(A, C)` in diamond A -> C <- B)
     detaches only edge (A -> C) rather than adding C to global `revoked_subtrees`,
     preserving authorized access via surviving path B -> C (`0` false negatives).
     Whole-container quarantine uses explicit `decommission_subtree(node_id)`.
  3. Every revision `zeta` publishes an immutable `CorpusRevisionSnapshot` containing
     both the topology-synced descendant posting bitmaps `B_v(zeta)` and the frozen
     principal grant/deny state at `zeta`, enabling true snapshot-isolated concurrent reads.

Note: Preserves all frozen files in FREEZE.md (5/5), FREEZE_v3.md (7/7), and
FREEZE_v3_1.md (8/8) completely untouched.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

import numpy as np

from src.modules.prism_ann.trimodal_planner import RoaringRunBitmap, ZOrderedCorpus
from src.modules.prism_ann.ubp_resolver import (
    UBPResolutionResult,
    ZanzibarAuthGraph,
    resolve_ubp_tokens,
)
from .geometric_hhnsw import GeometricBridgeConfig, GeometricHHNSW
from .trimodal_v3 import TriModalPlannerV3, TriModalResultV3, runs_to_range_arrays


__all__ = [
    "StaleOrMissingSnapshotError",
    "DynamicMultiParentAuthGraph",
    "CorpusRevisionSnapshot",
    "VersionedLineageCorpus",
    "DynamicPrismANNIndex",
]


class StaleOrMissingSnapshotError(RuntimeError):
    """Raised under fail-closed snapshot policies when no compatible revision is available."""


class DynamicMultiParentAuthGraph(ZanzibarAuthGraph):
    """
    Zanzibar / SpiceDB ReBAC Multi-Parent DAG supporting exact structural mutations:
      - `add_hierarchy_edge(parent_id, child_id)`: adds edge and advances hierarchy_version + zed_token.
      - `remove_hierarchy_edge(parent_id, child_id)`: removes ONLY edge (parent_id -> child_id),
        preserving alternative DAG paths (`A -> C <- B` keeps `B -> C` active).
      - `decommission_subtree(node_id)`: global container/subtree quarantine (`revoked_subtrees`).
      - `remove_deny_exclusion(principal_id, node_id)`: removes an explicit deny wall.
    """

    def __init__(self, branching_factor: int = 8, depth: int = 4):
        super().__init__(branching_factor=branching_factor, depth=depth)
        self.hierarchy_version: int = 1
        self._lock = threading.RLock()

    def _ensure_node(self, node_id: str, is_leaf: Optional[bool] = None) -> None:
        if node_id not in self.all_nodes:
            self.all_nodes.add(node_id)
            self.node_depth[node_id] = 0
            self.children.setdefault(node_id, [])
            self.parents.setdefault(node_id, set())
            if is_leaf is True or (is_leaf is None and node_id.startswith("doc")):
                self.leaf_documents.add(node_id)
        elif is_leaf is True:
            self.leaf_documents.add(node_id)

    def add_hierarchy_edge(self, parent_id: str, child_id: str) -> int:
        with self._lock:
            self._ensure_node(parent_id, is_leaf=False)
            self._ensure_node(child_id, is_leaf=None)
            if parent_id in self.leaf_documents:
                self.leaf_documents.discard(parent_id)
            if child_id not in self.children.get(parent_id, []):
                self.children.setdefault(parent_id, []).append(child_id)
            self.parents.setdefault(child_id, set()).add(parent_id)
            if self.node_depth.get(child_id, 0) <= self.node_depth.get(parent_id, 0):
                self.node_depth[child_id] = self.node_depth.get(parent_id, 0) + 1
            self.revoked_subtrees.discard(child_id)
            self.hierarchy_version += 1
            self.zed_token += 1
            return self.zed_token

    def remove_hierarchy_edge(self, parent_id: str, child_id: str) -> int:
        """
        Structural unlink of ONLY the single directed edge `(parent_id -> child_id)`.
        Does NOT insert `child_id` into global `revoked_subtrees`, so alternate parent
        paths in multi-parent DAGs (`A -> C <- B`) continue granting access until all
        authorized paths are unlinked or an ancestor is denied.
        """
        with self._lock:
            ch_list = self.children.get(parent_id)
            if ch_list is not None and child_id in ch_list:
                ch_list.remove(child_id)
            p_set = self.parents.get(child_id)
            if p_set is not None:
                p_set.discard(parent_id)
            self.hierarchy_version += 1
            self.zed_token += 1
            return self.zed_token

    def unlink_hierarchy_edge(self, parent_id: str, child_id: str) -> int:
        """Alias for `remove_hierarchy_edge(parent_id, child_id)`."""
        return self.remove_hierarchy_edge(parent_id, child_id)

    def decommission_subtree(self, node_id: str) -> int:
        """Explicitly quarantines an entire container/document globally across all paths."""
        with self._lock:
            self.revoked_subtrees.add(node_id)
            self.hierarchy_version += 1
            self.zed_token += 1
            return self.zed_token

    def grant_access(self, principal_id: str, node_id: str) -> int:
        with self._lock:
            self._ensure_node(node_id, is_leaf=None)
            return super().grant_access(principal_id, node_id)

    def revoke_access(self, principal_id: str, node_id: str) -> int:
        with self._lock:
            return super().revoke_access(principal_id, node_id)

    def add_deny_exclusion(self, principal_id: str, node_id: str) -> int:
        with self._lock:
            self._ensure_node(node_id, is_leaf=None)
            return super().add_deny_exclusion(principal_id, node_id)

    def remove_deny_exclusion(self, principal_id: str, node_id: str) -> int:
        with self._lock:
            if principal_id in self.explicit_denies:
                self.explicit_denies[principal_id].discard(node_id)
            self.zed_token += 1
            return self.zed_token

    def snapshot_graph_copy(self) -> "DynamicMultiParentAuthGraph":
        """Returns an isolated immutable-use copy of the graph at the current zed_token."""
        with self._lock:
            cp = DynamicMultiParentAuthGraph(branching_factor=self.b, depth=self.L)
            cp.all_nodes = set(self.all_nodes)
            cp.node_depth = dict(self.node_depth)
            cp.leaf_documents = set(self.leaf_documents)
            cp.children = {k: list(v) for k, v in self.children.items()}
            cp.parents = {k: set(v) for k, v in self.parents.items()}
            cp.positive_grants = {k: set(v) for k, v in self.positive_grants.items()}
            cp.explicit_denies = {k: set(v) for k, v in self.explicit_denies.items()}
            cp.revoked_subtrees = set(self.revoked_subtrees)
            cp.hierarchy_version = self.hierarchy_version
            cp.zed_token = self.zed_token
            return cp


@dataclass(frozen=True)
class CorpusRevisionSnapshot:
    """Immutable atomic revision snapshot for versioned ancestry posting bitmaps & graph state."""
    zed_token: int
    hierarchy_version: int
    token_bitmaps: Dict[str, RoaringRunBitmap]
    auth_snapshot: DynamicMultiParentAuthGraph


class VersionedLineageCorpus:
    """
    Maintains immutable Z-ordered vector buffers alongside atomically versioned
    descendant posting bitmaps `B_v(zeta) = {z_id : v in Anc_{G(zeta)}(doc(z_id))}`.

    On structural DAG mutations (`add_hierarchy_edge`, `remove_hierarchy_edge`),
    `sync_to_revision()` updates posting bitmaps cleanly without mutating or moving
    any FP32 vector, SQ8 buffer, or HNSW graph edge (`0` vector writes).
    """

    def __init__(
        self,
        auth_graph: DynamicMultiParentAuthGraph,
        raw_vectors: np.ndarray,
        leaf_doc_ids: Optional[List[str]] = None,
        ancestor_lineages: Optional[List[List[str]]] = None,
        meaning_magnet_ids: Optional[List[str]] = None,
    ):
        if ancestor_lineages is None:
            if leaf_doc_ids is None:
                raise ValueError("Provide either leaf_doc_ids or ancestor_lineages.")
            ancestor_lineages = [auth_graph.get_ancestor_lineage(d) for d in leaf_doc_ids]
        n = len(ancestor_lineages)
        if meaning_magnet_ids is None:
            meaning_magnet_ids = ["mag_default"] * n

        self.z_corpus = ZOrderedCorpus(
            raw_vectors=raw_vectors,
            ancestor_lineages=ancestor_lineages,
            meaning_magnet_ids=meaning_magnet_ids,
        )
        if leaf_doc_ids is not None:
            self.z_leaf_doc_ids: List[str] = [leaf_doc_ids[int(i)] for i in self.z_corpus.z_to_orig]
        else:
            self.z_leaf_doc_ids = list(self.z_corpus.leaf_doc_ids)

        for doc_id in self.z_leaf_doc_ids:
            auth_graph.add_node(doc_id, depth_level=auth_graph.node_depth.get(doc_id, 1), is_leaf=True)

        self.doc_to_z_ids: Dict[str, List[int]] = {}
        for z_id, doc_id in enumerate(self.z_leaf_doc_ids):
            self.doc_to_z_ids.setdefault(doc_id, []).append(z_id)

        self._lock = threading.RLock()
        self._snapshots: Dict[int, CorpusRevisionSnapshot] = {}
        self._latest_snapshot: Optional[CorpusRevisionSnapshot] = None
        self._min_retained_zed_token: int = 0
        self.sync_to_revision(auth_graph)

    def _compute_token_bitmaps(self, auth_graph: DynamicMultiParentAuthGraph) -> Dict[str, RoaringRunBitmap]:
        """
        Computes exact reachability postings B_v(zeta) = {z_id : v in Anc_{G(zeta)}(doc(z_id))}
        across the full upstream ancestor cone of every leaf document.

        Why naive `B_{p1} <- B_{p1} \\ B_c` is insufficient on general DAGs:
        if an alternate path `p1 -> x -> c` remains after removing `p1 -> c`, blind set
        difference falsely deletes `c`'s chunks from `B_{p1}` and fails to propagate
        reachability changes upward to ancestors `a in Anc(p1)`. Traversing exact
        `auth_graph.parents` guarantees both surviving diamond paths and upstream propagation.
        """
        token_to_ids: Dict[str, List[int]] = {}
        for doc_id, z_ids in self.doc_to_z_ids.items():
            visited: Set[str] = {doc_id}
            q = deque([doc_id])
            while q:
                curr = q.popleft()
                token_to_ids.setdefault(curr, []).extend(z_ids)
                for p in auth_graph.parents.get(curr, ()):
                    if p not in visited:
                        visited.add(p)
                        q.append(p)

        out: Dict[str, RoaringRunBitmap] = {}
        for tok, id_list in token_to_ids.items():
            id_list_sorted = sorted(set(id_list))
            out[tok] = RoaringRunBitmap.from_sorted_ids(id_list_sorted, self.z_corpus.N)
        return out

    def sync_to_revision(self, auth_graph: DynamicMultiParentAuthGraph) -> CorpusRevisionSnapshot:
        """Atomically compiles and publishes an immutable snapshot for `auth_graph.zed_token`."""
        with self._lock:
            zt = auth_graph.zed_token
            hv = auth_graph.hierarchy_version
            if self._latest_snapshot is not None and self._latest_snapshot.zed_token == zt:
                return self._latest_snapshot
            if self._latest_snapshot is not None and self._latest_snapshot.hierarchy_version == hv:
                bitmaps = self._latest_snapshot.token_bitmaps
            else:
                bitmaps = self._compute_token_bitmaps(auth_graph)
                self.z_corpus.token_bitmaps = bitmaps
            snap = CorpusRevisionSnapshot(
                zed_token=zt,
                hierarchy_version=hv,
                token_bitmaps=bitmaps,
                auth_snapshot=auth_graph.snapshot_graph_copy(),
            )
            self._snapshots[zt] = snap
            self._latest_snapshot = snap
            return snap

    def evict_snapshots_before(self, min_zed_token: int) -> int:
        """
        Models SpiceDB GC / snapshot expiration windows by evicting historical snapshots
        with `zt < min_zed_token` (preserving `_latest_snapshot` unless
        `min_zed_token > _latest_snapshot.zed_token`). Returns count evicted.
        """
        with self._lock:
            self._min_retained_zed_token = max(self._min_retained_zed_token, min_zed_token)
            latest_zt = self._latest_snapshot.zed_token if self._latest_snapshot is not None else None
            to_remove = [
                zt
                for zt in self._snapshots
                if zt < min_zed_token and (latest_zt is None or zt != latest_zt or min_zed_token > latest_zt)
            ]
            for zt in to_remove:
                self._snapshots.pop(zt, None)
            if latest_zt is not None and min_zed_token > latest_zt:
                self._latest_snapshot = None
            return len(to_remove)

    def get_snapshot(
        self,
        auth_graph: DynamicMultiParentAuthGraph,
        zed_token: Optional[int] = None,
        consistency_mode: str = "at_least_as_fresh",
        on_unavailable: str = "fail_closed",
        auto_sync: bool = True,
    ) -> Optional[CorpusRevisionSnapshot]:
        if consistency_mode not in ("at_least_as_fresh", "at_exact_snapshot"):
            raise ValueError(f"Unsupported consistency_mode: {consistency_mode}")
        if on_unavailable not in ("fail_closed", "safe_leaf_fallback"):
            raise ValueError(f"Unsupported on_unavailable policy: {on_unavailable}")

        with self._lock:
            if consistency_mode == "at_exact_snapshot":
                req_zt = auth_graph.zed_token if zed_token is None else zed_token
                if req_zt in self._snapshots:
                    return self._snapshots[req_zt]
                if auto_sync and req_zt == auth_graph.zed_token and req_zt >= self._min_retained_zed_token:
                    return self.sync_to_revision(auth_graph)
                if on_unavailable == "fail_closed":
                    raise StaleOrMissingSnapshotError(
                        f"Exact snapshot zed_token={req_zt} is unavailable or expired."
                    )
                return None

            # consistency_mode == "at_least_as_fresh"
            min_zt = auth_graph.zed_token if zed_token is None else zed_token
            if zed_token is not None and zed_token > auth_graph.zed_token:
                raise StaleOrMissingSnapshotError(
                    f"Requested zed_token={zed_token} exceeds current auth_graph.zed_token={auth_graph.zed_token}."
                )

            snap = self._latest_snapshot
            compatible = (
                snap is not None
                and snap.zed_token >= min_zt
                and snap.hierarchy_version == auth_graph.hierarchy_version
            )
            if compatible:
                return snap

            if auto_sync and (zed_token is None or zed_token <= auth_graph.zed_token):
                return self.sync_to_revision(auth_graph)

            if on_unavailable == "fail_closed":
                cur_zt = snap.zed_token if snap is not None else None
                cur_hv = snap.hierarchy_version if snap is not None else None
                raise StaleOrMissingSnapshotError(
                    f"No compatible snapshot for min_zed_token={min_zt}, hierarchy_version={auth_graph.hierarchy_version} "
                    f"(latest={cur_zt}, latest_hv={cur_hv})."
                )
            return None

    def compile_safe_leaf_fallback_bitmap(
        self, auth_graph: DynamicMultiParentAuthGraph, principal_id: str
    ) -> RoaringRunBitmap:
        """Direct leaf-oracle bitmap compilation used when `on_unavailable='safe_leaf_fallback'`."""
        allowed_docs = auth_graph.lookup_resources_leaf(principal_id)
        z_ids: List[int] = []
        for d_id in allowed_docs:
            z_ids.extend(self.doc_to_z_ids.get(d_id, ()))
        z_ids.sort()
        return RoaringRunBitmap.from_sorted_ids(z_ids, self.z_corpus.N)

    def compile_acl_bitmap_ubp(
        self,
        tokens_pos: Set[str],
        tokens_neg: Set[str],
        snapshot: Optional[CorpusRevisionSnapshot] = None,
    ) -> RoaringRunBitmap:
        tmap = snapshot.token_bitmaps if snapshot is not None else self.z_corpus.token_bitmaps
        pos_bms = [tmap[t] for t in tokens_pos if t in tmap]
        b_pos = RoaringRunBitmap.union_all(pos_bms, self.z_corpus.N)
        if not tokens_neg:
            return b_pos
        neg_bms = [tmap[z] for z in tokens_neg if z in tmap]
        b_neg = RoaringRunBitmap.union_all(neg_bms, self.z_corpus.N)
        return b_pos.difference(b_neg)


class DynamicPrismANNIndex:
    """
    Production-safe Prism-ANN v3 facade supporting post-index hierarchy edge
    additions, multi-parent edge unlinks, explicit subtree decommissioning, and
    atomic ZedToken-pinned snapshot queries across Modes 1, 2, and 3 (`0` vector writes).
    """

    def __init__(
        self,
        auth_graph: DynamicMultiParentAuthGraph,
        raw_vectors: np.ndarray,
        leaf_doc_ids: Optional[List[str]] = None,
        ancestor_lineages: Optional[List[List[str]]] = None,
        meaning_magnet_ids: Optional[List[str]] = None,
        M: int = 16,
        m_bridge: int = 8,
        ef_construction: int = 64,
        ef_search: int = 64,
        tau_high: float = 0.55,
        tau_low: float = 0.02,
        tau_stall: float = 0.04,
        n_guard: int = 25_000,
        mode3_precision: str = "f32",
        seed: int = 42,
    ):
        self.auth_graph = auth_graph
        self.vcorpus = VersionedLineageCorpus(
            auth_graph=auth_graph,
            raw_vectors=raw_vectors,
            leaf_doc_ids=leaf_doc_ids,
            ancestor_lineages=ancestor_lineages,
            meaning_magnet_ids=meaning_magnet_ids,
        )
        self.z_corpus = self.vcorpus.z_corpus
        l2_containers = [
            lin[-3] if len(lin) >= 3 else (lin[-2] if len(lin) >= 2 else lin[-1])
            for lin in self.z_corpus.ancestor_lineages
        ]
        self.hhnsw = GeometricHHNSW(
            vectors=self.z_corpus.vectors,
            l3_container_ids=self.z_corpus.primary_containers,
            l2_container_ids=l2_containers,
            meaning_magnet_ids=self.z_corpus.meaning_magnet_ids,
            bridge_config=GeometricBridgeConfig.for_m_bridge(m_bridge, "geometric"),
            M=M,
            ef_construction=ef_construction,
            seed=seed,
        )
        self.planner = TriModalPlannerV3(
            auth_graph=self.auth_graph,
            z_corpus=self.z_corpus,
            hhnsw=self.hhnsw,
            ef_search=ef_search,
            tau_high=tau_high,
            tau_low=tau_low,
            tau_stall=tau_stall,
            n_guard=n_guard,
            mode3_precision=mode3_precision,
        )

    def sync(self) -> CorpusRevisionSnapshot:
        """Publishes the latest atomic ancestry snapshot matching `self.auth_graph.zed_token`."""
        return self.vcorpus.sync_to_revision(self.auth_graph)

    def search(
        self,
        query_vec: np.ndarray,
        principal_id: str,
        concept_ids: Optional[Set[str]] = None,
        k: int = 10,
        zed_token: Optional[int] = None,
        consistency_mode: str = "at_least_as_fresh",
        on_unavailable: str = "fail_closed",
        auto_sync: bool = True,
    ) -> TriModalResultV3:
        snap = self.vcorpus.get_snapshot(
            self.auth_graph,
            zed_token=zed_token,
            consistency_mode=consistency_mode,
            on_unavailable=on_unavailable,
            auto_sync=auto_sync,
        )
        if snap is None:
            b_acl = self.vcorpus.compile_safe_leaf_fallback_bitmap(self.auth_graph, principal_id)
        else:
            tokens_pos, tokens_neg = resolve_ubp_tokens(snap.auth_snapshot, principal_id)
            b_acl = self.vcorpus.compile_acl_bitmap_ubp(tokens_pos, tokens_neg, snapshot=snap)
        if concept_ids:
            b_ont = self.z_corpus.compile_ontology_bitmap(concept_ids)
            b_phi = b_ont.intersect(b_acl)
        else:
            b_phi = b_acl
        starts, ends, n_cand = runs_to_range_arrays(b_phi)
        return self.planner.query_with_ranges(
            query_vec=query_vec,
            starts=starts,
            ends=ends,
            n_cand=n_cand,
            k=k,
        )

    def add_hierarchy_edge(self, parent_id: str, child_id: str) -> int:
        zt = self.auth_graph.add_hierarchy_edge(parent_id, child_id)
        self.sync()
        return zt

    def remove_hierarchy_edge(self, parent_id: str, child_id: str) -> int:
        zt = self.auth_graph.remove_hierarchy_edge(parent_id, child_id)
        self.sync()
        return zt

    def revoke_hierarchy_edge(self, parent_id: str, child_id: str) -> int:
        return self.remove_hierarchy_edge(parent_id, child_id)

    def decommission_subtree(self, node_id: str) -> int:
        zt = self.auth_graph.decommission_subtree(node_id)
        self.sync()
        return zt
