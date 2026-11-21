"""
Tri-Modal Query Planner v3 with Native C++ NEON Mode-3 & Local-Stall Guard
==========================================================================
Governing ADRs: ADR-0003, ADR-0005.
Upgrades TriModalQueryPlanner with:
  1. Zero-copy CRoaring [start, end) range dispatch to C++ ARM NEON Mode 3
     (`f32` exact NEON or `sq8` vdotq_s32 + top-4k FP32 rerank).
  2. Native C++ H-HNSW v2 + ACORN-GLS graph traversal (`GeometricHHNSW`).
  3. Local-Stall Mode-3 Escalation Guard: even when global selectivity S > S_low
     (e.g., S=2% in H3 with negative correlation r <= 0.5), if early graph hops
     detect a depleted pocket (early_s_loc < tau_stall or < k authorized found)
     and N_cand <= N_guard, seamlessly escalates to C++ NEON Mode 3.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

import numpy as np

from src.modules.prism_ann.trimodal_planner import (
    RoaringRunBitmap,
    ZOrderedCorpus,
    compute_optimal_crossover_threshold,
)
from src.modules.prism_ann.ubp_resolver import ZanzibarAuthGraph, resolve_ubp_tokens
from .ckernel_bridge import mode3_scan_ranges_f32, mode3_scan_ranges_sq8
from .geometric_hhnsw import GeometricHHNSW


@dataclass
class TriModalResultV3:
    top_k_ids: List[int]
    top_k_scores: List[float]
    execution_mode: str
    global_selectivity: float
    candidate_count: int
    n_ranges: int
    stalled_escalated: bool
    distance_evaluations: int
    hops_1hop: int
    hops_2hop: int
    hops_teleport: int
    mean_s_loc_hat: float
    bitmap_compile_ms: float
    search_exec_ms: float
    total_latency_ms: float


def runs_to_range_arrays(rbm: RoaringRunBitmap) -> Tuple[np.ndarray, np.ndarray, int]:
    """Converts a RoaringRunBitmap's merged runs into contiguous int32 (starts, ends, popcount)."""
    if not rbm.runs:
        empty = np.empty(0, dtype=np.int32)
        return empty, empty, 0
    arr = np.asarray(rbm.runs, dtype=np.int32)
    starts = np.ascontiguousarray(arr[:, 0], dtype=np.int32)
    ends = np.ascontiguousarray(arr[:, 1], dtype=np.int32)
    n_cand = int(np.sum(ends - starts))
    return starts, ends, n_cand


def bool_mask_to_range_arrays(mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray, int]:
    """Vectorized conversion of a boolean mask into contiguous int32 [start, end) run arrays."""
    m = np.asarray(mask, dtype=np.bool_)
    if not np.any(m):
        empty = np.empty(0, dtype=np.int32)
        return empty, empty, 0
    padded = np.empty(len(m) + 2, dtype=np.int8)
    padded[0] = 0
    padded[1:-1] = m
    padded[-1] = 0
    diffs = np.diff(padded)
    starts = np.ascontiguousarray(np.flatnonzero(diffs == 1), dtype=np.int32)
    ends = np.ascontiguousarray(np.flatnonzero(diffs == -1), dtype=np.int32)
    n_cand = int(np.sum(ends - starts))
    return starts, ends, n_cand


class TriModalPlannerV3:
    """
    Native C++ Tri-Modal Query Planner with Local-Stall Mode-3 Escalation Guard.
    """

    def __init__(
        self,
        auth_graph: ZanzibarAuthGraph,
        z_corpus: ZOrderedCorpus,
        hhnsw: GeometricHHNSW,
        s_dense_threshold: float = 0.60,
        s_sparse_threshold: float = 0.015,
        hardware_kappa: float = 32.0,
        ef_search: int = 64,
        tau_high: float = 0.55,
        tau_low: float = 0.02,
        tau_stall: float = 0.04,
        stall_check_hops: int = 16,
        n_guard: int = 25_000,
        mode3_precision: str = "sq8",  # "sq8" | "f32"
        sq8_rerank_mult: int = 4,
        use_express_bridges: bool = True,
        use_portals: bool = True,
        max_portals: int = 4,
    ):
        self.auth_graph = auth_graph
        self.z_corpus = z_corpus
        self.hhnsw = hhnsw
        self.s_dense_threshold = s_dense_threshold
        self.s_sparse_threshold = s_sparse_threshold
        self.hardware_kappa = hardware_kappa
        self.ef_search = ef_search
        self.tau_high = tau_high
        self.tau_low = tau_low
        self.tau_stall = tau_stall
        self.stall_check_hops = stall_check_hops
        self.n_guard = n_guard
        self.mode3_precision = mode3_precision
        self.sq8_rerank_mult = sq8_rerank_mult
        self.use_express_bridges = use_express_bridges
        self.use_portals = use_portals
        self.max_portals = max_portals

        base_crossover = compute_optimal_crossover_threshold(
            ef_search=ef_search,
            m_degree=hhnsw.M,
            hardware_kappa=hardware_kappa,
        )["n_flat_star"]
        self.n_flat_star = min(
            base_crossover,
            max(16, int(round(self.z_corpus.N * self.s_sparse_threshold))),
        )

    def _run_mode3(
        self, q: np.ndarray, starts: np.ndarray, ends: np.ndarray, k: int
    ) -> Tuple[List[int], List[float], int]:
        if self.mode3_precision == "f32":
            ids, scores, evals = mode3_scan_ranges_f32(
                self.z_corpus.vectors, q, starts, ends, k=k
            )
            return ids.tolist(), scores.tolist(), evals
        q_sq8 = np.ascontiguousarray(
            np.clip(np.round(q * 127.0), -127, 127).astype(np.int8)
        )
        rerank_k = max(k * self.sq8_rerank_mult, 64)
        ids, scores, evals = mode3_scan_ranges_sq8(
            self.z_corpus.sq8_vectors,
            self.z_corpus.vectors,
            q_sq8,
            q,
            starts,
            ends,
            k=k,
            rerank_k=rerank_k,
        )
        return ids.tolist(), scores.tolist(), evals

    def query_with_ranges(
        self,
        query_vec: np.ndarray,
        starts: np.ndarray,
        ends: np.ndarray,
        n_cand: Optional[int] = None,
        k: int = 10,
        bitmap_compile_ms: float = 0.0,
    ) -> TriModalResultV3:
        """Fast path when Z-order CRoaring [start, end) ranges are already compiled."""
        t_exec0 = time.perf_counter()
        q = np.ascontiguousarray(query_vec, dtype=np.float32)
        if n_cand is None:
            n_cand = int(np.sum(ends - starts)) if len(starts) > 0 else 0
        global_s = n_cand / float(max(1, self.z_corpus.N))

        hops_1 = hops_2 = hops_tp = 0
        mean_s_loc = 0.0
        stalled_escalated = False

        if n_cand == 0 or len(starts) == 0:
            mode = "EMPTY_FAST_RETURN"
            top_ids, top_scores, dist_evals = [], [], 0
        elif n_cand <= self.n_flat_star or global_s <= self.s_sparse_threshold:
            mode = f"MODE_3_CPP_NEON_{self.mode3_precision.upper()}"
            top_ids, top_scores, dist_evals = self._run_mode3(q, starts, ends, k=k)
        else:
            if global_s > self.s_dense_threshold:
                mode = "MODE_1_DENSE_1HOP_HNSW"
                th, tl = min(0.15, self.tau_high), 0.01
            else:
                mode = "MODE_2_GEOMETRIC_HHNSW_GLS"
                th, tl = self.tau_high, self.tau_low

            allow_guard = (self.tau_stall > 0.0) and (n_cand <= self.n_guard)
            res = self.hhnsw.search_ranges(
                query_vec=q,
                starts=starts,
                ends=ends,
                k=k,
                ef_search=self.ef_search,
                tau_high=th,
                tau_low=tl,
                use_express_bridges=self.use_express_bridges,
                use_portals=self.use_portals,
                max_portals=self.max_portals,
                use_gls_adaptive=True,
                faiss_style_1hop=False,
                tau_stall=self.tau_stall if allow_guard else 0.0,
                stall_check_hops=self.stall_check_hops,
            )
            hops_1 = res.hops_1hop
            hops_2 = res.hops_2hop
            hops_tp = res.hops_teleport
            mean_s_loc = res.mean_s_loc_hat

            if allow_guard and res.stalled:
                stalled_escalated = True
                mode = f"MODE_3_STALL_GUARD_{self.mode3_precision.upper()}"
                top_ids, top_scores, m3_evals = self._run_mode3(q, starts, ends, k=k)
                dist_evals = res.distance_evaluations + m3_evals
            else:
                top_ids = res.top_k_ids
                top_scores = res.top_k_scores
                dist_evals = res.distance_evaluations

        search_exec_ms = (time.perf_counter() - t_exec0) * 1000.0
        return TriModalResultV3(
            top_k_ids=top_ids,
            top_k_scores=top_scores,
            execution_mode=mode,
            global_selectivity=global_s,
            candidate_count=n_cand,
            n_ranges=int(len(starts)),
            stalled_escalated=stalled_escalated,
            distance_evaluations=dist_evals,
            hops_1hop=hops_1,
            hops_2hop=hops_2,
            hops_teleport=hops_tp,
            mean_s_loc_hat=mean_s_loc,
            bitmap_compile_ms=bitmap_compile_ms,
            search_exec_ms=search_exec_ms,
            total_latency_ms=bitmap_compile_ms + search_exec_ms,
        )

    def query(
        self,
        query_vec: np.ndarray,
        principal_id: str,
        concept_ids: Optional[Set[str]] = None,
        k: int = 10,
        override_bitmap_phi: Optional[RoaringRunBitmap] = None,
    ) -> TriModalResultV3:
        t0 = time.perf_counter()
        if override_bitmap_phi is not None:
            b_phi = override_bitmap_phi
        else:
            tokens_pos, tokens_neg = resolve_ubp_tokens(self.auth_graph, principal_id)
            b_acl = self.z_corpus.compile_acl_bitmap_ubp(tokens_pos, tokens_neg)
            if concept_ids:
                b_ont = self.z_corpus.compile_ontology_bitmap(concept_ids)
                b_phi = b_ont.intersect(b_acl)
            else:
                b_phi = b_acl
        starts, ends, n_cand = runs_to_range_arrays(b_phi)
        bm_ms = (time.perf_counter() - t0) * 1000.0
        return self.query_with_ranges(
            query_vec=query_vec,
            starts=starts,
            ends=ends,
            n_cand=n_cand,
            k=k,
            bitmap_compile_ms=bm_ms,
        )
