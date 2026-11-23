# Research Findings & Narrative Synthesis (`findings.md`)

> **Governing Protocols (`ADR-0004` + `ADR-0005` + `ADR-0006`):**
> All empirical findings below come from three strictly separated, deterministically recomputable raw-record campaigns totaling **`199,164` raw JSONL records**:
> 1. **Frozen Confirmatory Run (`v3-confirmatory-001`, commit `41868bb`)**: `FREEZE_v3.md` (`7/7` match), `169,810` raw records in `results/v3/raw/*.jsonl` -> `results/v3/summary.json` (`bench.recompute_v3 --check`).
> 2. **First-Round External Reviewer Audit (`v3.1-reviewer-audit-001`, commit `e39260a`)**: `FREEZE_v3_1.md` (`8/8` match), `22,533` raw records in `results/v3_1_audit/raw/v3_1_reviewer_audit.jsonl` -> `results/v3/reviewer_audit_v3_1.json` (`bench.recompute_v3_1 --check`).
> 3. **Second-Round External Reviewer Audit (`v3.2-reviewer-audit-001`, commit `a435bab`)**: `FREEZE_v3_1.md` (`8/8` match), `6,821` raw records in `results/v3_2_audit/raw/v3_2_reviewer_audit.jsonl` -> `results/v3/reviewer_audit_v3_2.json` (`bench.recompute_v3_2 --check`).

---

## 1. Multi-Corpus Real-Engine Confirmatory Setup (`v3-confirmatory-001`)
- **Corpus 1 (Primary)**: Full BEIR Quora (`522,931` real passages, `all-MiniLM-L6-v2` 384-d L2-normalized), strictly reserved held-out test query indices **`[500..9,984]`** (`9,485` queries; `0` corpus overlap, `0` overlap with Phase 17 dev queries `[0..499]`).
- **Corpus 2 (Cross-Domain Wikipedia)**: Official BEIR Natural Questions (`BeIR/nq`, first `250,000` Wikipedia passages, `all-MiniLM-L6-v2` 384-d), `3,452` strictly disjoint test queries (`0` ID/text overlap).
- **Live Native Engines**: Native SpiceDB `v1.57.1` on **both** `--datastore-engine memory` AND persistent `--datastore-engine postgres` (PostgreSQL `17.12`), PostgreSQL `17.12` + `pgvector 0.8.7` (`relaxed_order`, `EXPLAIN`-verified on BOTH corpora), `FAISS 1.16.0`, compiled upstream C++ `stanford-futuredata/ACORN` (`acorn-1` $\gamma=1$ AND `acorn-gamma` $\gamma=4, M_\beta=64$), `hnswlib 0.8.0` (`C++/Py-cb`), `pyroaring 1.2.0`, Accelerate BLAS `exact-brute-force`, and frozen native C++17 / ARM NEON Prism-ANN v3 (`bench/prism_ckernel.cpp` & `bench/prism_audit_kernel.cpp`).

---

## 2. Pre-Registered Confirmatory Findings (`P1a`–`P5`, **11/11 SUPPORTED**)

1. **H1v3 — Live Memory & Persistent PostgreSQL 17 SpiceDB (`P1a`, `P1b`, `P1c` — ALL SUPPORTED):**
   - `0/1,200` mismatches (`0/600` memory + `0/600` persistent PostgreSQL 17 SpiceDB); `100.0%` within Theorem 1 bound (median `76`, max `285` tokens).
   - Broad principals ($\ge 1,000$ docs, $n=271$): **Memory SpiceDB** `0.350 ms` vs. `79.14 ms` (**`225.9×`**, strict live `ReadRelationships` RPC `2.72 ms` = **`29.1×`**); **Persistent PostgreSQL 17 SpiceDB** `0.353 ms` vs. `98.30 ms` (`201.92 ms` P95) (**`278.2×`**, strict live RPC `3.49 ms` = **`28.2×`**).

2. **H2v3 — Multi-Corpus Random-Overlay Selectivity Sweep (`P2a`, `P2b`, `P2c` — ALL SUPPORTED):**
   - **Quora (`522,931`)**: `v3-geom-M8` (graph-only, C++, `+1.91%` RAM) reaches `66.60%` / `78.29%` / `85.99%` / `95.25%` (`0.32–0.64 ms`), beating `faiss-hnsw-M16` (`5.75%–77.51%`) by **`+49.15` to `+60.85` pts** at $S \le 1\%$, beating `v2-ring-chord-M4` (`46.06%–67.87%`) by **`+18.12` to `+21.88` pts**, and beating both `acorn-1` (`0.95%–31.66%`) and `acorn-gamma` ($\gamma=4$: `0.25%–87.69%`) at every $S$ using **`0.143×` (`7×` less)** extra level-0 RAM.
   - **BEIR NQ (`250,000`)**: `v3-geom-M8` reaches `75.57%` / `79.03%` / `84.51%` / `93.35%` (`0.27–0.58 ms`), again beating `FAISS M=16`, `v2-ring-chord-M4`, `acorn-1`, and `acorn-gamma` at every $S$.
   - **Native ARM NEON Mode 3 (`v3-full-guard-sq8`)**: **`100.00%` Recall@10** at $S \le 1\%$ on both corpora in **`0.09–0.11 ms` (Quora)** and **`0.05–0.08 ms` (NQ)** — beating BLAS `exact-brute-force` by **`4.5×` / `15.9×` / `30.8×` (Quora)** and **`3.2×` / `10.0×` / `18.9×` (NQ)**, and beating `hnswlib-M16` / `pgvector 0.8.7` by **`725×–2,430×`** at $S=0.1\%$.

3. **H3v3 — Multi-Corpus Cluster-Aligned Correlation & Local-Stall Guard (`P3a`, `P3b` — BOTH SUPPORTED):**
   - **`r <= 0.5` (`P3a`)**: `v3-geom-M8` beats `faiss-hnsw-M16` by **`+49.00 ± 3.57` pts** on Quora (`54.56%` vs `5.56%`) and **`+53.19 ± 2.57` pts** on NQ (`58.46%` vs `5.26%`). `v3-full-guard-sq8` escalates depleted queries on hop 1 (`667/728` Quora, `629/715` NQ), lifting Recall@10 to **`97.17%` (`0.35 ms` med / `1.56 ms` P99)** on Quora and **`96.42%` (`0.17 ms` med / `0.49 ms` P99)** on NQ (`131×–193×` faster than `hnswlib-M16`).
   - **`r >= 2.0` (`P3b`)**: Fast-path `ACORN-GLS` ($\tau_{\text{high}}=0.55$) cuts distance evaluations by **`3.82×` (`0.262×`)** on Quora (`749.8` vs `2,863.8`) and **`3.11×` (`0.322×`)** on NQ (`776.9` vs `2,416.1`) with Recall@10 within **`-0.99` pt** (Quora) and **`-0.93` pt** (NQ).

4. **H4v3 — Persistent PostgreSQL 17 SpiceDB Revocation (`P4a`, `P4b` — BOTH SUPPORTED):**
   - Persistent PostgreSQL 17 SpiceDB `DeleteRelationships` + mirror + UBP + `CRoaring`: **`67.28 ms` median, `0` vector writes** (`1,024` docs / `153,600` chunks, $n=5$) vs. PostgreSQL 17 + `pgvector 0.8.7` transactional `UPDATE`: **`179.4 s` (`179,390.6 ms`)** = **`2,666.2×` slower**.

5. **H5v3 — 4-Way `InitEntryPortals` Ablation (`P5` — SUPPORTED):**
   - Disabling portals completely on `H-HNSW v2` (`hhnsw-v2-geom-M8-noportal`) retains **`101.0%` / `102.3%` / `101.0%`** of `v3-geom-M8`'s recall gain over `FAISS M=16` across $S \le 1\%$ (`67.18%` / `79.59%` / `86.51%`), proving geometric intra-container/magnet bridges drive the gain.

---

## 3. First-Round External Reviewer Audit (`v3.1`, `R1`–`R5`, `22,533` Raw Records — **5/5 SUPPORTED**)

1. **`R1` (`PR1` SUPPORTED) — 10,000-Trial Property-Based UBP Fuzzing**:
   - Across `10,000` randomized single-parent hierarchy trials ($L \in [3, 6], b \in [3, 8], k_0 \in [1, 8], m \in [0, 25]$, overlapping ancestor/descendant grants, and deny-inside-grant chains), $\mathcal{P}_{\text{UBP}}$ achieved **`0` false positives, `0` false negatives (`100.0%` exact set equivalence)** and **`0` violations** of Theorem 1 (`max observed = 168 <= theoretical bound = 172`).
2. **`R2` (`PR2` SUPPORTED) — Ultra-Low Selectivity $S = 0.01\%$ ($N_{\text{cand}} \approx 52$) Stress Test**:
   - At $S = 0.01\%$, graph-only `v3-geom-M8` achieves **`73.73%` Recall@10** on BEIR Quora (`522,931`) and **`74.47%`** on BEIR NQ (`200,000`) (`+72.03` / `+69.57` pts over upstream C++ `acorn-1` `1.70%` / `4.90%`), while `v3-full-guard-sq8` achieves **`100.00%` Recall@10** in **`0.036 ms`** (`14.4×` faster than BLAS `exact-brute-force` `0.520 ms`, `0` unauthorized leaks).
3. **`R3` (`PR3` SUPPORTED) — 2×2×2 Mode-3 Component Isolation (`64 MB` Cache-Thrashing Eviction Sweep vs. Warm Cache)**:
   - At $S = 1.0\%$ ($N_{\text{cand}} = 5,229$) under a `64 MB` cache-thrashing eviction sweep before each query, `C8` (`Z-Order + SQ8 + ARM NEON vdotq_s32 + M=64 FP32 rerank`, `0.0628 ms`) achieves a **`23.62×` total speedup** over `C1` (`Scattered + FP32 + Scalar`, `1.4828 ms`), decomposing multiplicatively into **`2.37×` Z-order contiguity** $\times$ **`2.86×` `SQ8` bandwidth reduction** $\times$ **`3.49×` ARM NEON SIMD**. Under warm cache, total speedup is **`14.12×`** (`0.0445 ms` vs. `0.6279 ms`).
4. **`R4` (`PR4` SUPPORTED) — Revocation Scaling ($10^3 \to 1.05 \times 10^6$ Chunks) & 16-Thread `ZedToken` Concurrency**:
   - Persistent PostgreSQL 17 SpiceDB revocation latency remains flat (**`64.61–71.09 ms`**, `0` vector writes) across $10^3 \to 1.05 \times 10^6$ revoked chunks; across **`36,881` concurrent 16-thread queries** (`18,469` pre-$\zeta_2$ + `18,412` post-$\zeta_2$), atomic `ZedToken` ($\zeta_{\text{rev}}$) snapshot swap (`0.123 ms`) produces **`0/18,412` post-revocation leaks** and **`0` torn reads**.
5. **`R5` (`PR5` SUPPORTED) — Dynamic Stream Ingestion (`50,000` Vectors in `5 × 10k` Batches) & Background Z-Order Compaction**:
   - Appending `50,000` vectors into the mutable delta buffer costs **`5.33–6.21 µs/vector`**; dual-read (`Z-Order CSR + mutable delta scan`) adds **`0.068–0.219 ms`** search overhead while maintaining **`100.00%` Recall@10**; background C++ CSR Z-order remap completes in **`55.66–63.48 ms`** (`127.60–145.67 ms` including rebuild) and restores pure contiguous scan latency (**`0.072 ms`**).

---

## 4. Second-Round Research Audit (`v3.2`, `R6`–`R8`, `6,821` Raw Records — Theory Split, Two-Track Fairness & 5-Level Recall Taxonomy)

1. **`R6` (`PR6` SUPPORTED) — Multi-Parent Acyclic DAG Fuzzing (`5,000` Trials) & Theorem 1 / Theorem 2 Formal Split**:
   - Across `5,000` randomized multi-parent Zanzibar DAGs ($p_{\text{multi}} \in \{0.15, 0.30, 0.50\}$, mean `1,170.0` secondary parent edges/DAG, diamond inheritance + conflicting `GRANT`/`DENY` paths under **Deny-Dominates-Grant** precedence), $\mathcal{P}_{\text{UBP}}$ achieved **`0/5,000` set-equivalence mismatches (`0` false positives, `0` false negatives)**, validating **Theorem 2**.
   - As predicted by our DAG path-multiplicity analysis ($|T_{\text{UBP}}^+(u)| \le k_0 + m \cdot \bar{p}_{\text{dag}}(b-1)L$), **`243/5,000` (`4.86%`)** multi-parent DAG trials exceeded the single-parent tree bound $k_0 + m(b-1)L$ (`max observed = 135` vs. `tree bound = 122`), empirically confirming why **Theorem 1** (Single-Parent Tree Cardinality Bound) and **Theorem 2** (Multi-Parent DAG Exact Set Equivalence) must be formally separated.
2. **`R7` (`PR7` FALSIFIED on fragmented-$L_5$ sub-criterion) — Two-Track Fair Baseline Benchmark & Fragmented-$L_5$ Stress Test**:
   - **Track 1 (Pre-Compiled Filter Bitmaps, Pure Index/Traversal Latency) vs. Track 2 (End-to-End including Live PostgreSQL 17 SpiceDB Authorization)**: Under hierarchical grants ($S \in \{0.01\%, 0.1\%, 0.5\%, 1.0\%, 5.0\%\}$), `v3-full-guard-sq8` (`0.0363–0.4527 ms` Track 1; `0.3892–0.8162 ms` Track 2) outperforms `exact-brute-force` (`0.5238–1.2784 ms` Track 1; `98.82–99.58 ms` Track 2 with `LookupResources`) by **`2.8–14.4×` on Track 1** and **`121–254×` on Track 2**.
   - **Transparent Boundary Condition (`PR7` Falsification)**: When a principal holds only `~50` scattered leaf-level ($L_5$) grants with zero container coalescing, Z-order contiguity degrades into ~50 disjoint micro-ranges and the Z-order layout speedup over scattered memory drops from `2.37×` to **`1.00–1.08×`** (`< 1.25×` pre-registered threshold), while `SQ8 + ARM NEON` still provides ~`6–8×` speedup over scattered FP32 scalar scan.
3. **`R8` (`PR8` FALSIFIED on strict $\ge 99.0\%$ empirical recall cutoff at $S \ge 0.1\%$) — 5-Level Taxonomy of Exact vs. Empirical Recall@10**:
   - **Level 1 (Mathematical Guarantee)**: Pure FP32 Mode 3 (`v3-full-guard-f32`, `0.0035–0.3289 ms`) and `SQ8` when $N_{\text{cand}} \le M_{\text{rerank}}$ ($S = 0.01\%, N_{\text{cand}}=52 \le 64$: **`100.00%` guaranteed exact**).
   - **Level 2 (`SQ8 + M_rerank` vs. Pure FP32 Mode 3)**: At $S \in \{0.1\%, 0.5\%, 1.0\%\}$, `SQ8 + M_rerank=64` achieves **`98.17%–98.70%`** recall against pure FP32 Mode 3 (`98.70%–99.23%` at $M_{\text{rerank}}=128$), slightly below the strict `99.0%` pre-registered threshold (`PR8` falsified).
   - **Level 3 (`v3-full-guard-sq8` vs. Global `exact-brute-force` across all routed modes)**: When $N_{\text{cand}} > N_{\text{flat}}^* = 500$ ($S \ge 0.1\%$ on 523k vectors), queries route to Mode 2 (`H-HNSW` + Local-Stall Guard) unless stalled, yielding **`82.13%–94.40%`** against unconstrained `exact-brute-force` (`100.00%` inside the `v3` confirmatory protocol where $N_{\text{flat}}^* = 7,500$ covers $S \le 1.0\%$).
