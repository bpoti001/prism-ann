# Research Findings & Narrative Synthesis (`findings.md`)

> **Role (`0-autoresearch-skill` + `systems-paper-writing`):**
> This document is the living scientific narrative and outer-loop memory for **Prism-ANN**, following Irene Zhang's systems thesis formula: *"Prism-ANN ($X$) is better for multi-tenant Ontology + ReBAC filtered retrieval ($Y$) running over multi-million-vector HNSW indexes ($Z$)."*

---

## 1. Current Understanding & Epistemic Lineage
- **From `EngramRAG` (`arXiv:2609.32049`) to `Prism-ANN`:** `EngramRAG` solved dynamic topological plasticity (`U-PPR`, Epistemic Macro-Hubs / Meaning Magnets, and `CATD` decay). In enterprise deployments (`EMKP`), retrieval must also enforce fine-grained **Google Zanzibar / SpiceDB ReBAC** alongside **Ontological Meaning Magnets** prior to vector and graph traversal.
- **Why Existing Systems Fail (Literature Synthesis 2023–2026):**
  1. **Flat RBAC Partitioning (`HoneyBee`, `arXiv:2505.01538`, 2025)** relies on a small, static set of RBAC roles as a "thin waist." Under hierarchical Zanzibar ReBAC with dynamic folder grants, non-monotonic `but not` (`DENY`) walls, and orthogonal Ontology filters ($\mathcal{G}_{\text{auth}} \times \mathcal{T}_{\text{ont}}$), overlapping partition replication explodes memory ($>6\times$) and breaks on dynamic ACL updates.
  2. **Predicate-Agnostic 2-Hop HNSW (`ACORN-1`, SIGMOD 2024)** assumes uniform predicate survival. Below $S_{\text{crit}} = \frac{2}{rM(M+1)} \approx 1.47\%$ (or under negative Global-Local Selectivity correlation $r = S_{\text{loc}}/S < 1$, *FANNBench* 2025), 2-hop neighborhoods fall below the directed percolation threshold and recall collapses to $50\%\text{--}60\%$.
  3. **Naive SpiceDB `LookupResources` Pre-Filtering** expands container grants down to $\Theta(b^L) \approx 10^4\text{--}10^5$ leaf document IDs, creating a 50–180 ms Roaring Bitmap union bottleneck before HNSW traversal even starts.

## 2. Core Algorithmic Mechanisms Under Evaluation
1. **Subtractive-Aware Upward Boundary Pruning (`ADR-0001` / Theorem 1):** Bounds query-time capability tokens to $\le k_0 + m(b-1)L \le 50$ and achieves $O(1)$ zero-write document revocation.
2. **Ancestor-Stitched Express Bridges & `ACORN-GLS` (`ADR-0002` / Theorems 2–3):** Adds $M_{\text{bridge}}=4$ intra-container/intra-magnet bridges ($<8\%$ RAM) and uses hardware `POPCNT` to estimate $\hat{S}_{\text{loc}}(v)$ on the fly, switching between 1-hop HNSW, 2-hop `ACORN-1`, and Express-Bridge Teleportation.
3. **Lexicographic Z-Order Roaring-SIMD Planner (`ADR-0003` / Theorem 4):** Aligns vector IDs by `(Container_ID, Meaning_Magnet_ID)` so Roaring Bitmap segments execute sequential L1/L2-prefetched SIMD scans below the hardware crossover $N_{\text{flat}}^*$.

## 3. Lessons and Constraints
- **Constraint 1 (Reviewer Defense):** Never rely solely on a brute-force flat-scan switch below 1% selectivity without `Ancestor-Stitched Express Bridges` and `ACORN-GLS`, because negative correlation ($r < 1$) can stall `ACORN-1` even when global $S = 3\%\text{--}5\%$ ($N_{\text{cand}} > 150{,}000$).
- **Constraint 2 (Zero Hallucination):** Every citation in `literature/survey.md` and `paper/references.bib` is programmatically verified against arXiv / Semantic Scholar / ACM Digital Library.
