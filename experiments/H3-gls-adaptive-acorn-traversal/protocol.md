# Experiment Protocol H3: Bitmask-POPCNT Adaptive ACORN-GLS & Z-Ordered Tri-Modal Routing

- **Governing ADR**: `ADR-0002` & `ADR-0003`
- **Mapped Theorem**: Theorem 3 & Theorem 4
- **Status**: `PRE_REGISTERED`

## 1. Hypothesis & Mechanistic Prediction
Combining `ACORN-GLS` (per-node `POPCNT` local selectivity estimation $\hat{S}_{\text{loc}}(v)$ switching between 1-hop, 2-hop, and Express-Bridge Teleportation) with the Z-Ordered Roaring-SIMD Flat Scan ($N_{\text{cand}} \le N_{\text{flat}}^*$) sustains $\ge 97.5\%$ Recall@10 across all five orders of magnitude of selectivity ($S \in [10^{-4}, 1.0]$) while reducing average distance evaluations in dense regimes by $>2.5\times$ compared to static `ACORN-1`.
