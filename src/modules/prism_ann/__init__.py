"""
Prism-ANN Deep Module Package (__init__.py)
===========================================
Exports only the canonical public interfaces from index.py.
"""

from .index import (
    PrismANNIndex,
    ZanzibarAuthGraph,
    UBPResolutionResult,
    resolve_ubp_tokens,
    AncestorStitchedHNSW,
    HNSWSearchResult,
    compute_theoretical_percolation_cliff,
    search_hnsw_gls,
    search_post_filter,
    search_1hop_prefilter,
    search_pgvector_iterative,
    RoaringRunBitmap,
    ZOrderedCorpus,
    TriModalQueryPlanner,
    TriModalQueryResult,
    compute_optimal_crossover_threshold,
    execute_trimodal_query,
)

__all__ = [
    "PrismANNIndex",
    "ZanzibarAuthGraph",
    "UBPResolutionResult",
    "resolve_ubp_tokens",
    "AncestorStitchedHNSW",
    "HNSWSearchResult",
    "compute_theoretical_percolation_cliff",
    "search_hnsw_gls",
    "search_post_filter",
    "search_1hop_prefilter",
    "search_pgvector_iterative",
    "RoaringRunBitmap",
    "ZOrderedCorpus",
    "TriModalQueryPlanner",
    "TriModalQueryResult",
    "compute_optimal_crossover_threshold",
    "execute_trimodal_query",
]
