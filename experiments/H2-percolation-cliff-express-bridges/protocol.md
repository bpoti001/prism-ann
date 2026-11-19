# Experiment Protocol H2: Sub-1% Percolation Cliff & Ancestor-Stitched Express Bridges

- **Governing ADR**: `ADR-0002`
- **Mapped Theorem**: Theorem 2 & Theorem 3
- **Status**: `PRE_REGISTERED`

## 1. Hypothesis & Mechanistic Prediction
Sweeping global selectivity $S \in [10^{-4}, 1.0]$ and Global-Local Selectivity correlation $r = S_{\text{loc}}/S \in [0.25, 4.0]$:
1. Standalone `ACORN-1` suffers percolation collapse (Recall@10 dropping below $65\%$) whenever $S < S_{\text{crit}} = \frac{2}{rM(M+1)}$.
2. Augmenting HNSW with $M_{\text{bridge}} = 4$ Ancestor-Stitched Express Bridges (`H-HNSW`) restores giant-component connectivity down to $S \approx 5 \times 10^{-4}$ with $< 8\%$ memory overhead.
