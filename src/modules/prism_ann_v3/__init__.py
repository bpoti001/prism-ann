"""Prism-ANN v3 Deep Module (ADR-0005): Geometric H-HNSW v2 + C++ NEON Kernel."""

from .index import (
    GeometricBridgeConfig,
    GeometricHHNSW,
    HHNSWSearchResultV3,
    PrismANNIndexV3,
    TriModalPlannerV3,
    TriModalResultV3,
    bool_mask_to_range_arrays,
    runs_to_range_arrays,
    search_hhnsw_gls_py_ref,
)

__all__ = [
    "PrismANNIndexV3",
    "GeometricBridgeConfig",
    "GeometricHHNSW",
    "HHNSWSearchResultV3",
    "TriModalPlannerV3",
    "TriModalResultV3",
    "bool_mask_to_range_arrays",
    "runs_to_range_arrays",
    "search_hhnsw_gls_py_ref",
]
