# Experiment Protocol H1: SpiceDB Subtractive-Aware UBP Token Compression

- **Governing ADR**: `ADR-0001`
- **Mapped Theorem**: Theorem 1 (`|T_UBP^+(u)| <= k_0 + m * (b - 1) * L`)
- **Status**: `PRE_REGISTERED`

## 1. Hypothesis & Mechanistic Prediction
When resolving hierarchical permissions across an organizational tree of depth $L \in [2, 6]$ and branching factor $b \in [4, 12]$ with $k_0 \in [1, 5]$ top-level positive grants and $m \in [0, 20]$ explicit `DENY` exclusions (`but not` ethical walls):
1. **Exactness Invariant:** The union of inverted posting lists over $T_{\text{UBP}}^+(u) \setminus T_{\text{UBP}}^-(u)$ has **0 false positives and 0 false negatives** relative to exhaustive leaf `LookupResources` evaluation.
2. **Cardinality Bound:** Emitted token count never exceeds $k_0 + m(b-1)L$ ($\le 50$ tokens for enterprise defaults), reducing Roaring Bitmap union latency by $>15\times$ vs. naive leaf expansion.
