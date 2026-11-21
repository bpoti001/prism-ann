"""
Real baseline adapters & frozen-Prism adapter for Prism-ANN v2 (ADR-0004).
==========================================================================
Every adapter implements bench.harness.FilteredSearchSystem and operates in
original corpus ID space [0, N).  Frozen files under src/modules/prism_ann/
are never modified; PrismAdapter populates AncestorStitchedHNSW in memory
using FAISS HNSW level-0 adjacency lists (explicitly allowed by PROTOCOL_v2).
"""

from __future__ import annotations

import ctypes
import os
import time
from typing import Dict, List, Optional, Tuple

import faiss
import hnswlib
import numpy as np

from bench.harness import QuerySpec, SearchOutput
from src.modules.prism_ann.hnsw_gls import AncestorStitchedHNSW, search_hnsw_gls
from src.modules.prism_ann.trimodal_planner import (
    RoaringRunBitmap,
    TriModalQueryPlanner,
    ZOrderedCorpus,
)
from src.modules.prism_ann.ubp_resolver import ZanzibarAuthGraph

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACORN_DYLIB_PATH = os.path.join(REPO_ROOT, "bench", "_build", "libacorn_cwrap.dylib")


def _check_no_leak(ids: List[int], mask: np.ndarray, system_name: str) -> None:
    for nid in ids:
        if nid < 0 or nid >= len(mask) or not mask[nid]:
            raise AssertionError(f"Authorization leak in {system_name}: id={nid}")


class ExactBruteForceSystem:
    """Exact filtered brute-force inner-product search (ground truth baseline)."""

    def __init__(self, X: np.ndarray, name: str = "exact-brute-force"):
        self.name = name
        self.X = np.ascontiguousarray(X, dtype=np.float32)

    def search(self, q: QuerySpec, k: int) -> SearchOutput:
        valid = np.flatnonzero(q.mask)
        if len(valid) == 0:
            return SearchOutput(ids=[], distance_computations=0)
        sims = self.X[valid] @ q.vector
        if len(valid) <= k:
            order = np.argsort(-sims)
        else:
            part = np.argpartition(-sims, k)[:k]
            order = part[np.argsort(-sims[part])]
        ids = [int(valid[i]) for i in order[:k]]
        return SearchOutput(ids=ids, distance_computations=int(len(valid)))


class FaissHNSWSystem:
    """Real FAISS IndexHNSWFlat + IDSelectorBitmap with exact C++ hnsw_stats.ndis."""

    def __init__(
        self,
        X: np.ndarray,
        M: int = 16,
        ef_construction: int = 64,
        ef_search: int = 64,
        seed: int = 0,
        name: Optional[str] = None,
        ext_id_map: Optional[np.ndarray] = None,
    ):
        self.name = name or f"faiss-hnsw-M{M}"
        self.M = M
        self.ef_search = ef_search
        N, d = X.shape
        self.N = N
        rng = np.random.default_rng(10_000 + seed * 131 + M)
        self.perm = rng.permutation(N).astype(np.int32)
        self.inv_perm = np.empty(N, dtype=np.int32)
        self.inv_perm[self.perm] = np.arange(N, dtype=np.int32)
        # internal_to_orig[internal_pos] -> original corpus ID
        self.internal_to_orig = (
            ext_id_map[self.perm] if ext_id_map is not None else self.perm
        ).astype(np.int32)

        t0 = time.perf_counter()
        self.index = faiss.IndexHNSWFlat(d, M, faiss.METRIC_INNER_PRODUCT)
        self.index.hnsw.efConstruction = ef_construction
        self.index.hnsw.efSearch = ef_search
        self.index.add(np.ascontiguousarray(X[self.perm], dtype=np.float32))
        self.build_sec = time.perf_counter() - t0

    def extract_level0_in_input_space(self) -> Tuple[np.ndarray, float]:
        """
        Extracts level-0 adjacency lists mapped back into the input X's ID space.
        Returns (neighbors [N, 2*M] int32, fraction_of_empty_slots_padded).
        """
        neighbors = faiss.vector_to_array(self.index.hnsw.neighbors)
        offsets = faiss.vector_to_array(self.index.hnsw.offsets)
        l0_size = int(self.index.hnsw.nb_neighbors(0))
        idx_mat = offsets[:-1, None] + np.arange(l0_size, dtype=offsets.dtype)[None, :]
        l0_internal = neighbors[idx_mat].astype(np.int32)  # shape (N, l0_size)

        empty_mask = l0_internal < 0
        empty_frac = float(empty_mask.mean())

        # Map valid internal IDs -> input IDs via self.perm
        safe_internal = np.where(empty_mask, 0, l0_internal)
        mapped = self.perm[safe_internal]

        # Fill any -1 slots with the node's first valid neighbor (or self if none)
        if np.any(empty_mask):
            has_valid = np.any(~empty_mask, axis=1)
            first_valid_col = np.argmax(~empty_mask, axis=1)
            row_fill = np.where(
                has_valid,
                mapped[np.arange(self.N), first_valid_col],
                self.perm,
            )
            mapped = np.where(empty_mask, row_fill[:, None], mapped)

        # Reorder rows from internal order to input order
        l0_input = np.empty_like(mapped)
        l0_input[self.perm] = mapped
        return l0_input, empty_frac

    def search(self, q: QuerySpec, k: int) -> SearchOutput:
        # Map mask from original corpus space into internal FAISS ID space
        int_mask = q.mask[self.internal_to_orig]
        packed = np.packbits(int_mask, bitorder="little")
        sel = faiss.IDSelectorBitmap(self.N, faiss.swig_ptr(packed))
        params = faiss.SearchParametersHNSW(efSearch=self.ef_search, sel=sel)
        q_mat = np.ascontiguousarray(q.vector.reshape(1, -1), dtype=np.float32)

        faiss.cvar.hnsw_stats.reset()
        _, I = self.index.search(q_mat, k, params=params)
        ndis = int(faiss.cvar.hnsw_stats.ndis)

        ids = [int(self.internal_to_orig[i]) for i in I[0] if i >= 0]
        _check_no_leak(ids, q.mask, self.name)
        return SearchOutput(ids=ids, distance_computations=ndis)


class Acorn1System:
    """Real stanford-futuredata/ACORN (ACORN-1: gamma=1, M_beta=2*M) via ctypes C ABI."""

    _lib: Optional[ctypes.CDLL] = None

    @classmethod
    def available(cls) -> bool:
        return os.path.exists(ACORN_DYLIB_PATH)

    @classmethod
    def _load_lib(cls) -> ctypes.CDLL:
        if cls._lib is None:
            lib = ctypes.CDLL(ACORN_DYLIB_PATH)
            lib.acorn_create.restype = ctypes.c_void_p
            lib.acorn_create.argtypes = [ctypes.c_int] * 7
            lib.acorn_add.argtypes = [
                ctypes.c_void_p,
                ctypes.c_int64,
                ctypes.POINTER(ctypes.c_float),
            ]
            lib.acorn_search_one.restype = ctypes.c_int64
            lib.acorn_search_one.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.POINTER(ctypes.c_int64),
                ctypes.POINTER(ctypes.c_float),
            ]
            lib.acorn_destroy.argtypes = [ctypes.c_void_p]
            cls._lib = lib
        return cls._lib

    def __init__(
        self,
        X: np.ndarray,
        M: int = 16,
        ef_construction: int = 64,
        ef_search: int = 64,
        seed: int = 0,
        name: str = "acorn-1",
        gamma: int = 1,
        m_beta: Optional[int] = None,
    ):
        self.name = name
        self.ef_search = ef_search
        self.gamma = int(gamma)
        self.m_beta = int(m_beta) if m_beta is not None else int(M * 2 * max(1, gamma))
        self.lib = self._load_lib()
        N, d = X.shape
        self.N = N
        rng = np.random.default_rng(20_000 + seed * 137 + self.gamma * 17)
        self.perm = rng.permutation(N).astype(np.int32)

        t0 = time.perf_counter()
        self.handle = self.lib.acorn_create(
            d, M, self.gamma, self.m_beta, N, int(seed), ef_construction
        )
        X_perm = np.ascontiguousarray(X[self.perm], dtype=np.float32)
        self.lib.acorn_add(self.handle, N, X_perm.ctypes.data_as(ctypes.POINTER(ctypes.c_float)))
        self.build_sec = time.perf_counter() - t0

    def search(self, q: QuerySpec, k: int) -> SearchOutput:
        fmap = np.ascontiguousarray(q.mask[self.perm], dtype=np.uint8)
        qv = np.ascontiguousarray(q.vector, dtype=np.float32)
        out_ids = np.full(k, -1, dtype=np.int64)
        out_dists = np.zeros(k, dtype=np.float32)
        ndis = int(
            self.lib.acorn_search_one(
                self.handle,
                qv.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                int(k),
                int(self.ef_search),
                fmap.ctypes.data_as(ctypes.c_char_p),
                out_ids.ctypes.data_as(ctypes.POINTER(ctypes.c_int64)),
                out_dists.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            )
        )
        ids = [int(self.perm[i]) for i in out_ids if i >= 0]
        _check_no_leak(ids, q.mask, self.name)
        return SearchOutput(ids=ids, distance_computations=ndis)

    def close(self) -> None:
        if getattr(self, "handle", None):
            self.lib.acorn_destroy(self.handle)
            self.handle = None

    def __del__(self) -> None:
        self.close()


class HnswlibSystem:
    """Real hnswlib C++ HNSW with Python filter callback."""

    def __init__(
        self,
        X: np.ndarray,
        M: int = 16,
        ef_construction: int = 64,
        ef_search: int = 64,
        seed: int = 0,
        name: str = "hnswlib-M16",
    ):
        self.name = name
        N, d = X.shape
        rng = np.random.default_rng(30_000 + seed * 149)
        perm = rng.permutation(N).astype(np.int32)

        t0 = time.perf_counter()
        self.index = hnswlib.Index(space="ip", dim=d)
        self.index.init_index(
            max_elements=N,
            ef_construction=ef_construction,
            M=M,
            random_seed=100 + seed,
        )
        self.index.add_items(np.ascontiguousarray(X[perm], dtype=np.float32), perm, num_threads=8)
        self.index.set_ef(ef_search)
        self.index.set_num_threads(1)  # single-thread per-query timing
        self.build_sec = time.perf_counter() - t0

    def search(self, q: QuerySpec, k: int) -> SearchOutput:
        mask = q.mask
        n_auth = int(np.count_nonzero(mask))
        k_req = min(k, n_auth)
        if k_req == 0:
            return SearchOutput(ids=[], distance_computations=None)
        try:
            labels, _ = self.index.knn_query(
                q.vector.reshape(1, -1), k=k_req, filter=lambda label: bool(mask[label])
            )
            ids = [int(x) for x in labels[0]]
        except RuntimeError:
            # hnswlib raises RuntimeError if fewer than k_req authorized nodes are reachable
            ids = []
            for k_try in range(k_req - 1, 0, -1):
                try:
                    labels, _ = self.index.knn_query(
                        q.vector.reshape(1, -1), k=k_try, filter=lambda label: bool(mask[label])
                    )
                    ids = [int(x) for x in labels[0]]
                    break
                except RuntimeError:
                    continue
        _check_no_leak(ids, mask, self.name)
        return SearchOutput(ids=ids, distance_computations=None)


class PgvectorSystem:
    """Real PostgreSQL 17 + pgvector 0.8.7 HNSW with iterative_scan=relaxed_order."""

    def __init__(self, pg_service, table: str, name: str = "pgvector-hnsw-iter"):
        self.name = name
        self.pg = pg_service
        self.table = table

    def search(self, q: QuerySpec, k: int) -> SearchOutput:
        allowed_docs: List[int] = q.extra["allowed_doc_ints"]
        if not allowed_docs:
            return SearchOutput(ids=[], distance_computations=None)
        ids = self.pg.search_filtered(self.table, q.vector, allowed_docs, k=k)
        _check_no_leak(ids, q.mask, self.name)
        return SearchOutput(ids=ids, distance_computations=None)


def build_prism_bundle(
    auth_graph: ZanzibarAuthGraph,
    X: np.ndarray,
    ancestor_lineages: List[List[str]],
    meaning_magnet_ids: List[str],
    seed: int = 0,
    ef_construction: int = 64,
    ef_search: int = 64,
) -> Tuple[ZOrderedCorpus, AncestorStitchedHNSW, TriModalQueryPlanner, FaissHNSWSystem, Dict[str, float]]:
    """
    Populates frozen ZOrderedCorpus, AncestorStitchedHNSW, and TriModalQueryPlanner
    without modifying any file in src/modules/prism_ann/.
    Base level-0 graph (degree 16) is constructed via FAISS IndexHNSWFlat(d, 8) and
    express bridges (M_bridge=4) are constructed via AncestorStitchedHNSW._medoid_ring_and_chord.
    """
    t0 = time.perf_counter()
    z_corpus = ZOrderedCorpus(
        raw_vectors=X,
        ancestor_lineages=ancestor_lineages,
        meaning_magnet_ids=meaning_magnet_ids,
    )
    t_z = time.perf_counter() - t0

    # Shared-graph FAISS M=8 (level-0 degree = 2*8 = 16, exact match to frozen m_degree=16)
    faiss_m8 = FaissHNSWSystem(
        z_corpus.vectors,
        M=8,
        ef_construction=ef_construction,
        ef_search=ef_search,
        seed=seed,
        name="faiss-hnsw-M8",
        ext_id_map=z_corpus.z_to_orig,
    )
    l0_neighbors, empty_frac = faiss_m8.extract_level0_in_input_space()

    # Allocate frozen AncestorStitchedHNSW without running its slow O(N^2) Python builder
    t_b0 = time.perf_counter()
    idx = AncestorStitchedHNSW.__new__(AncestorStitchedHNSW)
    idx.t0_build = t_b0
    idx.corpus_vectors = z_corpus.vectors
    idx.N, idx.d = z_corpus.vectors.shape
    idx.container_ids = list(z_corpus.primary_containers)
    idx.meaning_magnet_ids = list(z_corpus.meaning_magnet_ids)
    idx.m_degree = 16
    idx.m_bridge = 4
    idx.rng = np.random.default_rng(seed)
    idx.base_neighbors = np.ascontiguousarray(l0_neighbors, dtype=np.int32)
    idx.express_bridges = np.zeros((idx.N, idx.m_bridge), dtype=np.int32)
    idx.container_buckets = {}
    idx.magnet_buckets = {}
    idx._build_buckets()

    # Build M_bridge=4 express bridges using frozen AncestorStitchedHNSW._medoid_ring_and_chord
    c_pos_map: Dict[Tuple[str, int], int] = {}
    c_medoid_map: Dict[str, int] = {}
    for c_id, arr in idx.container_buckets.items():
        for pos, nid in enumerate(arr):
            c_pos_map[(c_id, int(nid))] = pos
        c_vecs = idx.corpus_vectors[arr]
        c_centroid = np.mean(c_vecs, axis=0)
        c_medoid_map[c_id] = int(arr[int(np.argmax(c_vecs @ c_centroid))])

    m_pos_map: Dict[Tuple[str, int], int] = {}
    m_medoid_map: Dict[str, int] = {}
    for m_id, arr in idx.magnet_buckets.items():
        for pos, nid in enumerate(arr):
            m_pos_map[(m_id, int(nid))] = pos
        m_vecs = idx.corpus_vectors[arr]
        m_centroid = np.mean(m_vecs, axis=0)
        m_medoid_map[m_id] = int(arr[int(np.argmax(m_vecs @ m_centroid))])

    for i in range(idx.N):
        c_id = idx.container_ids[i]
        m_id = idx.meaning_magnet_ids[i]
        bridges = AncestorStitchedHNSW._medoid_ring_and_chord(
            idx.container_buckets.get(c_id), c_pos_map.get((c_id, i), 0), c_medoid_map.get(c_id, i), i
        )
        bridges.extend(
            AncestorStitchedHNSW._medoid_ring_and_chord(
                idx.magnet_buckets.get(m_id), m_pos_map.get((m_id, i), 0), m_medoid_map.get(m_id, i), i
            )
        )
        idx.express_bridges[i] = np.array(bridges[: idx.m_bridge], dtype=np.int32)

    idx.build_time_sec = faiss_m8.build_sec + (time.perf_counter() - t_b0)
    planner = TriModalQueryPlanner(
        auth_graph=auth_graph,
        z_corpus=z_corpus,
        hnsw_index=idx,
        ef_search=ef_search,
    )
    stats = {
        "z_order_sec": t_z,
        "faiss_m8_sec": faiss_m8.build_sec,
        "bridges_sec": time.perf_counter() - t_b0,
        "l0_empty_slot_frac": empty_frac,
        "prism_ram_bytes": float(idx.actual_memory_bytes()),
    }
    return z_corpus, idx, planner, faiss_m8, stats


class PrismGraphOnlySystem:
    """Frozen search_hnsw_gls (Mode 3 disabled) — mandatory ablation in PROTOCOL_v2."""

    def __init__(
        self,
        z_corpus: ZOrderedCorpus,
        hnsw_index: AncestorStitchedHNSW,
        ef_search: int = 64,
        use_gls_adaptive: bool = True,
        name: str = "prism-graph-only",
    ):
        self.name = name
        self.z_corpus = z_corpus
        self.hnsw_index = hnsw_index
        self.ef_search = ef_search
        self.use_gls_adaptive = use_gls_adaptive

    def search(self, q: QuerySpec, k: int) -> SearchOutput:
        z_mask = q.mask[self.z_corpus.z_to_orig]
        res = search_hnsw_gls(
            self.hnsw_index,
            q.vector,
            z_mask,
            k=k,
            ef_search=self.ef_search,
            tau_high=0.25,
            tau_low=0.02,
            use_express_bridges=True,
            use_gls_adaptive=self.use_gls_adaptive,
        )
        ids = [int(self.z_corpus.z_to_orig[zi]) for zi in res.top_k_ids]
        _check_no_leak(ids, q.mask, self.name)
        return SearchOutput(
            ids=ids,
            distance_computations=int(res.distance_evaluations),
            extra={
                "hops_1hop": int(res.hops_1hop),
                "hops_2hop": int(res.hops_2hop),
                "hops_teleport": int(res.hops_teleport),
                "mean_s_loc_hat": float(res.mean_local_selectivity_hat),
            },
        )


class PrismFullSystem:
    """Frozen TriModalQueryPlanner (UBP + H-HNSW/ACORN-GLS + Mode 3 Z-Order Roaring-SIMD)."""

    def __init__(
        self,
        z_corpus: ZOrderedCorpus,
        planner: TriModalQueryPlanner,
        name: str = "prism-full",
    ):
        self.name = name
        self.z_corpus = z_corpus
        self.planner = planner

    def search(self, q: QuerySpec, k: int) -> SearchOutput:
        z_mask = q.mask[self.z_corpus.z_to_orig]
        b_phi = RoaringRunBitmap.from_bool_mask(z_mask)
        res = self.planner.query(
            query_vec=q.vector,
            principal_id=q.extra.get("principal_id", "__override__"),
            k=k,
            override_bitmap_phi=b_phi,
        )
        ids = [int(self.z_corpus.z_to_orig[zi]) for zi in res.top_k_ids]
        _check_no_leak(ids, q.mask, self.name)
        return SearchOutput(
            ids=ids,
            distance_computations=int(res.distance_evaluations),
            extra={
                "execution_mode": res.execution_mode,
                "candidate_count": int(res.candidate_count),
            },
        )
