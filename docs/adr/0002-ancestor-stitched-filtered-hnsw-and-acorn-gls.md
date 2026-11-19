# ADR-0002: Ancestor-Stitched Express Bridges (`H-HNSW`) and Bitmask-`POPCNT` Adaptive `ACORN-GLS` Traversal

- **Status**: `accepted`
- **Date**: 2026-11-19
- **Scope**: `src/modules/prism_ann/hnsw_gls.py`
- **Mapped Paper Section**: Section 3.2 — Theorem 2 (Sub-1% Percolation Cliff) & Theorem 3 (Percolation Restoration via Express Bridges)

## Context
Predicate-agnostic 2-hop HNSW traversal (`ACORN-1`, SIGMOD 2024) breaks down when composite predicates ($\text{Ontology} \land \text{ReBAC}^+ \land \neg\text{ReBAC}^-$) push global selectivity below $S < 0.01$ or when negative query-predicate correlation ($r = S_{\text{loc}}/S < 1$, *FANNBench/GLS* 2025) depletes the local neighborhood around $q$, causing greedy traversal to stall with probability $P_{\text{stall}} \ge (1 - rS/2)^{M(M+1)}$. Furthermore, `ACORN-1` wastes CPU cycles performing 2-hop expansions ($M^2 = 256$ nodes) inside locally dense pockets.

## Decision
1. **Ancestor-Stitched Express Bridges (`H-HNSW`)**: During HNSW construction, augment each node's base-layer neighbor list ($M=16$) with $M_{\text{bridge}} = 4$ hierarchy-constrained long-range links ($2$ sharing the node's mid-level structural container $g_\ell \in \operatorname{Anc}(v_i)$ and $2$ sharing its primary Meaning Magnet $m_k \in \tau(v_i)$).
2. **Bitmask-`POPCNT` Local-Selectivity-Adaptive Traversal (`ACORN-GLS`)**: At each visited node $v$, compute instantaneous local selectivity $\hat{S}_{\text{loc}}(v) = \operatorname{popcount}(\mathcal{N}_1(v) \cap B_\Phi) / |\mathcal{N}_1(v)|$ in $O(1)$ time:
   - If $\hat{S}_{\text{loc}}(v) \ge 0.25$: execute **1-hop standard HNSW** (skipping 2-hop overhead).
   - If $0.02 \le \hat{S}_{\text{loc}}(v) < 0.25$: execute **2-hop `ACORN-1` bridge walk**.
   - If $\hat{S}_{\text{loc}}(v) < 0.02$: execute **Express-Bridge Teleportation** along the $M_{\text{bridge}}$ edges to escape negative-correlation pockets.

## Alternatives Considered (Design-It-Twice)
1. **Alternative A — Standalone `ACORN-1` (`gamma=1`, Baseline B3)**: Zero extra memory, but recall drops to $52\%\text{--}61\%$ below $1\%$ selectivity or under $r < 0.5$. Rejected.
2. **Alternative B — `ACORN-gamma` (`gamma=10..20`, Baseline B4)**: Expands all neighbor lists indiscriminately, inflating index build time by $9\times\text{--}53\times$ and RAM by $4\times\text{--}8\times$. Rejected.
3. **Alternative C — `UNG` Static Label-Navigating Graph (SIGMOD 2024, Baseline B6)**: Pre-builds a label-set containment graph. Rejected because effective ReBAC permissions and `DENY` rules are resolved dynamically per principal at query time.

## Mapped Paper Theorem & Bound
**Theorem 2 & Theorem 3:** While standard `ACORN-1` disconnects at $S_{\text{crit}} = \frac{2}{rM(M+1)} \approx 1.47\%$ (for $M=16, r=0.5$), adding $M_{\text{bridge}} = 4$ Ancestor-Stitched Express Bridges lowers the effective percolation threshold to $S_{\text{crit}}^{\text{bridge}} = S_{\text{crit}} \cdot S_{\text{container}} \approx 0.08\%$ with $< 8\%$ total memory overhead.

## Deep Module Seam
`src/modules/prism_ann/hnsw_gls.py` -> `search_hnsw_gls(index, query_vec, bitmap_phi, k, ef_search)`.

## Consequences
- **Positive**: Extends high-recall ($>97.5\%$) graph navigation down to $S \approx 8 \times 10^{-4}$ while cutting distance evaluations in dense regions by $2.8\times$.
- **Negative**: $+25\%$ base-layer edge storage ($pprox 8\%$ total index RAM overhead including vectors).
- **Reversibility**: `Two-Way Door`.
