# Research Findings & Narrative Synthesis (`findings.md`)

> **Governing Protocols (`ADR-0004` + `ADR-0005` + `ADR-0006`):**
> All empirical findings below come from four strictly separated, deterministically recomputable raw-record campaigns totaling **`207,685` v3-series JSONL records** (plus `62,410` archived `v2` records):
> 1. **Frozen Confirmatory Run (`v3-confirmatory-001`, commit `41868bb`)**: `FREEZE_v3.md` (`7/7` match), `169,810` raw records -> `results/v3/summary.json` (`bench.recompute_v3 --check`).
> 2. **First-Round External Reviewer Audit (`v3.1-reviewer-audit-001`, commit `e39260a`)**: `FREEZE_v3_1.md` (`8/8` match), `22,533` raw records -> `results/v3/reviewer_audit_v3_1.json` (`bench.recompute_v3_1 --check`).
> 3. **Second-Round External Reviewer Audit (`v3.2-reviewer-audit-001`, commit `a435bab`)**: `FREEZE_v3_1.md` (`8/8` match), `6,821` raw records -> `results/v3/reviewer_audit_v3_2.json` (`bench.recompute_v3_2 --check`).
> 4. **Third-Round Dynamic-DAG & E2E Audit (`v3.3-reviewer-audit-001`, commit `3c79298`)**: `FREEZE_v3_3.md` (`9/9` match), `8,521` raw records -> `results/v3/reviewer_audit_v3_3.json` (`bench.recompute_v3_3 --check`).

---

## 1. Multi-Corpus Real-Engine Confirmatory Setup (`v3-confirmatory-001`)
- **Corpus 1 (Primary)**: Full BEIR Quora (`522,931` real passages, `all-MiniLM-L6-v2` 384-d L2-normalized), strictly reserved held-out test query indices **`[500..9,984]`** (`9,485` queries; `0` corpus overlap, `0` overlap with Phase 17 dev queries `[0..499]`).
- **Corpus 2 (Cross-Domain Wikipedia)**: Official BEIR Natural Questions (`BeIR/nq`, first `250,000` Wikipedia passages, `all-MiniLM-L6-v2` 384-d), `3,452` strictly disjoint test queries (`0` ID/text overlap).
- **Live Native Engines**: Native SpiceDB `v1.57.1` (`memory` & persistent PostgreSQL `17.12`), PostgreSQL `17.12` + `pgvector 0.8.7`, `FAISS 1.16.0`, compiled upstream C++ `stanford-futuredata/ACORN` (`acorn-1` $\gamma=1$ & `acorn-gamma` $\gamma=4, M_\beta=64$), `hnswlib 0.8.0` (`C++/Py-cb`), `pyroaring 1.2.0`, Accelerate BLAS `exact-brute-force`, and frozen native C++17 / ARM NEON Prism-ANN v3 (`bench/prism_ckernel.cpp` & `bench/prism_audit_kernel.cpp`) + versioned dynamic DAG module (`src/modules/prism_ann_v3/dynamic_dag_ubp.py`).

---

## 2. Pre-Registered Confirmatory Findings (`P1a`–`P5`, **11/11 SUPPORTED**)

1. **H1v3 — Live Memory & Persistent PostgreSQL 17 SpiceDB (`P1a`, `P1b`, `P1c` — ALL SUPPORTED):**
   - `0/1,200` mismatches (`0/600` memory + `0/600` persistent PostgreSQL 17 SpiceDB); `100.0%` within Theorem 1 bound (median `76`, max `285` tokens).
   - Broad principals ($\ge 1,000$ docs, $n=271$): **Memory SpiceDB** `0.350 ms` vs. `79.14 ms` (**`225.9×`**, live `ReadRelationships` RPC `2.72 ms` = **`29.1×`**); **Persistent PostgreSQL 17 SpiceDB** `0.353 ms` vs. `98.30 ms` (`201.92 ms` P95) (**`278.2×`**, live RPC `3.49 ms` = **`28.2×`**).
2. **H2v3 — Multi-Corpus Random-Overlay Selectivity Sweep (`P2a`, `P2b`, `P2c` — ALL SUPPORTED):**
   - **Quora (`522,931`)**: `v3-geom-M8` (graph-only, C++, `+1.91%` graph RAM) hits `66.60%` / `78.29%` / `85.99%` / `95.25%` (`0.32–0.64 ms`), beating `faiss-hnsw-M16` (`5.75%–77.51%`) by **`+49.15` to `+60.85` pts** at $S \le 1\%$, beating `v2-ring-chord-M4` by **`+18.12` to `+21.88` pts**, and beating `acorn-1` & `acorn-gamma` at every $S$ using `0.143×` extra L0 RAM.
   - **BEIR NQ (`250,000`)**: `v3-geom-M8` hits `75.57%` / `79.03%` / `84.51%` / `93.35%` (`0.27–0.58 ms`), beating `FAISS`, `v2-ring-chord-M4`, `acorn-1`, and `acorn-gamma` at every $S$.
   - **Native ARM NEON Mode 3 (`v3-full-guard-sq8`)**: **`100.00%` empirical Recall@10** at $S \le 1\%$ on both corpora in **`0.09–0.11 ms` (Quora)** and **`0.05–0.08 ms` (NQ)** (mathematically guaranteed when $N_{\text{cand}} \le 64$ or via pure `FP32`).
3. **H3v3 — Correlation & Local-Stall Guard (`P3a`, `P3b` — BOTH SUPPORTED):**
   - **`r <= 0.5` (`P3a`)**: `v3-full-guard-sq8` lifts Recall@10 to **`97.17%` (`0.35 ms` med / `1.56 ms` P99)** on Quora and **`96.42%` (`0.17 ms` med / `0.49 ms` P99)** on NQ.
   - **`r >= 2.0` (`P3b`)**: Fast-path `ACORN-GLS` ($\tau_{\text{high}}=0.55$) cuts distance evaluations by **`3.82×` (Quora)** and **`3.11×` (NQ)** within `-0.99` / `-0.93` pt R@10.
4. **H4v3 — Persistent PG17 SpiceDB Revocation (`P4a`, `P4b` — BOTH SUPPORTED):** `67.28 ms` median (`0` vector writes) vs. PG17 + `pgvector 0.8.7` `UPDATE` `179.4 s` (**`2,666.2×` faster**).
5. **H5v3 — 4-Way `InitEntryPortals` Ablation (`P5` — SUPPORTED):** Zero-portal `H-HNSW v2` retains **`101.0% / 102.3% / 101.0%`** of recall lift over `FAISS M=16` across $S \le 1\%$.

---

## 3. First-Round External Reviewer Audit (`v3.1`, `R1`–`R5`, `22,533` Raw Records — **5/5 SUPPORTED**)

1. **`R1` (`PR1` SUPPORTED) — 10,000-Hierarchy Fuzzing:** `5,000` standard ReBAC trees + `5,000` alternating `GRANT<->DENY` override trees (`L <= 5`) -> **`0 / 10,000` leaf mismatches**, `100.0%` Theorem 1 bound satisfaction (`max 249` std, `164` alt).
2. **`R2` (`PR2` SUPPORTED) — Ultra-Low Selectivity $S = 0.01\%$ ($S_{\text{act}} \approx 0.0091\%$):** `v3-geom-M8` hits **`85.73%` (`0.538 ms` Quora)** and **`92.27%` (`0.273 ms` NQ)** vs. `acorn-1` `0.33%` / `0.40%` (`faiss-hnsw-M16` `0.87%` / `0.60%`); `v3-full-guard-sq8` hits **`100.00%`** in **`0.049 ms` (Quora)** and **`0.032 ms` (NQ)** (`0 / 1,200` leaks).
3. **`R3` (`PR3` SUPPORTED) — 6-Way Mode-3 Component Isolation (`64 MB` Cold-LLC Sweep vs. Warm Cache at $S=1.0\%$):** Cold LLC achieves **`29.40×` total speedup** (`0.0976 ms` vs. `2.8695 ms` scattered scalar FP32), decomposing into **`7.35×` Z-order contiguity** (`FP32` NEON), **`2.85×` `SQ8` compression** (on scalar), and **`7.46×` ARM NEON** over cold scalar `SQ8` (`0.7281 ms`). Warm cache achieves **`34.18×`** (`0.0812 ms` vs. `2.7758 ms`).
4. **`R4` (`PR4` SUPPORTED) — PG17 Subtree Scaling & Concurrent Local Snapshot-Swap Race:** PG17 SpiceDB single-edge deletions from `128 -> 490,419` chunks stay flat at **`0.74–1.66 ms` (`0` vector writes)**. Across **`11,244` concurrent 4-thread C++ queries** (`5,205` pre-swap `zeta=1` + `6,039` post-swap `zeta=2`; `4` crossing cutoff), local atomic swap (`0.091 ms`, PG17 commit `6.82 ms`) yields **`0 / 6,039` post-swap leaks** (note: `R4b` used local integer snapshot versions; real opaque SpiceDB `ZedToken` concurrency is tested in `R11`).
5. **`R5` (`PR5` SUPPORTED) — Dynamic Stream Ingestion & Z-Order Compaction:** Appending `+1k..+25k` vectors onto `500k` Quora base vectors takes **`5.30–23.93 µs/vector`**, background lexicographic compaction takes **`1.30–2.36 s`** (`1,303.3–2,357.2 ms`), and C++ CSR ID remap takes **`116.30–121.61 ms`**.

---

## 4. Second-Round Research Audit (`v3.2`, `R6`–`R8`, `6,821` Raw Records — Methodological Boundaries)

1. **`R6` (`PR6` SUPPORTED) — Multi-Parent DAG Fuzzing:** `5,000` permission/deny/revocation trials across **`36` generated multi-parent DAG topologies** (`3` initial + `33` replacements across `(4,5),(6,4),(8,4)`, `min 672` / mean `1,170.0` secondary edges) -> **`0 / 5,000` mismatches** (`median 20.0`, `max 387` tokens). (Supplemented in `R9a` by `1,000` genuinely independent DAGs with post-index structural mutations.)
2. **`R7` (`PR7` FALSIFIED on `<=0.35 ms` / `>=100x` fragmented-L5 thresholds; `0/1,500` leaks) — Track 1 Pure C++ vs. Modeled Track 2:** Track 1 excludes filter compilation; Track 2 is a **modeled composite sum** (`H1v3` broad-principal constants + `R7` filter compile + Track-1 C++ search; `SQ8` query quantization outside Track 1). On fragmented depth-5 Quora, `v3-geom-M8` hits `87.4% / 79.2% / 71.4% / 73.6% / 93.0%` vs. `acorn-1` (`0.2%–31.2%`) and in-repo `racorn-1-fallback` C++ proxy (`6.0%–89.0%`). `v3-full-guard-f32` (`0 B/n` vec RAM, `0.0206–0.4527 ms` Track 1) and `-sq8` (`0.0380–0.4344 ms` Track 1) hit `100.0%` at $S \le 1\%$ (`24.12×–28.07×` PG17 / `80.61×–163.75×` mirror; `0.4344 ms > 0.35 ms` at $S=1.0\%$ and `82.19x < 100x` caused honest `PR7` falsification).
3. **`R8` (`PR8` FALSIFIED on `<=0.25 ms` exact-FP32 cutoff at fragmented $S=1.0\%$) — 5-Level Recall Audit:** `M_rerank=64` achieves **`100.0%` mathematical guarantee coverage** at $S=0.01\%$ (`n_cand <= 48`); `SQ8`+`M_rerank>=32` (`32, 64, 128`) hits **`100.0%` empirical R@10** across all $S \in [0.01\%, 1.0\%]$ (`>= 99.8%` criterion met, whereas `M=10` drops to `97.0%–98.0%`); exact `FP32` hits `100.0%` in `0.0035 / 0.0235 / 0.1964 / 0.3289 ms` (`0.3289 ms > 0.25 ms` at fragmented $S=1.0\%$), motivating adaptive exact-`FP32` ($S \le 0.1\%$) vs. quantized-`SQ8` ($S \ge 0.5\%$) Mode-3 dispatch.

---

## 5. Third-Round Dynamic-DAG & Directly Timed E2E Audit (`v3.3`, `R9a`–`R11`, `8,521` Raw Records)

1. **`R9a` (`PR9a` SUPPORTED) — 1,000 Independent Multi-Parent DAGs + Dynamic Structural Mutations:** Across `1,000` freshly constructed multi-parent DAGs (`min 105`, mean `486.0` secondary edges, `0` graph reuse), all `5,000` post-index structural mutations (`M1` post-index `add_hierarchy_edge` to denied parent, `M2` multi-parent edge unlink keeping surviving path, `M3` final path unlink, `M4` deny removal, `M5` revoke + re-grant) yield **`0 / 5,000` FP, `0` FN, and `0` search-hit leaks** via `DynamicMultiParentAuthGraph` + `VersionedLineageCorpus`.
2. **`R9b` (`PR9b` SUPPORTED) — Live SpiceDB v1.57.1 10-Scenario Matrix:** Against real native SpiceDB `v1.57.1`, `DynamicPrismANNIndex` achieves **`0 / 10` mask mismatches, `0 / 10` search mismatches, and `0` `CheckPermission` mismatches** across surviving-path unlinks, final-path unlinks, direct child grants + denied parent add/remove, post-index denied parent additions, deny removals, grant/re-grants, and `at_exact_snapshot` historical `ZedToken` reads.
3. **`R11` (`PR11` SUPPORTED) — 8-Thread Concurrent Live SpiceDB Opaque `ZedToken` Concurrency:** Across `1,760` concurrent reads (`427` pre-revocation `at_exact_snapshot(zt_pre)` + `1,333` post-revocation `at_least_as_fresh(zt_post)`), live `CheckPermission` (`1.437 ms` med RPC) + `DynamicPrismANNIndex.search()` (`0.111 ms` med) achieve **`0 / 1,760` oracle mismatches, `0 / 1,333` post-revocation leaks, and `0` stale-snapshot errors**.
4. **`R10` (`PR10` FALSIFIED on `>=10x` live-RPC cutoff at $S=0.01\%$; `0 / 1,750` total leaks) — Directly Timed E2E Requests & `efSearch` Sweep:** Using an unbroken single timer wrapping live SpiceDB auth + filter compile + **in-timer `SQ8` query quantization** + C++ search/rerank on Quora `523k`: at $S=0.01\%$ (`3`-leaf `LookupResources = 10.40 ms`), live `ReadRelationships+UBP` takes `1.61–1.68 ms` (`6.20×–6.47×`, `< 10×` -> `PR10` falsified); at $S \in \{0.1\%, 0.5\%, 1.0\%, 5.0\%\}$, live-RPC UBP beats `LookupResources+FAISS` by **`11.39×–89.10×`**, while mirror E2E achieves **`197.39×–522.40×`** (`0.0422 ms` `FP32` vs `0.0527 ms` `SQ8` at $S=0.01\%$). At `S=0.5%`, `v3-geom-M8` (`ef=32..512`) reaches `98.0%` R@10 in `1.857 ms` vs. `FAISS` `69.6%` (`3.350 ms`) and `ACORN-1` `67.2%` (`7.730 ms`).
