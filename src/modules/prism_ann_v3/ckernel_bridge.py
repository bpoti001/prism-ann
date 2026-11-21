"""
C++17 / ARM NEON SIMD Kernel ctypes Bridge for Prism-ANN v3 (ADR-0005)
======================================================================
Loads `bench/_build/libprism_ckernel.dylib` compiled from `bench/prism_ckernel.cpp`
and exposes zero-copy NumPy wrappers for:
  - `mode3_scan_ranges_f32`
  - `mode3_scan_ranges_sq8`
  - `search_hhnsw_gls_cpp`
  - `select_rng_bridges_cpp`
  - `remap_hnsw_csr_cpp`
  - O(N_cand / 64) range bitset set/clear helpers
"""

from __future__ import annotations

import ctypes
import os
import subprocess
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
CKERNEL_SRC = os.path.join(REPO_ROOT, "bench", "prism_ckernel.cpp")
CKERNEL_DYLIB = os.path.join(REPO_ROOT, "bench", "_build", "libprism_ckernel.dylib")


class PrismSearchStatsC(ctypes.Structure):
    _fields_ = [
        ("dist_computations", ctypes.c_int64),
        ("hops_1hop", ctypes.c_int32),
        ("hops_2hop", ctypes.c_int32),
        ("hops_teleport", ctypes.c_int32),
        ("expansions", ctypes.c_int32),
        ("n_auth_found", ctypes.c_int32),
        ("stalled", ctypes.c_int32),
        ("mean_s_loc_hat", ctypes.c_float),
        ("early_s_loc_hat", ctypes.c_float),
    ]


@dataclass
class CKernelSearchStats:
    dist_computations: int
    hops_1hop: int
    hops_2hop: int
    hops_teleport: int
    expansions: int
    n_auth_found: int
    stalled: bool
    mean_s_loc_hat: float
    early_s_loc_hat: float


_LIB_CACHE: Optional[ctypes.CDLL] = None


def compile_ckernel(force: bool = False) -> str:
    """Compiles bench/prism_ckernel.cpp -> bench/_build/libprism_ckernel.dylib."""
    if not force and os.path.exists(CKERNEL_DYLIB):
        if os.path.getmtime(CKERNEL_DYLIB) >= os.path.getmtime(CKERNEL_SRC):
            return CKERNEL_DYLIB
    os.makedirs(os.path.dirname(CKERNEL_DYLIB), exist_ok=True)
    cmd = [
        "clang++",
        "-O3",
        "-mcpu=native",
        "-std=c++17",
        "-shared",
        "-fPIC",
    ]
    sdk_stable = "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk"
    if os.path.isdir(sdk_stable):
        cmd.extend(["-isysroot", sdk_stable])
    cmd.extend([CKERNEL_SRC, "-o", CKERNEL_DYLIB])
    subprocess.run(cmd, check=True)
    return CKERNEL_DYLIB


def load_ckernel() -> ctypes.CDLL:
    global _LIB_CACHE
    if _LIB_CACHE is not None:
        return _LIB_CACHE
    if not os.path.exists(CKERNEL_DYLIB):
        compile_ckernel()
    lib = ctypes.CDLL(CKERNEL_DYLIB)

    c_i32_p = ctypes.POINTER(ctypes.c_int32)
    c_i64_p = ctypes.POINTER(ctypes.c_int64)
    c_u64_p = ctypes.POINTER(ctypes.c_uint64)
    c_u32_p = ctypes.POINTER(ctypes.c_uint32)
    c_u8_p = ctypes.POINTER(ctypes.c_uint8)
    c_i8_p = ctypes.POINTER(ctypes.c_int8)
    c_f32_p = ctypes.POINTER(ctypes.c_float)

    lib.prism_kernel_has_neon.restype = ctypes.c_int32
    lib.prism_kernel_has_dotprod.restype = ctypes.c_int32

    lib.prism_ranges_set_bitset.argtypes = [c_i32_p, c_i32_p, ctypes.c_int32, c_u64_p, ctypes.c_int32]
    lib.prism_ranges_clear_bitset.argtypes = [c_i32_p, c_i32_p, ctypes.c_int32, c_u64_p, ctypes.c_int32]
    lib.prism_mask_bytes_to_bitset.argtypes = [c_u8_p, c_u64_p, ctypes.c_int32]

    lib.prism_mode3_scan_ranges_f32.restype = ctypes.c_int64
    lib.prism_mode3_scan_ranges_f32.argtypes = [
        c_f32_p, ctypes.c_int32, ctypes.c_int32, c_f32_p,
        c_i32_p, c_i32_p, ctypes.c_int32, ctypes.c_int32,
        c_i32_p, c_f32_p,
    ]

    lib.prism_mode3_scan_ranges_sq8.restype = ctypes.c_int64
    lib.prism_mode3_scan_ranges_sq8.argtypes = [
        c_i8_p, c_f32_p, ctypes.c_int32, ctypes.c_int32,
        c_i8_p, c_f32_p, c_i32_p, c_i32_p, ctypes.c_int32,
        ctypes.c_int32, ctypes.c_int32, c_i32_p, c_f32_p,
    ]

    lib.prism_search_hhnsw_gls.restype = ctypes.c_int32
    lib.prism_search_hhnsw_gls.argtypes = [
        c_f32_p, ctypes.c_int32, ctypes.c_int32,
        ctypes.c_int32, ctypes.c_int32, c_i64_p, c_i32_p, c_i32_p,
        c_i32_p, ctypes.c_int32, c_i32_p, ctypes.c_int32,
        c_u64_p, c_i32_p, c_i32_p, ctypes.c_int32,
        c_f32_p, ctypes.c_int32, ctypes.c_int32,
        ctypes.c_float, ctypes.c_float,
        ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32,
        ctypes.c_float, ctypes.c_int32,
        c_u32_p, ctypes.c_uint32,
        c_i32_p, c_f32_p, ctypes.POINTER(PrismSearchStatsC),
    ]

    lib.prism_select_rng_bridges.argtypes = [
        c_f32_p, c_i32_p, c_i32_p, c_f32_p,
        ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32,
        ctypes.c_int32, ctypes.c_int32, ctypes.c_float, c_i32_p,
    ]

    lib.prism_remap_hnsw_csr.argtypes = [
        c_i64_p, c_i32_p, c_i32_p, c_i32_p,
        ctypes.c_int32, ctypes.c_int32,
        c_i64_p, c_i32_p, c_i32_p,
    ]

    _LIB_CACHE = lib
    return lib


def ranges_set_bitset(
    starts: np.ndarray, ends: np.ndarray, mask_bits: np.ndarray, n_total: int
) -> None:
    if len(starts) == 0:
        return
    lib = load_ckernel()
    lib.prism_ranges_set_bitset(
        starts.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
        ends.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
        ctypes.c_int32(len(starts)),
        mask_bits.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)),
        ctypes.c_int32(n_total),
    )


def ranges_clear_bitset(
    starts: np.ndarray, ends: np.ndarray, mask_bits: np.ndarray, n_total: int
) -> None:
    if len(starts) == 0:
        return
    lib = load_ckernel()
    lib.prism_ranges_clear_bitset(
        starts.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
        ends.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
        ctypes.c_int32(len(starts)),
        mask_bits.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)),
        ctypes.c_int32(n_total),
    )


def mode3_scan_ranges_f32(
    vectors: np.ndarray,
    query: np.ndarray,
    starts: np.ndarray,
    ends: np.ndarray,
    k: int = 10,
) -> Tuple[np.ndarray, np.ndarray, int]:
    """Zero-copy C++ NEON FP32 scan over CRoaring [start, end) ranges."""
    n_ranges = int(len(starts))
    if n_ranges == 0 or k <= 0:
        return np.empty(0, dtype=np.int32), np.empty(0, dtype=np.float32), 0
    lib = load_ckernel()
    N, d = vectors.shape
    out_ids = np.full(k, -1, dtype=np.int32)
    out_scores = np.full(k, -1e30, dtype=np.float32)
    evals = int(
        lib.prism_mode3_scan_ranges_f32(
            vectors.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            ctypes.c_int32(N),
            ctypes.c_int32(d),
            query.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            starts.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
            ends.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
            ctypes.c_int32(n_ranges),
            ctypes.c_int32(k),
            out_ids.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
            out_scores.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        )
    )
    valid = out_ids >= 0
    return out_ids[valid], out_scores[valid], evals


def mode3_scan_ranges_sq8(
    sq8_vectors: np.ndarray,
    fp32_vectors: np.ndarray,
    q_sq8: np.ndarray,
    q_fp32: np.ndarray,
    starts: np.ndarray,
    ends: np.ndarray,
    k: int = 10,
    rerank_k: int = 40,
) -> Tuple[np.ndarray, np.ndarray, int]:
    """Zero-copy C++ NEON SQ8 scan (vdotq_s32) + top-rerank_k exact FP32 rerank."""
    n_ranges = int(len(starts))
    if n_ranges == 0 or k <= 0:
        return np.empty(0, dtype=np.int32), np.empty(0, dtype=np.float32), 0
    lib = load_ckernel()
    N, d = sq8_vectors.shape
    out_ids = np.full(k, -1, dtype=np.int32)
    out_scores = np.full(k, -1e30, dtype=np.float32)
    evals = int(
        lib.prism_mode3_scan_ranges_sq8(
            sq8_vectors.ctypes.data_as(ctypes.POINTER(ctypes.c_int8)),
            fp32_vectors.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            ctypes.c_int32(N),
            ctypes.c_int32(d),
            q_sq8.ctypes.data_as(ctypes.POINTER(ctypes.c_int8)),
            q_fp32.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            starts.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
            ends.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
            ctypes.c_int32(n_ranges),
            ctypes.c_int32(k),
            ctypes.c_int32(max(k, rerank_k)),
            out_ids.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
            out_scores.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        )
    )
    valid = out_ids >= 0
    return out_ids[valid], out_scores[valid], evals


def search_hhnsw_gls_cpp(
    vectors: np.ndarray,
    entry_point: int,
    max_level: int,
    upper_offsets: Optional[np.ndarray],
    upper_neighbors: Optional[np.ndarray],
    cum_nn_per_lvl: Optional[np.ndarray],
    base_neighbors: np.ndarray,
    express_bridges: Optional[np.ndarray],
    mask_bits: np.ndarray,
    starts: np.ndarray,
    ends: np.ndarray,
    query: np.ndarray,
    k: int,
    ef_search: int,
    tau_high: float,
    tau_low: float,
    use_express_bridges: bool,
    use_portals: bool,
    max_portals: int,
    use_gls_adaptive: bool,
    faiss_style_1hop: bool,
    tau_stall: float,
    stall_check_hops: int,
    visited_epoch: np.ndarray,
    current_epoch: int,
) -> Tuple[np.ndarray, np.ndarray, CKernelSearchStats]:
    """Invokes native C++ prism_search_hhnsw_gls with O(1) epoch visited tracking."""
    lib = load_ckernel()
    N, d = vectors.shape
    m_base = int(base_neighbors.shape[1])
    m_bridge = int(express_bridges.shape[1]) if express_bridges is not None else 0

    null_i64 = ctypes.POINTER(ctypes.c_int64)()
    null_i32 = ctypes.POINTER(ctypes.c_int32)()
    p_uoff = upper_offsets.ctypes.data_as(ctypes.POINTER(ctypes.c_int64)) if upper_offsets is not None else null_i64
    p_unb = upper_neighbors.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)) if upper_neighbors is not None else null_i32
    p_cum = cum_nn_per_lvl.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)) if cum_nn_per_lvl is not None else null_i32
    p_br = express_bridges.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)) if express_bridges is not None else null_i32
    p_st = starts.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)) if len(starts) > 0 else null_i32
    p_en = ends.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)) if len(ends) > 0 else null_i32

    out_ids = np.full(k, -1, dtype=np.int32)
    out_scores = np.full(k, -1e30, dtype=np.float32)
    c_stats = PrismSearchStatsC()

    n_out = int(
        lib.prism_search_hhnsw_gls(
            vectors.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            ctypes.c_int32(N),
            ctypes.c_int32(d),
            ctypes.c_int32(entry_point),
            ctypes.c_int32(max_level),
            p_uoff,
            p_unb,
            p_cum,
            base_neighbors.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
            ctypes.c_int32(m_base),
            p_br,
            ctypes.c_int32(m_bridge),
            mask_bits.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)),
            p_st,
            p_en,
            ctypes.c_int32(len(starts)),
            query.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            ctypes.c_int32(k),
            ctypes.c_int32(ef_search),
            ctypes.c_float(tau_high),
            ctypes.c_float(tau_low),
            ctypes.c_int32(1 if use_express_bridges else 0),
            ctypes.c_int32(1 if use_portals else 0),
            ctypes.c_int32(max_portals),
            ctypes.c_int32(1 if use_gls_adaptive else 0),
            ctypes.c_int32(1 if faiss_style_1hop else 0),
            ctypes.c_float(tau_stall),
            ctypes.c_int32(stall_check_hops),
            visited_epoch.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),
            ctypes.c_uint32(current_epoch),
            out_ids.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
            out_scores.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            ctypes.byref(c_stats),
        )
    )
    stats = CKernelSearchStats(
        dist_computations=int(c_stats.dist_computations),
        hops_1hop=int(c_stats.hops_1hop),
        hops_2hop=int(c_stats.hops_2hop),
        hops_teleport=int(c_stats.hops_teleport),
        expansions=int(c_stats.expansions),
        n_auth_found=int(c_stats.n_auth_found),
        stalled=bool(c_stats.stalled != 0),
        mean_s_loc_hat=float(c_stats.mean_s_loc_hat),
        early_s_loc_hat=float(c_stats.early_s_loc_hat),
    )
    return out_ids[:n_out], out_scores[:n_out], stats


def select_rng_bridges_cpp(
    bucket_vecs: np.ndarray,
    global_ids: np.ndarray,
    cand_local_ids: np.ndarray,
    cand_sims: np.ndarray,
    n_slots: int,
    medoid_local: int,
    include_medoid: bool = True,
    rng_alpha: float = 1.0,
) -> np.ndarray:
    """Runs C++ Vamana/RNG-diversity bridge selection for a single bucket."""
    lib = load_ckernel()
    n_b, d = bucket_vecs.shape
    K = int(cand_local_ids.shape[1])
    out = np.full((n_b, n_slots), -1, dtype=np.int32)
    lib.prism_select_rng_bridges(
        np.ascontiguousarray(bucket_vecs, dtype=np.float32).ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        np.ascontiguousarray(global_ids, dtype=np.int32).ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
        np.ascontiguousarray(cand_local_ids, dtype=np.int32).ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
        np.ascontiguousarray(cand_sims, dtype=np.float32).ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        ctypes.c_int32(n_b),
        ctypes.c_int32(d),
        ctypes.c_int32(K),
        ctypes.c_int32(n_slots),
        ctypes.c_int32(medoid_local),
        ctypes.c_int32(1 if include_medoid else 0),
        ctypes.c_float(rng_alpha),
        out.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
    )
    return out


def remap_hnsw_csr_cpp(
    offsets_int: np.ndarray,
    neighbors_int: np.ndarray,
    perm: np.ndarray,
    inv_perm: np.ndarray,
    m_base: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Remaps FAISS HNSW CSR arrays from internal insertion order into Z-order ID space."""
    lib = load_ckernel()
    N = int(len(perm))
    off_i64 = np.ascontiguousarray(offsets_int, dtype=np.int64)
    nb_i32 = np.ascontiguousarray(neighbors_int, dtype=np.int32)
    perm_i32 = np.ascontiguousarray(perm, dtype=np.int32)
    inv_i32 = np.ascontiguousarray(inv_perm, dtype=np.int32)

    out_offsets = np.empty(N + 1, dtype=np.int64)
    out_neighbors = np.empty(len(nb_i32), dtype=np.int32)
    out_base_l0 = np.full((N, m_base), -1, dtype=np.int32)

    lib.prism_remap_hnsw_csr(
        off_i64.ctypes.data_as(ctypes.POINTER(ctypes.c_int64)),
        nb_i32.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
        perm_i32.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
        inv_i32.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
        ctypes.c_int32(N),
        ctypes.c_int32(m_base),
        out_offsets.ctypes.data_as(ctypes.POINTER(ctypes.c_int64)),
        out_neighbors.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
        out_base_l0.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
    )
    return out_offsets, out_neighbors, out_base_l0
