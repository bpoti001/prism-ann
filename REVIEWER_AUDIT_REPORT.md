# Prism-ANN External Reviewer Audit & Hardening Report (`v3.1`)

**Repository:** [`bpoti001/prism-ann`](https://github.com/bpoti001/prism-ann)  
**Paper PDF:** [`prism_ann_paper.pdf`](prism_ann_paper.pdf)  
**Confirmatory Raw Data (`169,810` queries):** [`results/v3/raw/`](results/v3/raw) & [`results/v3/summary.json`](results/v3/summary.json)  
**Reviewer Audit Raw Data & Summary:** [`results/v3_1_audit/raw/v3_1_reviewer_audit.jsonl`](results/v3_1_audit/raw/v3_1_reviewer_audit.jsonl) & [`results/v3/reviewer_audit_v3_1.json`](results/v3/reviewer_audit_v3_1.json)

This document answers every technical challenge raised in the external systems review (`§6.1–§6.6`, `§8 Experiments`, and `§10 Evidence Separation`), separating **(A) Formal Proofs**, **(B) Frozen Confirmatory Runs (`v3-confirmatory-001`)**, and **(C) Supplementary Reviewer-Audit Experiments (`v3.1`, `R1`–`R5`)**.

---

## 1. Evidence & Reproducibility Map (Separating Implementation, Empirical Data & Theory)

| Layer | Where to Verify in Repo | Audit Status |
| :--- | :--- | :--- |
| **Algorithmic Proofs & Theorems** | [`paper/prism_ann.tex`](paper/prism_ann.tex) (`§3`, Theorem 1, Corollary 1, Propositions 2–4) | Theorem 1 proves $\|T_{\text{UBP}}^+(u)\| \le k_0 + m(b-1)L$ and exact equivalence `0 FP / 0 FN`. |
| **Native C++17 / ARM NEON Kernels** | [`bench/prism_ckernel.cpp`](bench/prism_ckernel.cpp) (frozen) & [`bench/prism_audit_kernel.cpp`](bench/prism_audit_kernel.cpp) (6-way isolation + LLC flush) | Frozen SHA-256 `7/7` match in [`FREEZE_v3.md`](FREEZE_v3.md). |
| **Frozen Confirmatory Run (`169,810` records)** | [`bench/harness_v3.py`](bench/harness_v3.py), [`results/v3/raw/`](results/v3/raw), [`bench/recompute_v3.py`](bench/recompute_v3.py) | `recompute_v3 --check` exits `0` (`MATCH`); `0` leaks across all `169,810` records; `11/11` predictions supported. |
| **New Reviewer-Audit Suite (`R1`–`R5`)** | [`bench/run_reviewer_audit_v3_1.py`](bench/run_reviewer_audit_v3_1.py), [`results/v3/reviewer_audit_v3_1.json`](results/v3/reviewer_audit_v3_1.json) | `1,360` audit records verifying §6.1–§6.5 directly on full BEIR Quora (`522,931`), BEIR NQ (`250,000`), and live PG17 SpiceDB. |
| **Unit & Parity Test Suite** | [`tests/test_prism_ann.py`](tests/test_prism_ann.py), [`tests/test_prism_v3_kernel.py`](tests/test_prism_v3_kernel.py), [`tests/test_bench_provenance.py`](tests/test_bench_provenance.py) | `19/19` `pytest` passing + C++ vs. Python exact bit parity checks. |
| **Anti-Hallucination & Provenance Guard** | [`verify_prism_hallucinations.py`](verify_prism_hallucinations.py) | Programmatically asserts zero numeric drift between raw JSONLs, `summary.json`, and `paper/prism_ann.tex`. |

---

## 2. Five Newly Executed Reviewer-Audit Experiments (`v3.1`)

### `R1` — 10,000-Hierarchy Property-Based & Alternating `GRANT/DENY` Fuzzing (§6.1)
*Challenge:* A 1,200-principal test does not stress arbitrary hierarchy depths, fanouts, or alternating `Root Grant -> L1 Deny -> L2 Re-Grant -> L3 Sub-Deny -> Leaf Override` rules.  
*Method (`bench/run_reviewer_audit_v3_1.py`):* Tested `10,000` randomized policies across `(b=8, L=4)`, `(b=4, L=5)`, and `(b=6, L=4)`:
1. **`5,000` Standard ReBAC (`but not` + revoked subtrees)**: `ZanzibarAuthGraph.upward_boundary_prune()` vs. exhaustive `lookup_resources_leaf()` oracle.
2. **`5,000` Generalized Alternating-Precedence Hierarchies** (deeper override wins across up to depth `L=5`): `generalized_alternating_ubp()` vs. exhaustive per-leaf ancestor-path oracle.

| Suite | Trials | Topologies | Set Mismatches (vs. Leaf Oracle) | Bound Satisfaction | `\|T_UBP+\|` Median / Max |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Standard ReBAC (`but not` + Revoked Edges) | `5,000` | `(8,4), (4,5), (6,4)` | **`0 / 5,000`** (`0` FP, `0` FN) | **`100.0%`** | `3.0` / `249` |
| Alternating Overrides (`GRANT↔DENY` up to `L=5`) | `5,000` | `(8,4), (4,5), (6,4)` | **`0 / 5,000`** (`0` FP, `0` FN) | **`100.0%`** | `48.0` / `164` |
| **Combined Fuzzing Total** | **`10,000`** | Depth `4–5` | **`0 / 10,000`** | **`100.0%`** | — |

---

### `R2` — Ultra-Low Selectivity `S = 0.01%` on Quora (`522,931`) & BEIR NQ (`250,000`) (§6.2 & Exp 2)
*Challenge:* Measure whether Prism-ANN holds up when permission selectivity drops below `0.1%` down to **`0.01%`** (~48 vectors on Quora, ~23 vectors on NQ, depth `L=5, b=8` -> `32,768` docs, 3 seeds × 50 queries = `150` queries/corpus).

| System | BEIR Quora (`S_act = 0.00917%`) R@10 / Med / P95 | BEIR NQ (`S_act = 0.00912%`) R@10 / Med / P95 |
| :--- | :---: | :---: |
| `faiss-hnsw-M16` | `0.87%` / `4.243 ms` / `5.539 ms` | `0.60%` / `0.545 ms` / `0.867 ms` |
| `acorn-1` (upstream C++) | `0.27%` / `0.969 ms` / `1.160 ms` | `0.40%` / `0.513 ms` / `1.059 ms` |
| `v3-geom-M8` (graph-only bridges) | **`85.73%`** / `0.589 ms` / `2.609 ms` | **`92.27%`** / `0.253 ms` / `0.368 ms` |
| **`v3-full-guard-sq8` (complete)** | **`100.00%`** / **`0.056 ms`** / `0.099 ms` | **`100.00%`** / **`0.032 ms`** / `0.046 ms` |

At `S ≈ 0.01%`, standard `FAISS` and `ACORN-1` drop below `1%` Recall@10, while graph-only geometric bridges sustain `85.7%–92.3%` and complete `v3-full-guard-sq8` delivers **`100.00%` Recall@10 in `0.032–0.056 ms`**.

---

### `R3` — 6-Way Mode-3 Component Isolation (Z-Order vs. SQ8 vs. ARM NEON vs. Portable Scalar; Warm & Cold LLC) (§6.3, §6.4, Exp 3, Exp 5)
*Challenge:* Isolate how much Mode-3 performance comes from (1) contiguous Z-ordering + `CRoaring` vs. scattered vector IDs, (2) `SQ8` quantization vs. `FP32`, and (3) ARM NEON SIMD vs. portable C++ scalar loops (compiled with `#pragma clang loop vectorize(disable)`), under both **Warm Cache** and **Cold Cache** (flushing L1/L2/SLC via a `64 MB` volatile stride-64 sweep before every single query on full `N=522,931` Quora).

**Cold-Cache (`64 MB` LLC Flush Before Every Query) Median Latency & 100.0% R@10 on Full Quora (`522,931 × 384-d`):**

| C++ Kernel Variant (`100.0%` R@10 on all variants) | `S = 0.01%` | `S = 0.1%` | `S = 0.5%` | `S = 1.0%` |
| :--- | :---: | :---: | :---: | :---: |
| `1. scattered_f32_scalar` (non-Z-ordered, no SIMD) | `0.0996 ms` | `0.3324 ms` | `1.5024 ms` | `2.9363 ms` |
| `2. scattered_f32_neon` (non-Z-ordered, NEON FP32) | `0.0659 ms` | `0.2161 ms` | `0.7779 ms` | `1.4570 ms` |
| `3. zorder_f32_scalar` (contiguous Z-order, scalar FP32) | `0.0771 ms` | `0.2260 ms` | `1.0175 ms` | `2.0685 ms` |
| `4. zorder_f32_neon` (contiguous Z-order, NEON FP32) | `0.0320 ms` | **`0.0429 ms`** | `0.1064 ms` | `0.1894 ms` |
| `5. zorder_sq8_scalar` (portable C++ scalar SQ8 + FP32 rerank) | `0.0780 ms` | `0.1275 ms` | `0.3923 ms` | **`0.7339 ms`** |
| `6. zorder_sq8_neon` (contiguous Z-order + ARM NEON `vdotq_s32`) | `0.0394 ms` | `0.0475 ms` | **`0.0725 ms`** | **`0.1022 ms`** |

**Cold-Cache Multiplicative Speedup Attribution (`S = 0.1% → 1.0%`):**
- **Contiguous Z-Order + CRoaring (`scattered → zorder` on `FP32 NEON`):** **`5.04× → 7.69×`** (`7.31×` at `0.5%`) — proves Z-ordering eliminates pointer/TLB scatter overhead once SIMD compute stops hiding memory stalls.
- **`SQ8` Bandwidth Reduction (`zorder FP32 scalar → zorder SQ8 scalar`):** **`1.77× → 2.82×`**.
- **ARM NEON SIMD vs. Portable Scalar (`zorder SQ8 scalar → zorder SQ8 NEON`):** **`2.68× → 7.18×`**.
- **Hardware Portability Finding:** Even on a generic CPU with **zero SIMD instructions** (`5_zorder_sq8_scalar`), Z-ordered contiguous `CRoaring` + `SQ8` achieves **`100.0%` Recall@10 in `0.128 ms` (`S=0.1%`) to `0.734 ms` (`S=1.0%`)** under cold cache — still sub-millisecond! Combining all three yields **`28.73×` cold (`33.64×` warm)** speedup at `S=1.0%` over `scattered_f32_scalar`.

---

### `R4` — Subtree Revocation Scaling (`128 → 490,419` Chunks) & Concurrent `ZedToken` Consistency (§6.5 & Exp 4)
*Challenge:* Verify (a) revocation latency across subtree sizes from ~100 to ~500k chunks, and (b) security consistency when concurrent queries are in flight while a folder revocation commits.

**Part A — Persistent PostgreSQL 17 SpiceDB Subtree Scaling (`0` vector writes throughout):**
| Docs Revoked | Chunks Revoked | Graph Edges Deleted | Median Latency (Min–Max, `n=5`) | Vector Writes |
| :---: | :---: | :---: | :---: | :---: |
| `1` | `128` | `1` | `1.65 ms` (`1.48–3.31`) | `0` |
| `8` | `1,024` | `1` | `0.96 ms` (`0.85–1.34`) | `0` |
| `64` | `8,192` | `1` | `2.89 ms` (`1.24–16.95`) | `0` |
| `512` | `65,536` | `1` | `0.94 ms` (`0.94–1.73`) | `0` |
| `1,024` | `131,072` | `2` | `1.59 ms` (`1.54–1.78`) | `0` |
| `2,048` | `262,144` | `4` | `3.56 ms` (`3.20–4.23`) | `0` |
| `3,840` | `490,419` | `11` | `8.34 ms` (`7.50–9.34`) | `0` |

*(Note: Hot persistent PostgreSQL `DeleteRelationships` + UBP + CRoaring takes `0.9–8.3 ms`; in `H4v3`, the `67.28 ms` figure reflects `DeleteRelationships` over a `128`-folder subtree immediately sharing host disk/IPC state with loaded `pgvector` HNSW tables — both **~2,666× to >100,000× faster** than `pgvector`'s `179.4 s` inline `UPDATE`.)*

**Part B — Concurrent 4-Thread In-Flight Query Race + Live Postgres SpiceDB Revocation (`131,072` chunks revoked mid-flight):**
- **Total concurrent C++ H-HNSW queries executed across 4 reader threads:** **`15,563`** (`6,647` on `zeta=1` pre-revocation, `8,916` on `zeta=2` post-revocation).
- **In-flight queries actively crossing the revocation swap cutoff:** **`4`** (all completed cleanly under immutable `zeta=1` snapshot isolation without tearing or crashes).
- **Queries started after atomic swap using old `zeta=1`:** **`0`**.
- **Chunks leaked from revoked subtree on any `zeta >= 2` query:** **`0 / 8,916`** queries.
- **Persistent SpiceDB commit time:** **`60.73 ms`** · **Atomic UBP + CRoaring snapshot compile & swap window:** **`0.273 ms` (`273 µs`)**.

---

### `R5` — Dynamic Document Ingestion & Background Z-Order Compaction Maintenance (§6.3)
*Challenge:* Measure online insert latency and Z-order maintenance / HNSW remapping cost when new documents arrive after initial index build (`base_N = 500,000` Quora vectors + incremental batches).

| New Batch Size | Total Vectors | Online Delta-Buffer Append (`µs/vec`) | Async Background Z-Order Compaction | C++ HNSW CSR ID Remap (`500k` nodes) |
| :---: | :---: | :---: | :---: | :---: |
| `+1,000` | `501,000` | `23.82 ms` (`23.8 µs/vec`) | `3,048.7 ms` | `111.5 ms` |
| `+5,000` | `505,000` | `64.59 ms` (`12.9 µs/vec`) | `2,503.6 ms` | `107.9 ms` |
| `+10,000` | `510,000` | `93.95 ms` (`9.4 µs/vec`) | `2,102.9 ms` | `103.0 ms` |
| `+25,000` | `525,000` | `130.27 ms` (`5.2 µs/vec`) | `2,599.3 ms` | `138.3 ms` |

Online chunk ingestion commits to an append-only delta buffer + incremental `CRoaring` delta bitmap in **`5.2–23.8 µs/vector`** without blocking readers, while full background lexicographic compaction + `SQ8` buffer build + C++ HNSW CSR ID remapping completes off-critical-path in **`2.1–3.0 s`** (`~103–138 ms` for the C++ graph remapper) with atomic pointer swap.

---

## 3. Reconciliation of Reviewer Table (§6.6)

| Claim Reviewed | Exact Reconciliation & Source Reference |
| :--- | :--- |
| **`67.28 ms` vs `179.4 s` vs `138.2 s`** | `179.4 s` (`179,390.6 ms`) is the final `n=5` median `pgvector UPDATE` over `522,931` rows (`H4v3`, [`v3-confirmatory-001__H4_postgres.jsonl`](results/v3/raw/v3-confirmatory-001__H4_postgres.jsonl)). `138.2 s` appeared in a mid-animation frame (`77%` progress, `118,314 / 153,600` rows) in [`Scene7Revocation.tsx`](remotion_explainer/src/scenes/Scene7Revocation.tsx) while the live timer climbed to `179.4 s`. |
| **Zero Authorization Leaks** | `0` mismatches across `1,200` live SpiceDB principals in `H1v3` (`LookupResources` vs. UBP set equality), `0` unauthorized IDs across `169,810` confirmatory query records, `0 / 10,000` fuzzing mismatches in `R1`, and `0` post-revocation leaks across `8,916` post-`ZedToken` concurrent queries in `R4b`. |
| **`100%` Recall@10** | Exact authorized top-10 computed per query via exhaustive FP32 inner product over $\Phi(u, C_q, \zeta)$ ([`bench/experiments.py:_exact_top_k`](bench/experiments.py)). Mode 3 scans all `N_cand` contiguous SQ8 vectors in the allowed intervals and exact-FP32 reranks the top `max(4k, 64)` candidates (`100.00%` verified across `S ∈ {0.01%, 0.1%, 0.5%, 1.0%}`). |
| **`+1.91%` Semantic Bridges** | Relative memory overhead (`+32 B/node` for 8 `uint32` bridge IDs vs. `1,672 B/node` baseline FP32+HNSW); Recall@10 gain at `S=0.1%` is **`+60.85` percentage points** on Quora (`5.75% → 66.60%`) and **`+69.88` percentage points** on NQ (`5.69% → 75.57%`). Full Mode-3+SQ8 retains a separate `+384 B/node` `SQ8` buffer (`+24.8%` total extra RAM, documented explicitly in `§6` Limitations). |
| **`30.8×` SIMD Speedup / Hardware Baseline** | Prior `v2` compared C++ NEON SQ8 against masked NumPy/FP32 gather (`v3` paper separates Python `O(N)` mask-marshaling floor cleanly). New `R3` proves **`28.73×` cold (`33.64×` warm)** speedup purely inside C++ (`scattered FP32 scalar → Z-order SQ8 NEON`) and shows portable scalar C++ still runs sub-millisecond (`0.13–0.73 ms`). |
| **`100%` Theoretical Bound Satisfaction** | Proven in Theorem 1 (`|T_UBP+| <= k0 + m(b-1)L`, [`paper/prism_ann.tex`](paper/prism_ann.tex)) and empirically verified across `1,200 / 1,200` live SpiceDB principals (`H1v3`) and `10,000 / 10,000` deep/alternating trees (`R1`). |
