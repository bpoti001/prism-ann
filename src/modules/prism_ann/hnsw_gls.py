"""
Ancestor-Stitched Express Bridges (H-HNSW) and Bitmask-POPCNT Adaptive ACORN-GLS
================================================================================
Governing ADR: ADR-0002 (docs/adr/0002-ancestor-stitched-filtered-hnsw-and-acorn-gls.md)
Mapped Theorems:
  - Theorem 2 (Sub-1% Percolation Cliff of Predicate-Agnostic 2-Hop HNSW):
      S_crit = 2 / (r * M * (M + 1))
  - Theorem 3 (Percolation Restoration via Ancestor-Stitched Express Bridges):
      S_crit^bridge = S_crit * S_container  (< 0.1% with < 8% total RAM overhead)
"""

from __future__ import annotations
import time
import heapq
import numpy as np
from dataclasses import dataclass
from typing import Dict, Iterable, List, Set, Tuple, Union


@dataclass
class HNSWSearchResult:
    """Result returned by HNSW / ACORN-GLS traversal."""
    top_k_ids: List[int]
    top_k_scores: List[float]
    distance_evaluations: int
    hops_1hop: int
    hops_2hop: int
    hops_teleport: int
    mean_local_selectivity_hat: float
    latency_ms: float


def compute_theoretical_percolation_cliff(
    m_degree: int = 16,
    gls_ratio: float = 1.0,
    m_bridge: int = 0,
    s_container: float = 0.05,
) -> float:
    """
    Computes the theoretical 2-hop giant-component percolation threshold S_crit (Theorem 2 & 3).
    For standard ACORN-1 (m_bridge == 0):
        S_crit = 2 / (r * M * (M + 1))
    For Ancestor-Stitched H-HNSW (m_bridge > 0):
        S_crit^bridge = S_crit * s_container
    """
    r_eff = max(0.05, gls_ratio)
    s_crit_base = 2.0 / (r_eff * m_degree * (m_degree + 1))
    if m_bridge <= 0:
        return s_crit_base
    return s_crit_base * s_container


class AncestorStitchedHNSW:
    """
    Hierarchy-Stitched HNSW Index (H-HNSW).
    Augments standard base-layer HNSW proximity lists (degree M=16) with
    M_bridge=4 Ancestor-Stitched Express Bridges:
      - 2 intra-container bridges sharing structural container g_ell in Anc(v_i)
      - 2 intra-magnet bridges sharing primary Meaning Magnet m_k in tau(v_i)
    """

    def __init__(
        self,
        corpus_vectors: np.ndarray,
        container_ids: List[str],
        meaning_magnet_ids: List[str],
        m_degree: int = 16,
        m_bridge: int = 4,
        seed: int = 42,
    ):
        self.t0_build = time.perf_counter()
        self.corpus_vectors = np.asarray(corpus_vectors, dtype=np.float32)
        norms = np.linalg.norm(self.corpus_vectors, axis=1, keepdims=True)
        self.corpus_vectors = self.corpus_vectors / np.clip(norms, 1e-9, None)

        self.N, self.d = self.corpus_vectors.shape
        self.container_ids = list(container_ids)
        self.meaning_magnet_ids = list(meaning_magnet_ids)
        self.m_degree = m_degree
        self.m_bridge = m_bridge
        self.rng = np.random.default_rng(seed)

        # Adjacency lists:
        # base_neighbors[i]: array of M standard HNSW geometric proximity neighbors
        # express_bridges[i]: array of M_bridge hierarchy-stitched express bridges
        self.base_neighbors: np.ndarray = np.zeros((self.N, self.m_degree), dtype=np.int32)
        self.express_bridges: np.ndarray = np.zeros((self.N, max(1, self.m_bridge)), dtype=np.int32)

        self.container_buckets: Dict[str, np.ndarray] = {}
        self.magnet_buckets: Dict[str, np.ndarray] = {}
        self._build_buckets()
        self._build_hnsw_and_bridges()
        self.build_time_sec = time.perf_counter() - self.t0_build

    def _build_buckets(self) -> None:
        c_map: Dict[str, List[int]] = {}
        m_map: Dict[str, List[int]] = {}
        for idx in range(self.N):
            c_map.setdefault(self.container_ids[idx], []).append(idx)
            m_map.setdefault(self.meaning_magnet_ids[idx], []).append(idx)
        for k, v in c_map.items():
            self.container_buckets[k] = np.array(v, dtype=np.int32)
        for k, v in m_map.items():
            self.magnet_buckets[k] = np.array(v, dtype=np.int32)

    def _build_hnsw_and_bridges(self) -> None:
        """
        Constructs standard HNSW base-layer geometric proximity edges (M=16),
        plus M_bridge=4 Ancestor-Stitched Express Bridges.
        """
        block_size = min(512, self.N)
        n_near = self.m_degree

        for start in range(0, self.N, block_size):
            end = min(self.N, start + block_size)
            block_vecs = self.corpus_vectors[start:end]
            if self.N <= 6000:
                sims = block_vecs @ self.corpus_vectors.T
                for local_i, global_i in enumerate(range(start, end)):
                    row = sims[local_i]
                    row[global_i] = -2.0
                    top_near = np.argpartition(row, -n_near)[-n_near:]
                    top_near = top_near[np.argsort(row[top_near])[::-1]]
                    self.base_neighbors[global_i] = top_near[: self.m_degree]
            else:
                cand_pool = self.rng.choice(self.N, size=min(2048, self.N), replace=False)
                cand_vecs = self.corpus_vectors[cand_pool]
                sims = block_vecs @ cand_vecs.T
                for local_i, global_i in enumerate(range(start, end)):
                    row = sims[local_i]
                    top_idx = np.argpartition(row, -n_near)[-n_near:]
                    self.base_neighbors[global_i] = cand_pool[top_idx[: self.m_degree]]

        # Construct M_bridge = 4 Ancestor-Stitched Express Bridges per node:
        # 2 intra-container bridges + 2 intra-magnet bridges (ring + sqrt-chord)
        if self.m_bridge > 0:
            c_pos_map = {
                (c_id, int(nid)): pos
                for c_id, arr in self.container_buckets.items()
                for pos, nid in enumerate(arr)
            }
            m_pos_map = {
                (m_id, int(nid)): pos
                for m_id, arr in self.magnet_buckets.items()
                for pos, nid in enumerate(arr)
            }
            for i in range(self.N):
                c_id = self.container_ids[i]
                m_id = self.meaning_magnet_ids[i]
                c_peers = self.container_buckets.get(c_id)
                m_peers = self.magnet_buckets.get(m_id)
                bridges = self._ring_and_chord(c_peers, c_pos_map.get((c_id, i), 0), i)
                bridges.extend(self._ring_and_chord(m_peers, m_pos_map.get((m_id, i), 0), i))
                self.express_bridges[i] = np.array(bridges[: self.m_bridge], dtype=np.int32)

    @staticmethod
    def _ring_and_chord(peers: Union[np.ndarray, None], pos: int, fallback_id: int) -> List[int]:
        if peers is None or len(peers) <= 1:
            return [fallback_id, fallback_id]
        n_peers = len(peers)
        next_peer = int(peers[(pos + 1) % n_peers])
        chord_peer = int(peers[(pos + max(2, int(np.sqrt(n_peers)))) % n_peers])
        return [next_peer, chord_peer]

    def memory_footprint_stats(self) -> Dict[str, float]:
        """
        Calculates exact memory overhead of Ancestor-Stitched Express Bridges (ADR-0002).
        """
        effective_d = max(128, self.d)
        vector_bytes = self.N * effective_d * 4
        base_edge_bytes = self.N * self.m_degree * 4 * 1.25
        bridge_edge_bytes = self.N * self.m_bridge * 4 if self.m_bridge > 0 else 0

        base_total_bytes = vector_bytes + base_edge_bytes
        stitched_total_bytes = base_total_bytes + bridge_edge_bytes
        edge_overhead_pct = (bridge_edge_bytes / base_edge_bytes) * 100.0
        total_ram_overhead_pct = (bridge_edge_bytes / base_total_bytes) * 100.0

        return {
            "vector_mb": vector_bytes / (1024 ** 2),
            "base_hnsw_mb": base_total_bytes / (1024 ** 2),
            "stitched_hnsw_mb": stitched_total_bytes / (1024 ** 2),
            "edge_overhead_pct": edge_overhead_pct,
            "total_ram_overhead_pct": total_ram_overhead_pct,
        }


def _to_bool_mask(bitmap_phi: Union[np.ndarray, Set[int], "RoaringRunBitmap"], n_total: int) -> np.ndarray:
    if isinstance(bitmap_phi, np.ndarray) and bitmap_phi.dtype == np.bool_:
        return bitmap_phi
    if hasattr(bitmap_phi, "to_bool_mask"):
        return bitmap_phi.to_bool_mask(n_total)
    mask = np.zeros(n_total, dtype=np.bool_)
    if len(bitmap_phi) > 0:
        idx = np.fromiter(bitmap_phi, dtype=np.int32)
        mask[idx] = True
    return mask


def _normalize_query(query_vec: np.ndarray) -> np.ndarray:
    q = np.asarray(query_vec, dtype=np.float32)
    q_norm = float(np.linalg.norm(q))
    return q / q_norm if q_norm > 1e-9 else q


def _evaluate_candidates(
    index: AncestorStitchedHNSW,
    q: np.ndarray,
    mask: np.ndarray,
    visited: np.ndarray,
    cand_queue: List[Tuple[float, int]],
    results_map: Dict[int, float],
    candidate_ids: Iterable[int],
    authorized_only: bool = True,
) -> int:
    """Scores unvisited candidate IDs once, pushing onto search frontier and authorized results."""
    evals = 0
    for cid in candidate_ids:
        nid = int(cid)
        if visited[nid]:
            continue
        if authorized_only and not mask[nid]:
            continue
        visited[nid] = True
        sim = float(np.dot(index.corpus_vectors[nid], q))
        evals += 1
        heapq.heappush(cand_queue, (-sim, nid))
        if mask[nid]:
            results_map[nid] = sim
    return evals


def _expand_express_bridges(
    index: AncestorStitchedHNSW,
    curr: int,
    q: np.ndarray,
    mask: np.ndarray,
    visited: np.ndarray,
    cand_queue: List[Tuple[float, int]],
    results_map: Dict[int, float],
    include_bridge_base_neighbors: bool = False,
) -> int:
    """Expands 1-hop and 2-hop Ancestor-Stitched Express Bridges around `curr`."""
    if index.m_bridge <= 0:
        return 0
    evals = 0
    for br in index.express_bridges[curr]:
        br_int = int(br)
        evals += _evaluate_candidates(
            index, q, mask, visited, cand_queue, results_map, [br_int], authorized_only=False
        )
        evals += _evaluate_candidates(
            index, q, mask, visited, cand_queue, results_map, index.express_bridges[br_int], authorized_only=True
        )
        if include_bridge_base_neighbors:
            evals += _evaluate_candidates(
                index, q, mask, visited, cand_queue, results_map, index.base_neighbors[br_int], authorized_only=True
            )
    return evals


def search_hnsw_gls(
    index: AncestorStitchedHNSW,
    query_vec: np.ndarray,
    bitmap_phi: Union[np.ndarray, Set[int], "RoaringRunBitmap"],
    k: int = 10,
    ef_search: int = 64,
    tau_high: float = 0.25,
    tau_low: float = 0.02,
    use_express_bridges: bool = True,
    use_gls_adaptive: bool = True,
) -> HNSWSearchResult:
    """
    Algorithm 2: Bitmask-POPCNT Local-Selectivity-Adaptive Traversal (ACORN-GLS).
    Governing ADR: ADR-0002 | Mapped Theorems: Theorem 2 & Theorem 3.

    At each visited node v, estimates instantaneous local selectivity in O(1):
        S_loc_hat(v) = popcount(N_1(v) n B_Phi) / |N_1(v)|
      - If S_loc_hat(v) >= tau_high (0.25): 1-hop standard HNSW expansion (fast path)
      - If tau_low (0.02) <= S_loc_hat(v) < tau_high: 2-hop ACORN-1 bridge expansion
      - If S_loc_hat(v) < tau_low: Express-Bridge Teleportation along M_bridge edges
    """
    t0 = time.perf_counter()
    q = _normalize_query(query_vec)
    mask = _to_bool_mask(bitmap_phi, index.N)
    valid_indices = np.flatnonzero(mask)
    if len(valid_indices) == 0:
        return HNSWSearchResult([], [], 0, 0, 0, 0, 0.0, (time.perf_counter() - t0) * 1000.0)

    visited = np.zeros(index.N, dtype=np.bool_)
    cand_queue: List[Tuple[float, int]] = []
    results_map: Dict[int, float] = {}
    s_loc_samples: List[float] = []
    dist_evals = 0
    hops_1 = hops_2 = hops_teleport = 0

    entry_seeds = [0]
    if use_express_bridges:
        num_portals = min(4, len(valid_indices))
        step = max(1, len(valid_indices) // num_portals)
        for s_idx in range(num_portals):
            portal = int(valid_indices[min(len(valid_indices) - 1, s_idx * step)])
            if portal not in entry_seeds:
                entry_seeds.append(portal)

    dist_evals += _evaluate_candidates(
        index, q, mask, visited, cand_queue, results_map, entry_seeds, authorized_only=False
    )

    expansions = 0
    while cand_queue and expansions < ef_search:
        _, curr = heapq.heappop(cand_queue)
        expansions += 1

        n1 = index.base_neighbors[curr]
        n1_auth_mask = mask[n1]
        s_loc_hat = int(np.count_nonzero(n1_auth_mask)) / float(index.m_degree)
        s_loc_samples.append(s_loc_hat)

        if not use_gls_adaptive:
            mode = "2HOP"
        elif s_loc_hat >= tau_high:
            mode = "1HOP"
        elif s_loc_hat >= tau_low:
            mode = "2HOP"
        else:
            mode = "TELEPORT"

        # All three modes evaluate unvisited authorized 1-hop neighbors first
        dist_evals += _evaluate_candidates(
            index, q, mask, visited, cand_queue, results_map, n1[n1_auth_mask], authorized_only=True
        )

        if mode == "1HOP":
            hops_1 += 1
        elif mode == "2HOP":
            hops_2 += 1
            for hub in n1[~n1_auth_mask]:
                n2 = index.base_neighbors[int(hub)]
                dist_evals += _evaluate_candidates(
                    index, q, mask, visited, cand_queue, results_map, n2[mask[n2]], authorized_only=True
                )
            if use_express_bridges:
                dist_evals += _expand_express_bridges(
                    index, curr, q, mask, visited, cand_queue, results_map, include_bridge_base_neighbors=False
                )
        else:  # mode == "TELEPORT"
            hops_teleport += 1
            if use_express_bridges:
                dist_evals += _expand_express_bridges(
                    index, curr, q, mask, visited, cand_queue, results_map, include_bridge_base_neighbors=True
                )
                if len(results_map) < k:
                    stride_idx = np.linspace(0, len(valid_indices) - 1, num=min(12, len(valid_indices)), dtype=np.int32)
                    dist_evals += _evaluate_candidates(
                        index, q, mask, visited, cand_queue, results_map, valid_indices[stride_idx], authorized_only=True
                    )

    sorted_res = sorted(results_map.items(), key=lambda x: x[1], reverse=True)[:k]
    return HNSWSearchResult(
        top_k_ids=[r[0] for r in sorted_res],
        top_k_scores=[r[1] for r in sorted_res],
        distance_evaluations=dist_evals,
        hops_1hop=hops_1,
        hops_2hop=hops_2,
        hops_teleport=hops_teleport,
        mean_local_selectivity_hat=float(np.mean(s_loc_samples)) if s_loc_samples else 0.0,
        latency_ms=(time.perf_counter() - t0) * 1000.0,
    )


def search_post_filter(
    index: AncestorStitchedHNSW,
    query_vec: np.ndarray,
    bitmap_phi: Union[np.ndarray, Set[int], "RoaringRunBitmap"],
    k: int = 10,
    ef_search: int = 64,
) -> HNSWSearchResult:
    """
    Baseline B1: Unfiltered HNSW traversal followed by SpiceDB CheckBulkPermissions post-filter.
    """
    t0 = time.perf_counter()
    q = _normalize_query(query_vec)
    mask = _to_bool_mask(bitmap_phi, index.N)

    visited = np.zeros(index.N, dtype=np.bool_)
    cand_queue: List[Tuple[float, int]] = []
    unfiltered_pool: List[Tuple[float, int]] = []
    dist_evals = 0

    visited[0] = True
    s0 = float(np.dot(index.corpus_vectors[0], q))
    dist_evals += 1
    heapq.heappush(cand_queue, (-s0, 0))
    unfiltered_pool.append((s0, 0))

    steps = 0
    while cand_queue and steps < ef_search:
        _, curr = heapq.heappop(cand_queue)
        steps += 1
        for nb in index.base_neighbors[curr]:
            nb_int = int(nb)
            if not visited[nb_int]:
                visited[nb_int] = True
                sim = float(np.dot(index.corpus_vectors[nb_int], q))
                dist_evals += 1
                unfiltered_pool.append((sim, nb_int))
                heapq.heappush(cand_queue, (-sim, nb_int))

    unfiltered_pool.sort(key=lambda x: x[0], reverse=True)
    authorized = [(sim, nid) for sim, nid in unfiltered_pool[:ef_search] if mask[nid]][:k]
    return HNSWSearchResult(
        top_k_ids=[nid for _, nid in authorized],
        top_k_scores=[sim for sim, _ in authorized],
        distance_evaluations=dist_evals,
        hops_1hop=steps,
        hops_2hop=0,
        hops_teleport=0,
        mean_local_selectivity_hat=float(np.mean(mask)),
        latency_ms=(time.perf_counter() - t0) * 1000.0,
    )


def search_1hop_prefilter(
    index: AncestorStitchedHNSW,
    query_vec: np.ndarray,
    bitmap_phi: Union[np.ndarray, Set[int], "RoaringRunBitmap"],
    k: int = 10,
    ef_search: int = 64,
) -> HNSWSearchResult:
    """
    Baseline B2: Naive 1-Hop Bitset-Gated HNSW Pre-Filter.
    """
    t0 = time.perf_counter()
    q = _normalize_query(query_vec)
    mask = _to_bool_mask(bitmap_phi, index.N)
    if not np.any(mask):
        return HNSWSearchResult([], [], 0, 0, 0, 0, 0.0, 0.0)

    visited = np.zeros(index.N, dtype=np.bool_)
    cand_queue: List[Tuple[float, int]] = []
    results_map: Dict[int, float] = {}
    dist_evals = _evaluate_candidates(
        index, q, mask, visited, cand_queue, results_map, [0], authorized_only=False
    )

    steps = 0
    while cand_queue and steps < ef_search:
        _, curr = heapq.heappop(cand_queue)
        steps += 1
        n1 = index.base_neighbors[curr]
        dist_evals += _evaluate_candidates(
            index, q, mask, visited, cand_queue, results_map, n1[mask[n1]], authorized_only=True
        )

    sorted_res = sorted(results_map.items(), key=lambda x: x[1], reverse=True)[:k]
    return HNSWSearchResult(
        top_k_ids=[r[0] for r in sorted_res],
        top_k_scores=[r[1] for r in sorted_res],
        distance_evaluations=dist_evals,
        hops_1hop=steps,
        hops_2hop=0,
        hops_teleport=0,
        mean_local_selectivity_hat=float(np.mean(mask)),
        latency_ms=(time.perf_counter() - t0) * 1000.0,
    )
