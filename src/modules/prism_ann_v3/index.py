"""
Prism-ANN v3 Public Deep Module Seam (`src/modules/prism_ann_v3/index.py`)
==========================================================================
Governing ADRs: ADR-0001, ADR-0002, ADR-0003, ADR-0005.
Unifies untouched `ubp_resolver.py` (ADR-0001), `GeometricHHNSW` (H-HNSW v2
geometric intra-container & intra-magnet express bridges), and `TriModalPlannerV3`
(native C++ ARM NEON Mode-3 + Local-Stall Guard) behind a clean Deep Module seam.
"""

from __future__ import annotations

from typing import List, Optional, Set

import numpy as np

from src.modules.prism_ann.trimodal_planner import RoaringRunBitmap, ZOrderedCorpus
from src.modules.prism_ann.ubp_resolver import ZanzibarAuthGraph, resolve_ubp_tokens
from .geometric_hhnsw import (
    GeometricBridgeConfig,
    GeometricHHNSW,
    HHNSWSearchResultV3,
    search_hhnsw_gls_py_ref,
)
from .trimodal_v3 import (
    TriModalPlannerV3,
    TriModalResultV3,
    bool_mask_to_range_arrays,
    runs_to_range_arrays,
)


class PrismANNIndexV3:
    """Unified Deep Module Facade for Prism-ANN v3."""

    def __init__(
        self,
        auth_graph: ZanzibarAuthGraph,
        raw_vectors: np.ndarray,
        ancestor_lineages: List[List[str]],
        meaning_magnet_ids: List[str],
        M: int = 16,
        m_bridge: int = 8,
        ef_construction: int = 64,
        ef_search: int = 64,
        tau_high: float = 0.55,
        tau_low: float = 0.02,
        tau_stall: float = 0.04,
        n_guard: int = 25_000,
        mode3_precision: str = "sq8",
        seed: int = 42,
    ):
        self.auth_graph = auth_graph
        self.z_corpus = ZOrderedCorpus(
            raw_vectors=raw_vectors,
            ancestor_lineages=ancestor_lineages,
            meaning_magnet_ids=meaning_magnet_ids,
        )
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

    def search(
        self,
        query_vec: np.ndarray,
        principal_id: str,
        concept_ids: Optional[Set[str]] = None,
        k: int = 10,
    ) -> TriModalResultV3:
        return self.planner.query(
            query_vec=query_vec,
            principal_id=principal_id,
            concept_ids=concept_ids,
            k=k,
        )

    def revoke_hierarchy_edge(self, parent_id: str, child_id: str) -> int:
        return self.auth_graph.remove_hierarchy_edge(parent_id, child_id)


__all__ = [
    "PrismANNIndexV3",
    "GeometricBridgeConfig",
    "GeometricHHNSW",
    "HHNSWSearchResultV3",
    "TriModalPlannerV3",
    "TriModalResultV3",
    "RoaringRunBitmap",
    "ZOrderedCorpus",
    "ZanzibarAuthGraph",
    "resolve_ubp_tokens",
    "runs_to_range_arrays",
    "bool_mask_to_range_arrays",
    "search_hhnsw_gls_py_ref",
]
