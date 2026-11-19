"""
Prism-ANN Public Deep Module Seam (index.py)
============================================
Unifies ADR-0001 (SpiceDB UBP Auth Resolver), ADR-0002 (Ancestor-Stitched HNSW & ACORN-GLS),
and ADR-0003 (Z-Ordered Roaring-SIMD Tri-Modal Query Planner) behind a minimal public entry point.
"""

from __future__ import annotations
import numpy as np
from typing import Dict, List, Set, Tuple, Optional

from .ubp_resolver import (
    ZanzibarAuthGraph,
    UBPResolutionResult,
    resolve_ubp_tokens,
)
from .hnsw_gls import (
    AncestorStitchedHNSW,
    HNSWSearchResult,
    compute_theoretical_percolation_cliff,
    search_hnsw_gls,
    search_post_filter,
    search_1hop_prefilter,
)
from .trimodal_planner import (
    RoaringRunBitmap,
    ZOrderedCorpus,
    TriModalQueryPlanner,
    TriModalQueryResult,
    compute_optimal_crossover_threshold,
    execute_trimodal_query,
)


class PrismANNIndex:
    """
    Unified Deep Module Facade for Prism-ANN.
    Hides internal Z-Ordering, SpiceDB UBP graph cutting, Ancestor-Stitched Express Bridges,
    and POPCNT local-selectivity-adaptive routing behind a clean 3-method interface:
      - __init__(...)  (builds ZOrderedCorpus, AncestorStitchedHNSW, TriModalQueryPlanner)
      - search(query_vec, principal_id, concept_ids, k)
      - revoke_hierarchy_edge(parent_id, child_id)
    """

    def __init__(
        self,
        auth_graph: ZanzibarAuthGraph,
        raw_vectors: np.ndarray,
        ancestor_lineages: List[List[str]],
        meaning_magnet_ids: List[str],
        m_degree: int = 16,
        m_bridge: int = 4,
        ef_search: int = 64,
        seed: int = 42,
    ):
        self.auth_graph = auth_graph
        self.z_corpus = ZOrderedCorpus(
            raw_vectors=raw_vectors,
            ancestor_lineages=ancestor_lineages,
            meaning_magnet_ids=meaning_magnet_ids,
        )
        self.hnsw_index = AncestorStitchedHNSW(
            corpus_vectors=self.z_corpus.vectors,
            container_ids=self.z_corpus.primary_containers,
            meaning_magnet_ids=self.z_corpus.meaning_magnet_ids,
            m_degree=m_degree,
            m_bridge=m_bridge,
            seed=seed,
        )
        self.planner = TriModalQueryPlanner(
            auth_graph=self.auth_graph,
            z_corpus=self.z_corpus,
            hnsw_index=self.hnsw_index,
            ef_search=ef_search,
        )

    def search(
        self,
        query_vec: np.ndarray,
        principal_id: str,
        concept_ids: Optional[Set[str]] = None,
        k: int = 10,
    ) -> TriModalQueryResult:
        """Executes a ReBAC + Ontology filtered ANN query via the Tri-Modal Planner."""
        return execute_trimodal_query(
            planner=self.planner,
            query_vec=query_vec,
            principal_id=principal_id,
            concept_ids=concept_ids,
            k=k,
        )

    def revoke_hierarchy_edge(self, parent_id: str, child_id: str) -> int:
        """
        O(1) zero-write document or folder revocation in SpiceDB (ADR-0001 / Corollary 1).
        """
        return self.auth_graph.remove_hierarchy_edge(parent_id, child_id)


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
    "RoaringRunBitmap",
    "ZOrderedCorpus",
    "TriModalQueryPlanner",
    "TriModalQueryResult",
    "compute_optimal_crossover_threshold",
    "execute_trimodal_query",
]
