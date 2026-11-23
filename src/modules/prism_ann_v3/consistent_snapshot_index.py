"""
Atomic Snapshot Publication & Opaque External ZedToken Consistency for Prism-ANN v3.4
=====================================================================================
Governing ADRs: ADR-0001, ADR-0005, ADR-0006.

Research prototype facade closing two concurrency and revision-mapping gaps
identified in the November 23, 2026 source review of commit `378d290`
(while leaving frozen `src/modules/prism_ann_v3/dynamic_dag_ubp.py` byte-identical
under `FREEZE_v3_3.md` for full provenance of the `v3.3` campaign):

  1. **Atomic Snapshot Publication (Closes `sync_to_revision` Race):**
     `AtomicVersionedLineageCorpus.sync_to_revision()` first captures a single
     consistent point-in-time graph copy via `auth_graph.snapshot_graph_copy()`
     under `auth_graph._lock`, derives `zed_token`, `hierarchy_version`, and all
     reachability postings `B_v(zeta)` strictly from that frozen copy (never
     re-reading the live mutable `auth_graph`), and publishes under an explicit
     monotonic ordering policy so concurrent slower publishers for older
     revisions can never overwrite a newer `_latest_snapshot`.

  2. **Opaque External SpiceDB ZedToken Binding & Authoritative Fallback:**
     `ConsistentDynamicPrismANNIndex` tracks an explicit mirror-ingestion ledger
     mapping opaque external SpiceDB `ZedToken` strings to published local
     snapshots (`_ext_to_local`, `_evicted_ext_tokens`). When a caller supplies
     an `external_zed_token`:
       - `at_least_as_fresh(opaque_zt)` succeeds using a local snapshot ONLY if
         `opaque_zt` has already been ingested into the mirror ledger and the
         latest snapshot is at or newer than that ingested revision (permitting
         SpiceDB's valid newer-revision evaluation). Any un-ingested external
         token (mirror lag) is NEVER treated as compatible.
       - `at_exact_snapshot(opaque_zt)` succeeds ONLY if the exact bound
         snapshot is present and has not been evicted by the GC window.
       - When compatibility cannot be established, the index either fails closed
         (`StaleOrMissingSnapshotError`, default) or executes an authoritative
         external SpiceDB lookup (`on_unavailable="spicedb_leaf_fallback"`),
         never silently trusting an unverified lagging local mirror graph.

Scope note: This module is a research prototype demonstrating atomic local
snapshot publication and fail-closed / authoritative-fallback revision checks;
automatic distributed SpiceDB `Watch`-stream ingestion across multi-node vector
clusters remains future systems engineering work.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np

from src.modules.prism_ann.trimodal_planner import RoaringRunBitmap, ZOrderedCorpus
from src.modules.prism_ann.ubp_resolver import resolve_ubp_tokens
from .dynamic_dag_ubp import (
    DynamicMultiParentAuthGraph,
    StaleOrMissingSnapshotError,
)
from .geometric_hhnsw import GeometricBridgeConfig, GeometricHHNSW
from .trimodal_v3 import TriModalPlannerV3, TriModalResultV3, runs_to_range_arrays


__all__ = [
    "StaleOrMissingSnapshotError",
    "ExternalAuthLookupFn",
    "AtomicRevisionSnapshot",
    "ConsistentSearchResult",
    "AtomicVersionedLineageCorpus",
    "ConsistentDynamicPrismANNIndex",
]

# Callable signature:
#   (principal_id, consistency_mode, external_zed_token) -> (authorized_doc_ids, served_external_zed_token)
ExternalAuthLookupFn = Callable[
    [str, str, Optional[str]],
    Tuple[Set[str], Optional[str]],
]


@dataclass(frozen=True)
class AtomicRevisionSnapshot:
    """
    Immutable point-in-time snapshot where `zed_token`, `hierarchy_version`,
    `token_bitmaps`, and `auth_snapshot` are all derived from one frozen copy
    of `DynamicMultiParentAuthGraph`.
    """

    zed_token: int
    hierarchy_version: int
    token_bitmaps: Dict[str, RoaringRunBitmap]
    auth_snapshot: DynamicMultiParentAuthGraph
    external_zed_token: Optional[str] = None


@dataclass(frozen=True)
class ConsistentSearchResult:
    """Search output augmented with revision provenance & fallback telemetry."""

    result: TriModalResultV3
    selected_local_revision: Optional[int]
    selected_external_zed_token: Optional[str]
    indexed_hierarchy_version: Optional[int]
    consistency_mode: str
    fallback_used: Optional[str] = None


class AtomicVersionedLineageCorpus:
    """
    Race-free versioned lineage posting store for dynamic multi-parent DAGs.

    Key invariant: Every published `AtomicRevisionSnapshot` corresponds to one
    exact point-in-time graph revision (`snap.zed_token == snap.auth_snapshot.zed_token`,
    `snap.hierarchy_version == snap.auth_snapshot.hierarchy_version`, and
    `snap.token_bitmaps` equals the exact reachability bitmaps of `snap.auth_snapshot`).
    """

    def __init__(
        self,
        auth_graph: DynamicMultiParentAuthGraph,
        raw_vectors: np.ndarray,
        leaf_doc_ids: Optional[List[str]] = None,
        ancestor_lineages: Optional[List[List[str]]] = None,
        meaning_magnet_ids: Optional[List[str]] = None,
        initial_external_zed_token: Optional[str] = None,
    ):
        frozen_init = auth_graph.snapshot_graph_copy()
        if ancestor_lineages is None:
            if leaf_doc_ids is None:
                raise ValueError("Provide either leaf_doc_ids or ancestor_lineages.")
            ancestor_lineages = [frozen_init.get_ancestor_lineage(d) for d in leaf_doc_ids]
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

        with auth_graph._lock:
            for doc_id in self.z_leaf_doc_ids:
                if doc_id not in auth_graph.all_nodes:
                    auth_graph.add_node(doc_id, depth_level=auth_graph.node_depth.get(doc_id, 1), is_leaf=True)
                else:
                    auth_graph.leaf_documents.add(doc_id)

        self.doc_to_z_ids: Dict[str, List[int]] = {}
        for z_id, doc_id in enumerate(self.z_leaf_doc_ids):
            self.doc_to_z_ids.setdefault(doc_id, []).append(z_id)

        self._lock = threading.RLock()
        self._snapshots: Dict[int, AtomicRevisionSnapshot] = {}
        self._bitmaps_by_hv: Dict[int, Dict[str, RoaringRunBitmap]] = {}
        self._latest_snapshot: Optional[AtomicRevisionSnapshot] = None
        self._min_retained_zed_token: int = 0

        # Explicit mirror-ingestion ledger for opaque external SpiceDB ZedTokens.
        self._ext_to_local: Dict[str, int] = {}
        self._evicted_ext_tokens: Set[str] = set()
        self._latest_external_zed_token: Optional[str] = None

        self.sync_to_revision(auth_graph, external_zed_token=initial_external_zed_token)

    def _compute_token_bitmaps(self, frozen_graph: DynamicMultiParentAuthGraph) -> Dict[str, RoaringRunBitmap]:
        """
        Computes exact reachability postings `B_v(zeta) = {z_id : v in Anc_{G(zeta)}(doc(z_id))}`
        strictly from an already-frozen `DynamicMultiParentAuthGraph` copy.
        """
        token_to_ids: Dict[str, List[int]] = {}
        for doc_id, z_ids in self.doc_to_z_ids.items():
            visited: Set[str] = {doc_id}
            q = deque([doc_id])
            while q:
                curr = q.popleft()
                token_to_ids.setdefault(curr, []).extend(z_ids)
                for p in frozen_graph.parents.get(curr, ()):
                    if p not in visited:
                        visited.add(p)
                        q.append(p)

        out: Dict[str, RoaringRunBitmap] = {}
        for tok, id_list in token_to_ids.items():
            id_list_sorted = sorted(set(id_list))
            out[tok] = RoaringRunBitmap.from_sorted_ids(id_list_sorted, self.z_corpus.N)
        return out

    def sync_to_revision(
        self,
        auth_graph: DynamicMultiParentAuthGraph,
        external_zed_token: Optional[str] = None,
        on_after_capture: Optional[Callable[[int, int], None]] = None,
        on_after_postings: Optional[Callable[[int, int], None]] = None,
    ) -> AtomicRevisionSnapshot:
        """
        Atomically captures a consistent point-in-time graph snapshot under
        `auth_graph._lock`, computes all reachability postings strictly from
        that frozen snapshot, and publishes under a monotonic revision-ordering
        policy so slower concurrent publishers never regress `_latest_snapshot`.

        Optional `on_after_capture` and `on_after_postings` hooks exist solely
        for deterministic concurrency fault-injection tests (Experiment R12a).
        """
        # Step 1: Capture ONE consistent graph snapshot atomically under auth_graph._lock.
        frozen_graph = auth_graph.snapshot_graph_copy()
        zt = frozen_graph.zed_token
        hv = frozen_graph.hierarchy_version

        if on_after_capture is not None:
            on_after_capture(zt, hv)

        # Step 2: Derive postings strictly from `frozen_graph` (reusing immutable
        # bitmaps only when an exact matching hierarchy_version is already cached).
        with self._lock:
            cached_bitmaps = self._bitmaps_by_hv.get(hv)
        if cached_bitmaps is not None:
            bitmaps = cached_bitmaps
        else:
            bitmaps = self._compute_token_bitmaps(frozen_graph)

        if on_after_postings is not None:
            on_after_postings(zt, hv)

        # Step 3: Publish under corpus lock with strict monotonic ordering policy.
        with self._lock:
            if zt < self._min_retained_zed_token:
                raise StaleOrMissingSnapshotError(
                    f"Captured revision zed_token={zt} fell behind GC horizon {self._min_retained_zed_token}."
                )

            if hv not in self._bitmaps_by_hv:
                self._bitmaps_by_hv[hv] = bitmaps
            else:
                bitmaps = self._bitmaps_by_hv[hv]

            existing = self._snapshots.get(zt)
            if existing is not None:
                # If binding an external ZedToken to an already-published local revision,
                # record the binding cleanly without altering the frozen snapshot state.
                if external_zed_token is not None and existing.external_zed_token is None:
                    snap = AtomicRevisionSnapshot(
                        zed_token=existing.zed_token,
                        hierarchy_version=existing.hierarchy_version,
                        token_bitmaps=existing.token_bitmaps,
                        auth_snapshot=existing.auth_snapshot,
                        external_zed_token=external_zed_token,
                    )
                    self._snapshots[zt] = snap
                    self._ext_to_local[external_zed_token] = zt
                    if self._latest_snapshot is not None and self._latest_snapshot.zed_token == zt:
                        self._latest_snapshot = snap
                        self._latest_external_zed_token = external_zed_token
                    return snap
                if external_zed_token is not None:
                    self._ext_to_local[external_zed_token] = zt
                return existing

            snap = AtomicRevisionSnapshot(
                zed_token=zt,
                hierarchy_version=hv,
                token_bitmaps=bitmaps,
                auth_snapshot=frozen_graph,
                external_zed_token=external_zed_token,
            )
            self._snapshots[zt] = snap
            if external_zed_token is not None:
                self._ext_to_local[external_zed_token] = zt

            # Monotonic ordering policy: only advance `_latest_snapshot` when strictly newer.
            if self._latest_snapshot is None or zt > self._latest_snapshot.zed_token:
                self._latest_snapshot = snap
                self.z_corpus.token_bitmaps = bitmaps
                if external_zed_token is not None:
                    self._latest_external_zed_token = external_zed_token

            return snap

    def verify_snapshot_internal_consistency(self, snap: AtomicRevisionSnapshot) -> Dict[str, Any]:
        """
        Independently verifies that `snap` corresponds to a single complete graph
        revision (no torn label/posting/permission mixing).
        """
        recomputed = self._compute_token_bitmaps(snap.auth_snapshot)
        zt_ok = snap.zed_token == snap.auth_snapshot.zed_token
        hv_ok = snap.hierarchy_version == snap.auth_snapshot.hierarchy_version
        keys_ok = set(snap.token_bitmaps.keys()) == set(recomputed.keys())
        bitmap_mismatches = 0
        if keys_ok:
            for k, bm in recomputed.items():
                if snap.token_bitmaps[k].to_id_set() != bm.to_id_set():
                    bitmap_mismatches += 1
        else:
            bitmap_mismatches = len(set(snap.token_bitmaps.keys()) ^ set(recomputed.keys()))
        return {
            "consistent": bool(zt_ok and hv_ok and keys_ok and bitmap_mismatches == 0),
            "zt_match": zt_ok,
            "hv_match": hv_ok,
            "keys_match": keys_ok,
            "bitmap_mismatches": bitmap_mismatches,
            "snap_zed_token": snap.zed_token,
            "auth_zed_token": snap.auth_snapshot.zed_token,
            "snap_hv": snap.hierarchy_version,
            "auth_hv": snap.auth_snapshot.hierarchy_version,
        }

    def evict_snapshots_before(self, min_zed_token: int) -> int:
        """Evicts historical snapshots with `zt < min_zed_token`, tracking evicted external tokens."""
        with self._lock:
            self._min_retained_zed_token = max(self._min_retained_zed_token, min_zed_token)
            latest_zt = self._latest_snapshot.zed_token if self._latest_snapshot is not None else None
            to_remove = [
                zt
                for zt in self._snapshots
                if zt < min_zed_token and (latest_zt is None or zt != latest_zt or min_zed_token > latest_zt)
            ]
            removed_set = set(to_remove)
            for zt in to_remove:
                old = self._snapshots.pop(zt, None)
                if old is not None and old.external_zed_token is not None:
                    self._evicted_ext_tokens.add(old.external_zed_token)
            for ext_tok, loc_zt in list(self._ext_to_local.items()):
                if loc_zt in removed_set:
                    self._evicted_ext_tokens.add(ext_tok)
            if latest_zt is not None and min_zed_token > latest_zt:
                if self._latest_snapshot is not None and self._latest_snapshot.external_zed_token is not None:
                    self._evicted_ext_tokens.add(self._latest_snapshot.external_zed_token)
                self._latest_snapshot = None
            return len(to_remove)

    def evict_snapshots_before_external_token(self, min_external_zed_token: str) -> int:
        """Evicts historical snapshots older than the ingested external SpiceDB ZedToken."""
        with self._lock:
            if min_external_zed_token not in self._ext_to_local:
                raise StaleOrMissingSnapshotError(
                    f"Cannot set eviction horizon to unknown external_zed_token={min_external_zed_token!r}."
                )
            return self.evict_snapshots_before(self._ext_to_local[min_external_zed_token])

    def get_snapshot(
        self,
        auth_graph: DynamicMultiParentAuthGraph,
        zed_token: Optional[int] = None,
        external_zed_token: Optional[str] = None,
        consistency_mode: str = "at_least_as_fresh",
        on_unavailable: str = "fail_closed",
        auto_sync: bool = True,
    ) -> Optional[AtomicRevisionSnapshot]:
        """
        Resolves a revision-compatible `AtomicRevisionSnapshot` honoring SpiceDB's
        `at_least_as_fresh` vs. `at_exact_snapshot` semantics.

        When `external_zed_token` is supplied:
          - Compatibility is verified STRICTLY against the mirror's ingested
            external-token ledger (`self._ext_to_local`).
          - An unrecognized `external_zed_token` (e.g., produced by an external
            SpiceDB write the local mirror has not ingested yet) NEVER matches a
            local snapshot and NEVER silently auto-syncs the lagging local mirror.
          - `at_least_as_fresh(ext)` may serve any published snapshot at or newer
            than `_ext_to_local[ext]` (even if `ext` itself has been GC-evicted,
            matching SpiceDB's newer-revision permission).
          - `at_exact_snapshot(ext)` requires the exact bound snapshot to still
            be retained (not evicted).
        """
        if consistency_mode not in ("at_least_as_fresh", "at_exact_snapshot"):
            raise ValueError(f"Unsupported consistency_mode: {consistency_mode}")
        if on_unavailable not in ("fail_closed", "spicedb_leaf_fallback"):
            raise ValueError(f"Unsupported on_unavailable policy: {on_unavailable}")

        with self._lock:
            # --- Path A: Opaque external SpiceDB ZedToken compatibility ---
            if external_zed_token is not None:
                if external_zed_token not in self._ext_to_local:
                    if on_unavailable == "fail_closed":
                        raise StaleOrMissingSnapshotError(
                            f"External SpiceDB zed_token={external_zed_token!r} has not been "
                            "ingested by the local mirror; refusing stale local evaluation."
                        )
                    return None

                req_local_zt = self._ext_to_local[external_zed_token]
                if consistency_mode == "at_exact_snapshot":
                    if external_zed_token not in self._evicted_ext_tokens and req_local_zt in self._snapshots:
                        return self._snapshots[req_local_zt]
                    if on_unavailable == "fail_closed":
                        raise StaleOrMissingSnapshotError(
                            f"Exact external snapshot zed_token={external_zed_token!r} "
                            f"(local rev {req_local_zt}) has expired or been evicted."
                        )
                    return None

                # consistency_mode == "at_least_as_fresh" for a known ingested external token:
                # SpiceDB permits serving any complete snapshot at or newer than req_local_zt.
                latest = self._latest_snapshot
                if latest is not None and latest.zed_token >= req_local_zt:
                    return latest
                if on_unavailable == "fail_closed":
                    cur = latest.zed_token if latest is not None else None
                    raise StaleOrMissingSnapshotError(
                        f"No retained snapshot at_least_as_fresh as external_zed_token="
                        f"{external_zed_token!r} (local rev {req_local_zt}, latest={cur})."
                    )
                return None

            # --- Path B: Local integer revision compatibility (no external ZedToken) ---
            with auth_graph._lock:
                cur_graph_zt = auth_graph.zed_token
                cur_graph_hv = auth_graph.hierarchy_version

            if consistency_mode == "at_exact_snapshot":
                req_zt = cur_graph_zt if zed_token is None else zed_token
                if req_zt in self._snapshots:
                    return self._snapshots[req_zt]
                if auto_sync and req_zt == cur_graph_zt and req_zt >= self._min_retained_zed_token:
                    synced = self.sync_to_revision(auth_graph)
                    if synced.zed_token == req_zt:
                        return synced
                    if req_zt in self._snapshots:
                        return self._snapshots[req_zt]
                if on_unavailable == "fail_closed":
                    raise StaleOrMissingSnapshotError(
                        f"Exact local snapshot zed_token={req_zt} is unavailable or expired."
                    )
                return None

            min_zt = cur_graph_zt if zed_token is None else zed_token
            if zed_token is not None and zed_token > cur_graph_zt:
                if on_unavailable == "fail_closed":
                    raise StaleOrMissingSnapshotError(
                        f"Requested zed_token={zed_token} exceeds current auth_graph.zed_token={cur_graph_zt}."
                    )
                return None

            latest = self._latest_snapshot
            if (
                latest is not None
                and latest.zed_token >= min_zt
                and (zed_token is not None or latest.hierarchy_version == cur_graph_hv)
            ):
                return latest

            if auto_sync and min_zt <= cur_graph_zt:
                synced = self.sync_to_revision(auth_graph)
                if synced.zed_token >= min_zt:
                    return synced

            if on_unavailable == "fail_closed":
                cur_zt = latest.zed_token if latest is not None else None
                raise StaleOrMissingSnapshotError(
                    f"No compatible snapshot for min_zed_token={min_zt} (latest={cur_zt})."
                )
            return None

    def compile_bitmap_from_authorized_docs(self, allowed_docs: Set[str]) -> RoaringRunBitmap:
        """Compiles a Z-ordered Roaring bitmap from an externally authorized document set."""
        z_ids: List[int] = []
        for d_id in allowed_docs:
            z_ids.extend(self.doc_to_z_ids.get(d_id, ()))
        z_ids.sort()
        return RoaringRunBitmap.from_sorted_ids(z_ids, self.z_corpus.N)

    def compile_acl_bitmap_ubp(
        self,
        tokens_pos: Set[str],
        tokens_neg: Set[str],
        snapshot: AtomicRevisionSnapshot,
    ) -> RoaringRunBitmap:
        tmap = snapshot.token_bitmaps
        pos_bms = [tmap[t] for t in tokens_pos if t in tmap]
        b_pos = RoaringRunBitmap.union_all(pos_bms, self.z_corpus.N)
        if not tokens_neg:
            return b_pos
        neg_bms = [tmap[z] for z in tokens_neg if z in tmap]
        b_neg = RoaringRunBitmap.union_all(neg_bms, self.z_corpus.N)
        return b_pos.difference(b_neg)


class ConsistentDynamicPrismANNIndex:
    """
    Research-prototype Prism-ANN v3.4 dynamic-DAG index facade combining:
      - race-free atomic snapshot publication (`AtomicVersionedLineageCorpus`),
      - opaque SpiceDB `ZedToken` compatibility tracking (`at_least_as_fresh` vs.
        `at_exact_snapshot`), and
      - fail-closed refusal or authoritative live SpiceDB fallback when the local
        mirror lags an external revision.
    """

    def __init__(
        self,
        auth_graph: DynamicMultiParentAuthGraph,
        raw_vectors: np.ndarray,
        leaf_doc_ids: Optional[List[str]] = None,
        ancestor_lineages: Optional[List[List[str]]] = None,
        meaning_magnet_ids: Optional[List[str]] = None,
        initial_external_zed_token: Optional[str] = None,
        external_auth_lookup: Optional[ExternalAuthLookupFn] = None,
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
        self.external_auth_lookup = external_auth_lookup
        self.vcorpus = AtomicVersionedLineageCorpus(
            auth_graph=auth_graph,
            raw_vectors=raw_vectors,
            leaf_doc_ids=leaf_doc_ids,
            ancestor_lineages=ancestor_lineages,
            meaning_magnet_ids=meaning_magnet_ids,
            initial_external_zed_token=initial_external_zed_token,
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

    def sync(
        self,
        external_zed_token: Optional[str] = None,
        on_after_capture: Optional[Callable[[int, int], None]] = None,
        on_after_postings: Optional[Callable[[int, int], None]] = None,
    ) -> AtomicRevisionSnapshot:
        """Atomically captures and publishes a revision snapshot for `self.auth_graph`."""
        return self.vcorpus.sync_to_revision(
            self.auth_graph,
            external_zed_token=external_zed_token,
            on_after_capture=on_after_capture,
            on_after_postings=on_after_postings,
        )

    def search_with_metadata(
        self,
        query_vec: np.ndarray,
        principal_id: str,
        concept_ids: Optional[Set[str]] = None,
        k: int = 10,
        zed_token: Optional[int] = None,
        external_zed_token: Optional[str] = None,
        consistency_mode: str = "at_least_as_fresh",
        on_unavailable: str = "fail_closed",
        auto_sync: bool = True,
    ) -> ConsistentSearchResult:
        """
        Executes revision-consistent filtered ANN search and returns both the
        `TriModalResultV3` hits and explicit revision/fallback telemetry.
        """
        snap = self.vcorpus.get_snapshot(
            self.auth_graph,
            zed_token=zed_token,
            external_zed_token=external_zed_token,
            consistency_mode=consistency_mode,
            on_unavailable=on_unavailable,
            auto_sync=auto_sync,
        )
        fallback_used: Optional[str] = None
        selected_local_rev: Optional[int] = None
        selected_ext_zt: Optional[str] = None
        indexed_hv: Optional[int] = None

        if snap is None:
            # Authoritative external SpiceDB fallback only — never silently trust a lagging local mirror!
            if self.external_auth_lookup is None:
                raise StaleOrMissingSnapshotError(
                    "on_unavailable='spicedb_leaf_fallback' requires a configured external_auth_lookup "
                    "provider; refusing to consult an unverified local mirror graph."
                )
            try:
                allowed_docs, served_ext_zt = self.external_auth_lookup(
                    principal_id, consistency_mode, external_zed_token
                )
            except StaleOrMissingSnapshotError:
                raise
            except Exception as exc:
                raise StaleOrMissingSnapshotError(
                    f"Authoritative external SpiceDB fallback failed for "
                    f"consistency={consistency_mode}, token={external_zed_token!r}: {exc}"
                ) from exc
            b_acl = self.vcorpus.compile_bitmap_from_authorized_docs(allowed_docs)
            fallback_used = "spicedb_leaf_fallback"
            selected_ext_zt = served_ext_zt or external_zed_token
        else:
            tokens_pos, tokens_neg = resolve_ubp_tokens(snap.auth_snapshot, principal_id)
            b_acl = self.vcorpus.compile_acl_bitmap_ubp(tokens_pos, tokens_neg, snapshot=snap)
            selected_local_rev = snap.zed_token
            selected_ext_zt = snap.external_zed_token
            indexed_hv = snap.hierarchy_version

        if concept_ids:
            b_ont = self.z_corpus.compile_ontology_bitmap(concept_ids)
            b_phi = b_ont.intersect(b_acl)
        else:
            b_phi = b_acl

        starts, ends, n_cand = runs_to_range_arrays(b_phi)
        res = self.planner.query_with_ranges(
            query_vec=query_vec,
            starts=starts,
            ends=ends,
            n_cand=n_cand,
            k=k,
        )
        return ConsistentSearchResult(
            result=res,
            selected_local_revision=selected_local_rev,
            selected_external_zed_token=selected_ext_zt,
            indexed_hierarchy_version=indexed_hv,
            consistency_mode=consistency_mode,
            fallback_used=fallback_used,
        )

    def search(
        self,
        query_vec: np.ndarray,
        principal_id: str,
        concept_ids: Optional[Set[str]] = None,
        k: int = 10,
        zed_token: Optional[int] = None,
        external_zed_token: Optional[str] = None,
        consistency_mode: str = "at_least_as_fresh",
        on_unavailable: str = "fail_closed",
        auto_sync: bool = True,
    ) -> TriModalResultV3:
        return self.search_with_metadata(
            query_vec=query_vec,
            principal_id=principal_id,
            concept_ids=concept_ids,
            k=k,
            zed_token=zed_token,
            external_zed_token=external_zed_token,
            consistency_mode=consistency_mode,
            on_unavailable=on_unavailable,
            auto_sync=auto_sync,
        ).result
