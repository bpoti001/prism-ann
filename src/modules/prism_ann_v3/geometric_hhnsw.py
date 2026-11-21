"""
Geometric Intra-Container & Intra-Magnet Express Bridges (H-HNSW v2)
====================================================================
Governing ADRs: ADR-0002, ADR-0005.
Replaces non-geometric ID-ordered ring-chord bridges (v2) with Vamana/RNG-diverse
semantic navigable bridges inside each structural container bucket V(g_ell)
(L3 folder + optional L2 parent container) and Meaning Magnet bucket V(m_k),
plus native C++ ARM NEON traversal with O(1) epoch-based visited tracking.
"""

from __future__ import annotations

import heapq
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import faiss
import numpy as np

from src.modules.prism_ann.hnsw_gls import AncestorStitchedHNSW
from .ckernel_bridge import (
    CKernelSearchStats,
    ranges_clear_bitset,
    ranges_set_bitset,
    remap_hnsw_csr_cpp,
    search_hhnsw_gls_cpp,
    select_rng_bridges_cpp,
)


@dataclass(frozen=True)
class GeometricBridgeConfig:
    """Configuration for H-HNSW v2 Express Bridge construction."""
    m_bridge: int = 8
    bridge_mode: str = "geometric"  # "geometric" | "ring_chord" | "none"
    l3_slots: int = 4               # intra-L3 folder semantic RNG + medoid links
    l2_slots: int = 2               # intra-L2 parent container semantic RNG + medoid links
    magnet_slots: int = 2           # intra-Meaning Magnet semantic RNG + medoid links
    rng_alpha: float = 1.0          # Vamana/RNG diversity parameter
    candidate_k: int = 32           # semantic candidate pool per node inside each bucket
    include_medoid: bool = True     # reserve 1 slot per bucket for medoid hub link

    @classmethod
    def for_m_bridge(cls, m_bridge: int, bridge_mode: str = "geometric") -> "GeometricBridgeConfig":
        if bridge_mode == "none" or m_bridge <= 0:
            return cls(m_bridge=0, bridge_mode="none", l3_slots=0, l2_slots=0, magnet_slots=0)
        if bridge_mode == "ring_chord":
            half = max(1, m_bridge // 2)
            return cls(
                m_bridge=m_bridge,
                bridge_mode="ring_chord",
                l3_slots=half,
                l2_slots=0,
                magnet_slots=m_bridge - half,
            )
        if m_bridge == 4:
            # 2 intra-L3 folder + 2 intra-Magnet (matches v2 M_bridge=4 slot split cleanly)
            return cls(m_bridge=4, bridge_mode="geometric", l3_slots=2, l2_slots=0, magnet_slots=2)
        if m_bridge == 8:
            return cls(m_bridge=8, bridge_mode="geometric", l3_slots=4, l2_slots=2, magnet_slots=2)
        l3 = max(1, m_bridge // 2)
        l2 = max(0, (m_bridge - l3) // 2)
        mag = m_bridge - l3 - l2
        return cls(m_bridge=m_bridge, bridge_mode="geometric", l3_slots=l3, l2_slots=l2, magnet_slots=mag)


@dataclass
class HHNSWSearchResultV3:
    top_k_ids: List[int]
    top_k_scores: List[float]
    distance_evaluations: int
    hops_1hop: int
    hops_2hop: int
    hops_teleport: int
    expansions: int
    n_auth_found: int
    stalled: bool
    mean_s_loc_hat: float
    early_s_loc_hat: float
    latency_ms: float


def _group_buckets(labels: Sequence[str]) -> Dict[str, np.ndarray]:
    buckets: Dict[str, List[int]] = {}
    for idx, lbl in enumerate(labels):
        buckets.setdefault(lbl, []).append(idx)
    return {k: np.asarray(v, dtype=np.int32) for k, v in buckets.items()}


def _build_bucket_geometric_edges(
    vectors: np.ndarray,
    buckets: Dict[str, np.ndarray],
    n_slots: int,
    candidate_k: int = 32,
    rng_alpha: float = 1.0,
    include_medoid: bool = True,
) -> np.ndarray:
    """
    Constructs `n_slots` Vamana/RNG-diverse geometric bridges inside each bucket V(g).
    Uses exact BLAS `X_b @ X_b.T` for |V(g)| <= 2048 and FAISS IndexHNSWFlat/FlatIP
    for larger buckets, then selects angularly diverse + medoid edges in C++.
    """
    N, d = vectors.shape
    out = np.full((N, n_slots), -1, dtype=np.int32)
    if n_slots <= 0:
        return out

    for _, global_ids in buckets.items():
        n_b = len(global_ids)
        if n_b <= 1:
            continue
        b_vecs = np.ascontiguousarray(vectors[global_ids], dtype=np.float32)

        # Compute exact bucket medoid (closest point to normalized bucket centroid)
        centroid = b_vecs.mean(axis=0)
        c_norm = float(np.linalg.norm(centroid))
        if c_norm > 1e-9:
            centroid = centroid / c_norm
        medoid_local = int(np.argmax(b_vecs @ centroid))

        k_eff = min(candidate_k, n_b - 1)
        if n_b <= 2048:
            # Exact batched inner products via BLAS
            sims = b_vecs @ b_vecs.T
            np.fill_diagonal(sims, -2.0)
            if k_eff < n_b - 1:
                part = np.argpartition(-sims, k_eff, axis=1)[:, :k_eff]
                part_sims = np.take_along_axis(sims, part, axis=1)
                order = np.argsort(-part_sims, axis=1)
                cand_local = np.take_along_axis(part, order, axis=1).astype(np.int32)
                cand_sims = np.take_along_axis(part_sims, order, axis=1).astype(np.float32)
            else:
                order = np.argsort(-sims, axis=1)[:, :k_eff]
                cand_local = order.astype(np.int32)
                cand_sims = np.take_along_axis(sims, order, axis=1).astype(np.float32)
        elif n_b <= 4096:
            idx_flat = faiss.IndexFlatIP(d)
            idx_flat.add(b_vecs)
            D_all, I_all = idx_flat.search(b_vecs, k_eff + 1)
            cand_local = np.full((n_b, k_eff), -1, dtype=np.int32)
            cand_sims = np.full((n_b, k_eff), -2.0, dtype=np.float32)
            for u in range(n_b):
                row_i = I_all[u]
                row_d = D_all[u]
                keep = row_i != u
                kept_i = row_i[keep][:k_eff]
                kept_d = row_d[keep][:k_eff]
                cand_local[u, : len(kept_i)] = kept_i
                cand_sims[u, : len(kept_d)] = kept_d
        else:
            # Fast intra-bucket HNSW k-NN for large buckets (e.g. L2/Magnet at N=523k)
            idx_sub = faiss.IndexHNSWFlat(d, 16, faiss.METRIC_INNER_PRODUCT)
            idx_sub.hnsw.efConstruction = 48
            idx_sub.hnsw.efSearch = max(48, k_eff * 2)
            idx_sub.add(b_vecs)
            D_all, I_all = idx_sub.search(b_vecs, k_eff + 1)
            cand_local = np.full((n_b, k_eff), -1, dtype=np.int32)
            cand_sims = np.full((n_b, k_eff), -2.0, dtype=np.float32)
            for u in range(n_b):
                row_i = I_all[u]
                row_d = D_all[u]
                keep = (row_i >= 0) & (row_i != u)
                kept_i = row_i[keep][:k_eff]
                kept_d = row_d[keep][:k_eff]
                cand_local[u, : len(kept_i)] = kept_i
                cand_sims[u, : len(kept_d)] = kept_d

        b_edges = select_rng_bridges_cpp(
            bucket_vecs=b_vecs,
            global_ids=global_ids,
            cand_local_ids=cand_local,
            cand_sims=cand_sims,
            n_slots=n_slots,
            medoid_local=medoid_local,
            include_medoid=include_medoid,
            rng_alpha=rng_alpha,
        )
        out[global_ids] = b_edges
    return out


def _build_ring_chord_bridges(
    vectors: np.ndarray,
    l3_buckets: Dict[str, np.ndarray],
    l3_ids: Sequence[str],
    magnet_buckets: Dict[str, np.ndarray],
    magnet_ids: Sequence[str],
    m_bridge: int = 4,
) -> np.ndarray:
    """Reproduces v2 ID-ordered ring-chord + medoid bridges for E1 ablation."""
    N = len(vectors)
    out = np.full((N, m_bridge), -1, dtype=np.int32)
    if m_bridge <= 0:
        return out

    c_pos: Dict[Tuple[str, int], int] = {}
    c_med: Dict[str, int] = {}
    for cid, arr in l3_buckets.items():
        for pos, nid in enumerate(arr):
            c_pos[(cid, int(nid))] = pos
        vecs = vectors[arr]
        c_med[cid] = int(arr[int(np.argmax(vecs @ vecs.mean(axis=0)))])

    m_pos: Dict[Tuple[str, int], int] = {}
    m_med: Dict[str, int] = {}
    for mid, arr in magnet_buckets.items():
        for pos, nid in enumerate(arr):
            m_pos[(mid, int(nid))] = pos
        vecs = vectors[arr]
        m_med[mid] = int(arr[int(np.argmax(vecs @ vecs.mean(axis=0)))])

    for i in range(N):
        cid = l3_ids[i]
        mid = magnet_ids[i]
        br = AncestorStitchedHNSW._medoid_ring_and_chord(
            l3_buckets.get(cid), c_pos.get((cid, i), 0), c_med.get(cid, i), i
        )
        br.extend(
            AncestorStitchedHNSW._medoid_ring_and_chord(
                magnet_buckets.get(mid), m_pos.get((mid, i), 0), m_med.get(mid, i), i
            )
        )
        for j in range(min(m_bridge, len(br))):
            out[i, j] = -1 if br[j] == i else int(br[j])
    return out


def extract_faiss_hnsw_graph(
    faiss_index: faiss.IndexHNSWFlat, perm: np.ndarray
) -> Tuple[int, int, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Extracts full upper-layer + level-0 CSR graph from a FAISS IndexHNSWFlat
    built on X[perm] and remaps all IDs back into input (Z-order) ID space.
    """
    h = faiss_index.hnsw
    N = int(len(perm))
    m_base = int(h.nb_neighbors(0))
    offsets_int = faiss.vector_to_array(h.offsets).astype(np.int64, copy=False)
    neighbors_int = faiss.vector_to_array(h.neighbors).astype(np.int32, copy=False)
    cum_nn = faiss.vector_to_array(h.cum_nneighbor_per_level).astype(np.int32, copy=True)

    inv_perm = np.empty(N, dtype=np.int32)
    inv_perm[perm] = np.arange(N, dtype=np.int32)

    offsets_z, neighbors_z, base_l0 = remap_hnsw_csr_cpp(
        offsets_int, neighbors_int, perm, inv_perm, m_base
    )
    ep_z = int(perm[h.entry_point]) if h.entry_point >= 0 else -1
    max_level = int(h.max_level)
    return ep_z, max_level, offsets_z, neighbors_z, cum_nn, base_l0


class GeometricHHNSW:
    """
    H-HNSW v2: Base FAISS HNSW (M=16, M_max0=32) + Geometric Intra-Container
    & Intra-Magnet Express Bridges, executed via native C++ ARM NEON kernel.
    """

    def __init__(
        self,
        vectors: np.ndarray,
        l3_container_ids: Sequence[str],
        l2_container_ids: Sequence[str],
        meaning_magnet_ids: Sequence[str],
        bridge_config: Optional[GeometricBridgeConfig] = None,
        M: int = 16,
        ef_construction: int = 64,
        seed: int = 0,
        prebuilt_faiss: Optional[Tuple[faiss.IndexHNSWFlat, np.ndarray]] = None,
    ):
        t0 = time.perf_counter()
        self.vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        self.N, self.d = self.vectors.shape
        self.M = M
        self.bridge_config = bridge_config or GeometricBridgeConfig.for_m_bridge(8, "geometric")
        self.m_bridge = self.bridge_config.m_bridge

        # Build or reuse FAISS IndexHNSWFlat(d, M) for the exact shared base graph
        t_f0 = time.perf_counter()
        if prebuilt_faiss is not None:
            faiss_idx, perm = prebuilt_faiss
            self.faiss_build_sec = 0.0
        else:
            rng = np.random.default_rng(10_000 + seed * 131 + M)
            perm = rng.permutation(self.N).astype(np.int32)
            faiss_idx = faiss.IndexHNSWFlat(self.d, M, faiss.METRIC_INNER_PRODUCT)
            faiss_idx.hnsw.efConstruction = ef_construction
            faiss_idx.add(np.ascontiguousarray(self.vectors[perm], dtype=np.float32))
            self.faiss_build_sec = time.perf_counter() - t_f0

        (
            self.entry_point,
            self.max_level,
            self.upper_offsets,
            self.upper_neighbors,
            self.cum_nn_per_lvl,
            self.base_neighbors,
        ) = extract_faiss_hnsw_graph(faiss_idx, perm)
        self.m_base = int(self.base_neighbors.shape[1])

        # Build Express Bridges (geometric or ring-chord)
        t_b0 = time.perf_counter()
        self.express_bridges = self._build_express_bridges(
            l3_container_ids, l2_container_ids, meaning_magnet_ids
        )
        self.bridge_build_sec = time.perf_counter() - t_b0
        self.total_build_sec = time.perf_counter() - t0

        # Pre-allocated O(1) query scratch buffers (zero per-query allocation/memset!)
        self._visited_epoch = np.zeros(self.N, dtype=np.uint32)
        self._epoch_counter = 1
        self._mask_bits = np.zeros((self.N + 63) // 64, dtype=np.uint64)

    def _build_express_bridges(
        self,
        l3_ids: Sequence[str],
        l2_ids: Sequence[str],
        magnet_ids: Sequence[str],
    ) -> Optional[np.ndarray]:
        cfg = self.bridge_config
        if cfg.bridge_mode == "none" or cfg.m_bridge <= 0:
            return None

        l3_buckets = _group_buckets(l3_ids)
        mag_buckets = _group_buckets(magnet_ids)

        if cfg.bridge_mode == "ring_chord":
            return _build_ring_chord_bridges(
                self.vectors, l3_buckets, l3_ids, mag_buckets, magnet_ids, m_bridge=cfg.m_bridge
            )

        parts: List[np.ndarray] = []
        if cfg.l3_slots > 0:
            parts.append(
                _build_bucket_geometric_edges(
                    self.vectors,
                    l3_buckets,
                    n_slots=cfg.l3_slots,
                    candidate_k=cfg.candidate_k,
                    rng_alpha=cfg.rng_alpha,
                    include_medoid=cfg.include_medoid,
                )
            )
        if cfg.l2_slots > 0:
            l2_buckets = _group_buckets(l2_ids)
            parts.append(
                _build_bucket_geometric_edges(
                    self.vectors,
                    l2_buckets,
                    n_slots=cfg.l2_slots,
                    candidate_k=cfg.candidate_k,
                    rng_alpha=cfg.rng_alpha,
                    include_medoid=cfg.include_medoid,
                )
            )
        if cfg.magnet_slots > 0:
            parts.append(
                _build_bucket_geometric_edges(
                    self.vectors,
                    mag_buckets,
                    n_slots=cfg.magnet_slots,
                    candidate_k=cfg.candidate_k,
                    rng_alpha=cfg.rng_alpha,
                    include_medoid=cfg.include_medoid,
                )
            )
        if not parts:
            return None
        return np.ascontiguousarray(np.concatenate(parts, axis=1), dtype=np.int32)

    def _next_epoch(self) -> int:
        self._epoch_counter += 1
        if self._epoch_counter >= 0xFFFFFFFE:
            self._visited_epoch.fill(0)
            self._epoch_counter = 1
        return self._epoch_counter

    def search_ranges(
        self,
        query_vec: np.ndarray,
        starts: np.ndarray,
        ends: np.ndarray,
        k: int = 10,
        ef_search: int = 64,
        tau_high: float = 0.55,
        tau_low: float = 0.02,
        use_express_bridges: bool = True,
        use_portals: bool = True,
        max_portals: int = 4,
        use_gls_adaptive: bool = True,
        faiss_style_1hop: bool = False,
        tau_stall: float = 0.0,
        stall_check_hops: int = 16,
    ) -> HHNSWSearchResultV3:
        """
        Native C++ search given CRoaring Z-order [start, end) ranges.
        Uses O(N_cand / 64) bitset set/clear and O(1) epoch visited tracking.
        """
        t0 = time.perf_counter()
        if len(starts) == 0:
            return HHNSWSearchResultV3([], [], 0, 0, 0, 0, 0, 0, False, 0.0, 0.0, 0.0)

        q = np.ascontiguousarray(query_vec, dtype=np.float32)
        starts_i32 = np.ascontiguousarray(starts, dtype=np.int32)
        ends_i32 = np.ascontiguousarray(ends, dtype=np.int32)

        ranges_set_bitset(starts_i32, ends_i32, self._mask_bits, self.N)
        try:
            epoch = self._next_epoch()
            ids, scores, st = search_hhnsw_gls_cpp(
                vectors=self.vectors,
                entry_point=self.entry_point,
                max_level=self.max_level,
                upper_offsets=self.upper_offsets,
                upper_neighbors=self.upper_neighbors,
                cum_nn_per_lvl=self.cum_nn_per_lvl,
                base_neighbors=self.base_neighbors,
                express_bridges=self.express_bridges if use_express_bridges else None,
                mask_bits=self._mask_bits,
                starts=starts_i32,
                ends=ends_i32,
                query=q,
                k=k,
                ef_search=ef_search,
                tau_high=tau_high,
                tau_low=tau_low,
                use_express_bridges=use_express_bridges and (self.express_bridges is not None),
                use_portals=use_portals,
                max_portals=max_portals,
                use_gls_adaptive=use_gls_adaptive,
                faiss_style_1hop=faiss_style_1hop,
                tau_stall=tau_stall,
                stall_check_hops=stall_check_hops,
                visited_epoch=self._visited_epoch,
                current_epoch=epoch,
            )
        finally:
            ranges_clear_bitset(starts_i32, ends_i32, self._mask_bits, self.N)

        return HHNSWSearchResultV3(
            top_k_ids=ids.tolist(),
            top_k_scores=scores.tolist(),
            distance_evaluations=st.dist_computations,
            hops_1hop=st.hops_1hop,
            hops_2hop=st.hops_2hop,
            hops_teleport=st.hops_teleport,
            expansions=st.expansions,
            n_auth_found=st.n_auth_found,
            stalled=st.stalled,
            mean_s_loc_hat=st.mean_s_loc_hat,
            early_s_loc_hat=st.early_s_loc_hat,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )

    def memory_footprint_bytes(self) -> Dict[str, int]:
        vec_b = int(self.vectors.nbytes)
        base_b = int(self.upper_neighbors.nbytes + self.upper_offsets.nbytes)
        br_b = int(self.express_bridges.nbytes) if self.express_bridges is not None else 0
        return {
            "vectors_bytes": vec_b,
            "base_hnsw_bytes": base_b,
            "bridges_bytes": br_b,
            "total_bytes": vec_b + base_b + br_b,
        }


def search_hhnsw_gls_py_ref(
    index: GeometricHHNSW,
    query_vec: np.ndarray,
    mask: np.ndarray,
    k: int = 10,
    ef_search: int = 64,
    tau_high: float = 0.55,
    tau_low: float = 0.02,
    use_express_bridges: bool = True,
    use_portals: bool = True,
    max_portals: int = 4,
    use_gls_adaptive: bool = True,
) -> HHNSWSearchResultV3:
    """
    Pure-Python reference implementation of H-HNSW v2 + ACORN-GLS traversal
    used in unit tests to verify parity and zero-leak invariants of the C++ kernel.
    """
    t0 = time.perf_counter()
    q = np.asarray(query_vec, dtype=np.float32)
    valid_ids = np.flatnonzero(mask)
    if len(valid_ids) == 0:
        return HHNSWSearchResultV3([], [], 0, 0, 0, 0, 0, 0, False, 0.0, 0.0, 0.0)

    visited = np.zeros(index.N, dtype=np.bool_)
    dist_evals = 0

    def score(nid: int) -> float:
        nonlocal dist_evals
        dist_evals += 1
        return float(np.dot(index.vectors[nid], q))

    # Upper-layer greedy zoom-in
    ep = index.entry_point
    ep_sim = score(ep)
    for lvl in range(index.max_level, 0, -1):
        changed = True
        while changed:
            changed = False
            off = int(index.upper_offsets[ep])
            row_end = int(index.upper_offsets[ep + 1])
            beg = off + int(index.cum_nn_per_lvl[lvl])
            end = min(row_end, off + int(index.cum_nn_per_lvl[lvl + 1]))
            for idx_p in range(beg, end):
                nb = int(index.upper_neighbors[idx_p])
                if nb < 0:
                    break
                sc = score(nb)
                if sc > ep_sim:
                    ep_sim = sc
                    ep = nb
                    changed = True

    cand_queue: List[Tuple[float, int]] = []
    results_map: Dict[int, float] = {}

    def eval_push(nid: int, auth_only: bool) -> None:
        if nid < 0 or nid >= index.N or visited[nid]:
            return
        auth = bool(mask[nid])
        if auth_only and not auth:
            return
        visited[nid] = True
        sc = score(nid)
        heapq.heappush(cand_queue, (-sc, nid))
        if auth:
            results_map[nid] = sc

    visited[ep] = True
    heapq.heappush(cand_queue, (-ep_sim, ep))
    if mask[ep]:
        results_map[ep] = ep_sim

    if use_portals and max_portals > 0:
        kp = min(max_portals, 4, len(valid_ids))
        total = len(valid_ids)
        for j in range(kp):
            pos = min(total - 1, (j * total + total // 2) // kp)
            eval_push(int(valid_ids[pos]), False)

    hops_1 = hops_2 = hops_tp = expansions = 0
    s_loc_sum = 0.0
    while cand_queue and expansions < ef_search:
        neg_sim, curr = heapq.heappop(cand_queue)
        curr_sim = -neg_sim
        if len(results_map) >= max(ef_search, k):
            worst = sorted(results_map.values(), reverse=True)[max(ef_search, k) - 1]
            if curr_sim < worst:
                break
        expansions += 1
        n1_raw = index.base_neighbors[curr]
        n1 = [int(x) for x in n1_raw if x >= 0]
        auth_n1 = [x for x in n1 if mask[x]]
        unauth_n1 = [x for x in n1 if not mask[x]]
        s_loc = len(auth_n1) / float(len(n1)) if n1 else 0.0
        s_loc_sum += s_loc

        for nb in auth_n1:
            eval_push(nb, True)

        if not use_gls_adaptive:
            mode = 1
        elif s_loc >= tau_high:
            mode = 0
        elif s_loc >= tau_low:
            mode = 1
        else:
            mode = 2

        if mode == 0:
            hops_1 += 1
        elif mode == 1:
            hops_2 += 1
            if use_express_bridges and index.express_bridges is not None:
                for br in index.express_bridges[curr]:
                    if br >= 0:
                        eval_push(int(br), True)
            hubs = n1 if not use_gls_adaptive else unauth_n1
            for h in hubs:
                for c2 in index.base_neighbors[h]:
                    if c2 < 0:
                        break
                    if not visited[c2] and mask[c2]:
                        eval_push(int(c2), True)
            if use_express_bridges and index.express_bridges is not None:
                for br in index.express_bridges[curr]:
                    if br >= 0:
                        for b2 in index.express_bridges[int(br)]:
                            if b2 >= 0 and not visited[b2] and mask[b2]:
                                eval_push(int(b2), True)
        else:
            hops_tp += 1
            if use_express_bridges and index.express_bridges is not None:
                for br in index.express_bridges[curr]:
                    if br >= 0:
                        eval_push(int(br), True)
            for h in unauth_n1:
                for c2 in index.base_neighbors[h]:
                    if c2 < 0:
                        break
                    if not visited[c2] and mask[c2]:
                        eval_push(int(c2), True)
            if use_express_bridges and index.express_bridges is not None:
                for br in index.express_bridges[curr]:
                    if br >= 0:
                        br_i = int(br)
                        for b2 in index.express_bridges[br_i]:
                            if b2 >= 0 and not visited[b2] and mask[b2]:
                                eval_push(int(b2), True)
                        if mask[br_i]:
                            for nb in index.base_neighbors[br_i]:
                                if nb < 0:
                                    break
                                if not visited[nb] and mask[nb]:
                                    eval_push(int(nb), True)
            if len(cand_queue) < 4 and unauth_n1:
                pushed = 0
                for h in unauth_n1:
                    if not visited[h]:
                        eval_push(h, False)
                        pushed += 1
                        if pushed >= 4:
                            break

    ranked = sorted(results_map.items(), key=lambda x: (-x[1], x[0]))[:k]
    return HHNSWSearchResultV3(
        top_k_ids=[r[0] for r in ranked],
        top_k_scores=[r[1] for r in ranked],
        distance_evaluations=dist_evals,
        hops_1hop=hops_1,
        hops_2hop=hops_2,
        hops_teleport=hops_tp,
        expansions=expansions,
        n_auth_found=len(results_map),
        stalled=False,
        mean_s_loc_hat=s_loc_sum / float(max(1, expansions)),
        early_s_loc_hat=0.0,
        latency_ms=(time.perf_counter() - t0) * 1000.0,
    )
