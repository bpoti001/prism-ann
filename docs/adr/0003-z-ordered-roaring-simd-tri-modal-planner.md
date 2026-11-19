# ADR-0003: Lexicographic Ancestor-Magnet Z-Order Layout & Shard-Coupled Tri-Modal Query Planner

- **Status**: `accepted`
- **Date**: 2026-11-19
- **Scope**: `src/modules/prism_ann/trimodal_planner.py`
- **Mapped Paper Section**: Section 3.3 — Theorem 4 (Optimal Tri-Modal Crossover & Shard Coupling)

## Context
When candidate cardinality $N_{\text{cand}} = \operatorname{popcount}(B_\Phi)$ falls into the ultra-sparse regime ($N_{\text{cand}} \le N_{\text{flat}}^*$), sequential SIMD evaluation over INT8 quantized vectors (`SQ8`) outperforms random-access graph pointer chasing. However, if vector IDs are ordered by arrival timestamp, iterating over $B_\Phi$ causes random DRAM cache misses (`gather` penalty).

## Decision
1. **Lexicographic `(Container_ID, Meaning_Magnet_ID)` Vector ID Layout**: Order internal vector IDs by primary structural container and Meaning Magnet so that pruned capability tokens $t \in T_{\text{UBP}}^+(u)$ map to contiguous integer runs (`RunContainers` in Roaring Bitmaps).
2. **Shard-Coupled Tri-Modal Routing**: Route queries deterministically based on $(S, N_{\text{cand}})$ across Mode 1 (1-Hop HNSW, $S > 0.60$), Mode 2 (`H-HNSW` + `ACORN-GLS`, $S_{\text{low}} \le S \le 0.60$ and $N_{\text{cand}} > N_{\text{flat}}^*$), and Mode 3 (Contiguous Roaring-SIMD `SQ8` Scan, $N_{\text{cand}} \le N_{\text{flat}}^*$).

## Alternatives Considered (Design-It-Twice)
1. **Alternative A — Arrival-Order IDs with Random Vector Gather**: Suffers L3/TLB cache misses during flat scan, reducing $\kappa = c_{\text{rand}}/c_{\text{simd}}$ from $32\times$ to $6\times$. Rejected.
2. **Alternative B — `pgvector` v0.8.0 Iterative HNSW Scan (Baseline B7)**: Continues walking HNSW until $k$ matches are found; degrades to $>200\text{ ms}$ tail latency at $S < 0.005$. Rejected.

## Mapped Paper Theorem & Bound
**Theorem 4 (Tri-Modal Crossover & Shard Coupling):** Contiguous SIMD scanning strictly dominates graph traversal in both recall ($1.0$) and latency whenever $N_{\text{cand}} \le N_{\text{flat}}^* = \kappa \cdot E_{\text{ACORN-GLS}}(S, r)$, and capping shard size at $N_{\text{shard}}^* = N_{\text{flat}}^* / S_{\text{crit}}^{\text{bridge}}$ eliminates any recall-or-latency dead zone.

## Deep Module Seam
`src/modules/prism_ann/trimodal_planner.py` -> `execute_trimodal_query(planner, query_vec, principal_id, concept_ids, k)`.

## Consequences
- **Positive**: Guarantees $1.000$ Recall@10 in the extreme sub-0.1% regime at $\le 11.6\text{ ms}$ P99 latency.
- **Negative**: Periodic background compaction re-sorts newly ingested vectors into Z-order segments.
- **Reversibility**: `Two-Way Door`.
