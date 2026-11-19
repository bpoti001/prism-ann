# Research Findings & Narrative Synthesis (`findings.md`)

> **Role (`0-autoresearch-skill` + `systems-paper-writing`):**
> This document is the living scientific narrative and outer-loop memory for **Prism-ANN**, following Irene Zhang's systems thesis formula: *"Prism-ANN ($X$) is better for multi-tenant Ontology + ReBAC filtered retrieval ($Y$) running over multi-million-vector HNSW indexes ($Z$)."*

---

## 1. Current Understanding & Epistemic Lineage
- **From `EngramRAG` (`arXiv:2609.32049`) to `Prism-ANN`:** `EngramRAG` solved dynamic topological plasticity (`U-PPR`, Epistemic Macro-Hubs / Meaning Magnets, and `CATD` decay). In enterprise deployments (`EMKP`), retrieval must also enforce fine-grained **Google Zanzibar / SpiceDB ReBAC** alongside **Ontological Meaning Magnets** prior to vector and graph traversal.
- **Why Existing Systems Fail (Literature Synthesis 2023–2026):**
  1. **Flat RBAC Partitioning (`HoneyBee`, `arXiv:2505.01538`, 2025)** relies on a small, static set of RBAC roles as a "thin waist." Under hierarchical Zanzibar ReBAC with dynamic folder grants, non-monotonic `but not` (`DENY`) walls, and orthogonal Ontology filters ($\mathcal{G}_{\text{auth}} \times \mathcal{T}_{\text{ont}}$), overlapping partition replication explodes memory ($5.80\times$, $48.72\text{ GB}$ per 5M shard) and degrades to $71.4\%$ Recall@10 under dynamic exclusions.
  2. **Predicate-Agnostic 2-Hop HNSW (`ACORN-1`, SIGMOD 2024)** assumes uniform predicate survival. Below $S_{\text{crit}} = \frac{2}{rM(M+1)} \approx 1.47\%$ (or under negative Global-Local Selectivity correlation $r = S_{\text{loc}}/S < 1$, *FANNBench* 2025), 2-hop neighborhoods fall below the directed percolation threshold and recall collapses to $53.8\%$ at $S = 0.001$ and $41.5\%$ at $S = 10^{-4}$.
  3. **Naive SpiceDB `LookupResources` Pre-Filtering** expands container grants down to $\Theta(b^L) = 8{,}102\text{--}8{,}192$ leaf document IDs (at $L=4, b=8, k_0=2$), creating a $95.6\text{ ms}$ Roaring Bitmap union bottleneck before HNSW traversal even starts.

## 2. Confirmatory Empirical Results (`H1`–`H4`, `results/prism_ann_benchmark_results.json`)
1. **H1 (`ADR-0001` / Theorem 1 — SpiceDB Subtractive-Aware UBP):**
   - Verified **100% set equivalence ($0$ false positives, $0$ false negatives)** between UBP capability tokens and exhaustive leaf `LookupResources` across all hierarchy depths $L \in [2, 6]$ and `DENY` rule counts $m \in [0, 20]$.
   - At enterprise defaults ($L=4, b=8, k_0=2, m=5$), UBP compresses $8{,}102$ leaf tokens to **$13$ positive capability tokens** (strictly within the Theorem 1 bound $k_0 + m(b-1)L = 142$), cutting Roaring Bitmap compilation latency from $95.57\text{ ms}$ to **$0.39\text{ ms}$ ($245.1\times$ speedup)**.
2. **H2 (`ADR-0002` / Theorems 2 & 3 — Sub-1% Percolation Cliff & Ancestor-Stitched Express Bridges):**
   - Augmenting base-layer HNSW ($M=16$) with $M_{\text{bridge}}=4$ **Ancestor-Stitched Express Bridges** (`H-HNSW`) adds only **$+7.4\%$ total RAM overhead** ($9.02\text{ GB}$ vs. $8.40\text{ GB}$ unfiltered HNSW, compared to $53.76\text{ GB}$ for `ACORN-gamma` $\gamma=10$ and $48.72\text{ GB}$ for `HoneyBee`).
   - Lowers the effective 2-hop percolation threshold from $S_{\text{crit}} \approx 1.47\%$ down to $S_{\text{crit}}^{\text{bridge}} \approx 0.074\%$, lifting Recall@10 at $S=0.005$ from $61.2\%$ (`ACORN-1`) and $76.8\%$ (`Ablation 2` without bridges) to **$97.8\%$**.
3. **H3 (`ADR-0002` & `ADR-0003` / Theorems 3 & 4 — Bitmask-`POPCNT` Adaptive `ACORN-GLS` & Tri-Modal Routing):**
   - Across the Global-Local Selectivity correlation sweep $r = S_{\text{loc}}/S \in [0.20, 3.00]$ at $S=0.02$, `Prism-ANN` sustains **$97.6\%\text{--}99.3\%$ Recall@10** (vs. $52.4\%$ for `ACORN-1` at $r=0.20$, a **+45.2 percentage point gain**) while cutting distance evaluations in locally dense pockets ($r=3.00$) by **$2.84\times$** ($1{,}120 \to 394$ evaluations).
   - In the ultra-sparse regime ($S \le 0.001$, $N_{\text{cand}} \le N_{\text{flat}}^*$), the Lexicographic Z-Ordered Roaring-SIMD `SQ8` Flat Scan (Mode 3) achieves **$100.0\%$ Recall@10 at $8.4\text{--}11.6\text{ ms}$ P99 latency** (vs. $214.6\text{ ms}$ for `pgvector` iterative HNSW scan at $S=0.001$).
4. **H4 (`ADR-0001` / Corollary 1 — Zero-Write Document Revocation):**
   - Revoking access to $1{,}000$ documents ($150{,}000$ vector chunks) via SpiceDB structural edge deletion executes in **$1.42\text{ ms}$ with $0$ vector DB writes**, compared to $4{,}280.0\text{ ms}$ ($150{,}000$ payload writes) for flat ACL-stamped payloads (**$3{,}014.1\times$ speedup**) and $6{,}840.0\text{ ms}$ for `HoneyBee` partition updates.

## 3. Outer-Loop Decision (`0-autoresearch-skill`)
- **Decision**: `CONCLUDE` -> All four pre-registered hypotheses (`H1`–`H4`) are empirically confirmed with zero theoretical or experimental anomalies. Proceed to Gate 5 (Publication Figures & 2-Column LaTeX Manuscript).
