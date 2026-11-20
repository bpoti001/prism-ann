# Brake 3 — Independent Conference-Style Peer Review (Prism-ANN v2)

- **Reviewer**: Independent Auditor (Milestone 4, Phase 15-01)
- **Reviewed at**: 2026-11-20
- **Manuscript**: `paper/prism_ann.pdf` (`paper/prism_ann.tex`, 10 pages, IEEEtran conference format)
- **Manuscript SHA-256 (reviewed)**: `cdc06a7441b82d2245cf84d3f9ddcfba24a24919952b9ddc0e484e6ef12dea7e`
- **Manuscript SHA-256 (post-blocker template-fix recompile)**: `2b8c2d7570451d22e1a6dcb384706765c1ea525d3327fa9d6fae54eaa5871305` (removed `(X)`/`(Y)`/`(Z)` placeholders at line 81 and double `\paragraph` punctuation; all empirical content and technical weaknesses below remain unchanged)

---

## 1. Summary of Paper & Claims

The paper proposes **Prism-ANN**, an architecture for enterprise filtered Approximate Nearest Neighbor (ANN) search combining SpiceDB/Zanzibar hierarchical Relationship-Based Access Control (ReBAC, including subtractive `but not` / `DENY` exclusions) with ontological filters over HNSW vector indexes. Its three components are:
1. **Subtractive-Aware Upward Boundary Pruning ($\mathcal{P}_{\text{UBP}}$)**: Stamps chunks at ingest with immutable container lineages $\operatorname{Anc}(v_i)$ and resolves capability token pairs $(T_{\text{UBP}}^+, T_{\text{UBP}}^-)$ via top-down taint splitting in SpiceDB, yielding $|T_{\text{UBP}}^+| \le k_0 + m(b-1)L$ (Theorem 1), exact set equivalence with `LookupResources`, and $0$-write revocation (Corollary 1).
2. **Ancestor-Stitched Express Bridges (`H-HNSW`) and `ACORN-GLS`**: Adds $M_{\text{bridge}}=4$ intra-container and intra-magnet ring-chord links ($+1.0\%$ RAM at $d=384$) plus `POPCNT`-adaptive 1-hop / 2-hop / teleport traversal (Propositions 2–3).
3. **Lexicographic Z-Ordered Roaring-SIMD Tri-Modal Planner**: Orders internal IDs by $(\operatorname{Anc}, \text{Magnet})$ so container tokens map to contiguous Roaring `RunContainers` for quantized `SQ8` exact Mode 3 scanning below crossover $N_{\text{flat}}^*$ (Proposition 4).

The authors execute a single frozen confirmatory benchmark (`v2-confirmatory-002`, 62,410 raw JSONL records, 3 seeds) on 522,931 BEIR Quora passages (`all-MiniLM-L6-v2`, 384-d) with 9,985 strictly disjoint test queries against live SpiceDB v1.57.1, PostgreSQL 17.12 + pgvector 0.8.7, FAISS 1.16.0, compiled upstream C++ `stanford-futuredata/ACORN-1`, and `hnswlib` 0.8.0.

---

## 2. Strengths

1. **Exceptional Empirical Provenance & Scientific Honesty**: Unlike many systems papers that quietly tune around negative findings, the authors freeze the algorithm beforehand (`FREEZE.md`), trace every metric to per-query raw JSONL logs (`bench/harness.py`, `bench/recompute.py`), run live external database/gRPC engines (no toy reimplementations), and report **both falsified pre-registered hypotheses (`P2b` and `P3b`)** and regimes where `hnswlib` and `pgvector` outperform `prism-graph-only` plainly in the abstract, Table II, figures, and §VI.
2. **Decisive Systems Win on ReBAC Pre-Filtering & Revocation (H1v2 & H4v2)**: On real SpiceDB v1.57.1 across 600 principals ($0$–$20$ `DENY` edges), $\mathcal{P}_{\text{UBP}}$ achieves $0$ doc / $0$ chunk mismatches and cuts broad-principal pre-filter latency by $226.5\times$ locally ($0.310\text{ ms}$ vs. $70.15\text{ ms}$) and **$33.6\times$ even when fetching grants/denies live via `ReadRelationships` RPCs** ($2.089\text{ ms}$). Revoking $1{,}024$ docs ($153{,}600$ chunks) in SpiceDB takes $76.05\text{ ms}$ with $0$ vector writes versus $182.5\text{ s}$ ($2{,}400.1\times$ slower) for a B-tree-indexed `UPDATE` on a real PostgreSQL 17 + `pgvector` HNSW table.
3. **Appropriate Theoretical Calibration**: Reclassifying percolation and crossover claims into **Propositions 2–4 under explicit modeling assumptions** while preserving a clean formal proof for **Theorem 1** is mathematically disciplined and prevents overclaiming.
4. **Honest Upstream `ACORN-1` Comparison**: Compiling upstream C++ `stanford-futuredata/ACORN` (`c259f11`) with only a 3-line OOB memory-safety patch and selector wiring (`D5`) reveals real-world failure modes of `ACORN-1` on 523k embeddings (`11.4` evals stall, `0.85%` R@10 at $S=0.1\%$) without distorting the baseline.

---

## 3. Weaknesses & Technical Critique

### Major / Blocking Issues
1. **Unedited Writing-Template Placeholders in Introduction (`paper/prism_ann.tex:81`)**:
   The opening sentence of Section I reads verbatim:
   > *"Prism-ANN (X) is designed for multi-tenant Ontology and Relationship-Based Access Control (ReBAC) filtered retrieval (Y) over HNSW vector indexes (Z)."*
   Leaving `(X)`, `(Y)`, `(Z)` template placeholders in the published PDF is an immediate red flag that must be fixed before any submission.

### Substantive Technical & Experimental Weaknesses
2. **Missing Ablation Isolating `InitEntryPortals` vs. Express Bridges (`H-HNSW`)**:
   In `src/modules/prism_ann/hnsw_gls.py:362-375`, `search_hnsw_gls` populates `cand_queue` with up to 4 authorized entry nodes sampled directly from `valid_indices` (derived from bitmap $B_\Phi$), alongside 50 uniform upper-layer stride landmarks (`_select_upper_layer_entry`). Meanwhile, `faiss-hnsw-M16` and `acorn-1` begin from a single global top-layer entry point without authorized-portal injection. While using $B_\Phi$ for entry portals is legitimate for Prism-ANN, **no ablation separates the recall gain of `InitEntryPortals` from the gain of $M_{\text{bridge}}=4$ ring-chord bridges**. At $S=0.1\%$ or $r \le 0.5$, simply seeding search at 4 authorized nodes rather than an unauthorized global entry point can account for a substantial fraction of the `+22.25` / `+17.65` pt lift over `FAISS M=16`.
3. **Graph-Only Express Bridges Fail to Achieve Viable Recall at Low $S$, and Mode 3 Misses $S=2\%$ Negative-Correlation Queries (`H3`)**:
   - The authors transparently show that `prism-graph-only` reaches only `28.21%` ($S=0.1\%$), `45.93%` ($S=0.5\%$), and `53.27%` ($S=1.0\%$) Recall@10, far below `hnswlib-M16` (`99.3%–99.9%`) and `pgvector` (`75.5%–97.5%`). As a result, Prism-ANN's sub-1% recall rests entirely on **Mode 3 exact flat scanning** over Z-ordered intervals.
   - However, at $S=2.0\%$ in `H3` (`r <= 0.5`), `N_cand` (~10,243) exceeds Mode 3's `0.015 * N` (`7,844`) cutoff for nearly all queries (`725/735` depleted queries stay in Mode 2), so **`prism-full` itself collapses to `24.55%` Recall@10** (`Table IV`)—a major practical failure mode that §V-D does not explicitly call out. Similarly, at $S=5\%$ (`H2`), `prism-full` drops to `80.69%` recall in `9.23 ms`, whereas `hnswlib` achieves `99.34%` in `4.40 ms`.
4. **Comparison of Mode 3 (`prism-full`) Against `exact-brute-force` Latency**:
   In Table III, `exact-brute-force` (`X[valid] @ q` in BLAS) attains `100.00%` Recall@10 in `0.25 ms`, `0.89 ms`, and `1.94 ms` at $S=0.1\%, 0.5\%, 1.0\%$, outperforming `prism-full` (`1.10 ms`, `1.82 ms`, `2.14 ms`) by $1.1\times$–$4.4\times$. While `PrismFullSystem`'s Python/NumPy `from_bool_mask` and `sq8_vectors[start:end].astype(np.int32)` explain this overhead (and Mode 3 in C++/SIMD paired with UBP `CRoaring` ranges would eliminate `np.flatnonzero(mask)` gather cost), the paper does not analyze why Mode 3 underperforms `exact-brute-force` in the measured implementation, nor does it yet provide a C++ Mode 3 kernel to substantiate Proposition 4's $\kappa$ crossover speedup empirically.
5. **Theoretical Scope Gap for Multi-Parent DAGs (`Theorem 1` vs. `Definition 1` / `ZOrderedCorpus`)**:
   Theorem 1 carefully restricts its cardinality bound to single-parent trees while claiming Eq. (5) exact set equivalence on multi-parent DAGs. However, Definition 1 (`|Anc(v_i)| = L+1`), `ZOrderedCorpus` (`primary_containers = lin[-2]`), and single-tuple lexicographic sorting assume a single canonical lineage per chunk. In a general multi-parent DAG, chunks would need either replicated lineage keys or multi-path interval mappings, breaking contiguous single-run Z-ordering.
6. **Baseline Timing Nuances (`hnswlib` Python Callback, Single `ef=64`, `H4` Schema Alternative)**:
   - `hnswlib-M16` (`bench/systems.py:270`) invokes a Python `lambda label: bool(mask[label])` callback from C++ on every visited node, adding substantial pybind11 FFI overhead to its `131.52 ms` latency; attributing that latency solely to "deep iterative walks" overstates the native C++ cost of `hnswlib`'s graph search.
   - All graph systems are evaluated at a single operating point (`efConstruction=64, efSearch=64`); a recall-vs-evaluations Pareto sweep over `efSearch` would strengthen the comparison.
   - In `H4`, `pgvector` uses an inline `acl_allowed` boolean column on packed (`fillfactor=100`) heap pages; while this accurately captures write amplification for inline ACL metadata, a relational PostgreSQL baseline joining a separate `folders(folder_id, acl_allowed)` table would also avoid HNSW index writes (though at SQL join/filter cost).

### Minor Presentation Issues
7. **IEEEtran `\paragraph` Punctuation (`paper/prism_ann.tex:218,448,451,454`)**: Placing a trailing period inside `\paragraph{Title.}` causes IEEEtran to render `.:` (`a) Ancestor-Stitched Express Bridges (H-HNSW).:`).
8. **Double-Blind Anonymization**: Line 35 includes author identity (`Bhavyateja Potineni`) and cites `[19]` by name; acceptable for arXiv/technical reports, requires anonymization for double-blind conferences.
9. **Figure 2 Panel (a) Line Occlusion**: `Prism full`, `hnswlib`, and `Exact brute force` sit directly atop `y=100%` for $S \le 1\%$, making `Exact brute force` invisible in Panel (a).

---

## 4. Detailed Questions for Authors

1. How much of `prism-graph-only`'s `+22.25 pt` ($S=0.1\%$) and `+17.65 pt` ($r \le 0.5$) gain over `FAISS M=16` remains if `InitEntryPortals` is disabled (or if `FAISS M=16` and `ACORN-1` are given the same 4 authorized seeds from $B_\Phi$)?
2. Given that `prism-full` collapses to `24.55%` Recall@10 at $S=2\%$ (`r <= 0.5`) in `H3`, how should `N_flat^*` or `s_sparse_threshold` be coupled to *local* selectivity `r` rather than just global `S`?
3. When implemented in C++/SIMD (without Python `from_bool_mask` and `int8 -> int32` copies), at what exact $S$ does Mode 3 cross below `hnswlib` and `exact-brute-force`?

---

## 5. Independent Score & Recommendation

- **Overall Score**: **5.5 / 10** (*Borderline — Weak Accept as a Provenance-Verified Empirical Study / Major Revision before Top-Tier DB/Systems Submission*)
- **Confidence**: **5 / 5** (verified directly from compiled PDF, raw JSONL records, frozen modules, and engine adapters)
- **Rationale**:
  The paper's **reproducibility, engineering rigor, SpiceDB UBP contribution (Theorem 1 + H1v2/H4v2), and intellectual honesty** (plainly falsifying P2b/P3b and exposing graph-only limitations) are well above average and set a high methodological standard. However, three factors hold it back from a clear accept at a top venue (SIGMOD/VLDB/ICDE): (1) the core filtered-HNSW innovation (`M_bridge=4` ring-chord bridges) yields only `28%–53%` graph-only recall at $S \le 1\%$ and loses to `hnswlib`/`pgvector`, leaving practical low-$S$ recall reliant on exact flat scanning (Mode 3), which itself is unimplemented in native C++/SIMD and misses $S=2\%$ depleted queries (`24.55%` recall); (2) no ablation separates `InitEntryPortals` from express bridges; and (3) the opening sentence of §I contains unedited `(X)/(Y)/(Z)` template placeholders that must be fixed immediately.
