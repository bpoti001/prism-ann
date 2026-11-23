# Prism-ANN External Reviewer Audit & Hardening Report (`v3.1`)

**Repository:** [`bpoti001/prism-ann`](https://github.com/bpoti001/prism-ann)  
**Paper PDF:** [`prism_ann_paper.pdf`](prism_ann_paper.pdf) (`12` pages)  
**Pre-Registered Protocols:** [`PROTOCOL_v3.md`](experiments/v3/PROTOCOL_v3.md) & [`PROTOCOL_v3_1.md`](experiments/v3/PROTOCOL_v3_1.md)  
**Freeze Manifests:** [`FREEZE.md`](FREEZE.md) (`5/5`), [`FREEZE_v3.md`](FREEZE_v3.md) (`7/7`), [`FREEZE_v3_1.md`](FREEZE_v3_1.md) (`8/8`)  
**Confirmatory Raw Data (`169,810` queries):** [`results/v3/raw/`](results/v3/raw) → [`results/v3/summary.json`](results/v3/summary.json) (`recompute_v3 --check`: `MATCH`, `11/11 SUPPORTED`)  
**Reviewer Audit Raw Data (`23,056` records):** [`results/v3_1_audit/raw/v3_1_reviewer_audit.jsonl`](results/v3_1_audit/raw/v3_1_reviewer_audit.jsonl) → [`results/v3/reviewer_audit_v3_1.json`](results/v3/reviewer_audit_v3_1.json) (`recompute_v3_1 --check`: `MATCH`, `5/5 SUPPORTED`)

This document answers every technical challenge raised in the external systems review (`§6.1–§6.6`, `§8 Experiments`, and `§10 Evidence Separation`), strictly separating **(A) Formal Proofs**, **(B) Frozen Confirmatory Runs (`v3-confirmatory-001`)**, and **(C) Pre-Registered Audit Suites (`v3.1`, `R1`–`R5`)**.

---

## 1. Evidence & Reproducibility Map (Separating Implementation, Empirical Data & Theory)

| Layer | Where to Verify in Repo | Audit Status |
| :--- | :--- | :--- |
| **Algorithmic Proofs & Theorems** | [`paper/prism_ann.tex`](paper/prism_ann.tex) (`§3`, Theorem 1, Corollary 1, Propositions 2–4) | Theorem 1 proves $\|T_{\text{UBP}}^+(u)\| \le k_0 + m(b-1)L$ and exact equivalence `0 FP / 0 FN`. |
| **Native C++17 / ARM NEON Kernels** | [`bench/prism_ckernel.cpp`](bench/prism_ckernel.cpp) (`7/7` `FREEZE_v3`) & [`bench/prism_audit_kernel.cpp`](bench/prism_audit_kernel.cpp) (`8/8` `FREEZE_v3_1`) | SHA-256 frozen before running confirmatory & audit harnesses. |
| **Frozen Confirmatory Run (`169,810` records)** | [`bench/harness_v3.py`](bench/harness_v3.py), [`results/v3/raw/`](results/v3/raw), [`bench/recompute_v3.py`](bench/recompute_v3.py) | `recompute_v3 --check` exits `0` (`MATCH`); `0` leaks across all `169,810` records; `11/11` predictions (`P1a`–`P5`) `SUPPORTED`. |
| **Pre-Registered Reviewer-Audit Suite (`R1`–`R5`)** | [`PROTOCOL_v3_1.md`](experiments/v3/PROTOCOL_v3_1.md), [`bench/run_reviewer_audit_v3_1.py`](bench/run_reviewer_audit_v3_1.py), [`bench/recompute_v3_1.py`](bench/recompute_v3_1.py) | `23,056` raw records; `recompute_v3_1 --check` exits `0` (`MATCH`); `5/5` audit predictions (`PR1`–`PR5`) `SUPPORTED`. |
| **Publication Figures & Unit/Parity Tests** | [`bench/plot_v3_1.py`](bench/plot_v3_1.py), [`tests/`](tests), [`verify_prism_hallucinations.py`](verify_prism_hallucinations.py) | `19/19` `pytest` passing + Brake 1 programmatic check verifying 0.0% drift across `summary.json`, `reviewer_audit_v3_1.json`, `prism_ann.tex`, & this report. |

---

## 2. Five Pre-Registered Reviewer-Audit Experiments (`v3.1` — `PR1`–`PR5` All `SUPPORTED`)

### `R1` — 10,000-Hierarchy Property-Based & Alternating `GRANT/DENY` Fuzzing (§6.1 · `PR1: SUPPORTED`)
*Challenge:* A 1,200-principal test does not stress arbitrary hierarchy depths, fanouts, or alternating `Root Grant -> L1 Deny -> L2 Re-Grant -> L3 Sub-Deny -> Leaf Override` rules.  
*Method:* Executed `10,000` individual logged trials (`5,000` `R1_standard` + `5,000` `R1_alternating`) spanning `(b=8, L=4)`, `(b=4, L=5)`, and `(b=6, L=4)`, comparing UBP boundary tokens against exhaustive leaf-oracle sets.

| Suite | Trials | Topologies | Set Mismatches (vs. Leaf Oracle) | Bound Satisfaction | `\|T_UBP+\|` Median / Max |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Standard ReBAC (`but not` + Revoked Edges) | `5,000` | `(8,4), (4,5), (6,4)` | **`0 / 5,000`** (`0` FP, `0` FN) | **`100.0%`** | `3.0` / `249` |
| Alternating Overrides (`GRANT↔DENY` up to `L=5`) | `5,000` | `(8,4), (4,5), (6,4)` | **`0 / 5,000`** (`0` FP, `0` FN) | **`100.0%`** | `48.0` / `164` |
| **Combined Fuzzing Total** | **`10,000`** | Depth `4–5` | **`0 / 10,000`** | **`100.0%`** | — |

---

### `R2` — Ultra-Low Selectivity `S = 0.01%` on Quora (`522,931`) & BEIR NQ (`250,000`) (§6.2 & Exp 2 · `PR2: SUPPORTED`)
*Method:* Depth-5 hierarchy overlays (`b=8, L=5`, `32,768` docs, `S_actual ≈ 0.0091%`, `3` seeds × `50` queries = `150` queries/corpus).

| System | BEIR Quora (`S_act = 0.00917%`) R@10 / Med / P95 | BEIR NQ (`S_act = 0.00912%`) R@10 / Med / P95 |
| :--- | :---: | :---: |
| `faiss-hnsw-M16` | `0.87%` / `4.243 ms` / `5.539 ms` | `0.60%` / `0.545 ms` / `0.867 ms` |
| `acorn-1` (upstream C++) | `0.27%` / `0.969 ms` / `1.160 ms` | `0.40%` / `0.513 ms` / `1.059 ms` |
| `v3-geom-M8` (graph-only bridges) | **`85.73%`** / `0.589 ms` / `2.609 ms` | **`92.27%`** / `0.253 ms` / `0.368 ms` |
| **`v3-full-guard-sq8` (complete)** | **`100.00%`** / **`0.056 ms`** / `0.099 ms` | **`100.00%`** / **`0.032 ms`** / `0.046 ms` |

---

### `R3` — 6-Way Mode-3 Component Isolation (`Z-Order / CRoaring / SQ8 / NEON vs. Scalar`; Warm & Cold LLC) (§6.3–§6.4 · `PR3: SUPPORTED`)
*Method:* Cold-cache tests execute a `64 MB` volatile stride-64 L1/L2/SLC flush (`audit_flush_llc_cache`) before every single query on full BEIR Quora (`522,931 × 384-d`). Scalar baselines explicitly disable SIMD vectorization (`#pragma clang loop vectorize(disable)`).

| C++ Kernel Variant (`100.0%` R@10 on all variants) | `S = 0.01%` | `S = 0.1%` | `S = 0.5%` | `S = 1.0%` |
| :--- | :---: | :---: | :---: | :---: |
| `1. scattered_f32_scalar` (non-Z-ordered, no SIMD) | `0.0996 ms` | `0.3324 ms` | `1.5024 ms` | `2.9363 ms` |
| `2. scattered_f32_neon` (non-Z-ordered, NEON FP32) | `0.0659 ms` | `0.2161 ms` | `0.7779 ms` | `1.4570 ms` |
| `3. zorder_f32_scalar` (contiguous Z-order, scalar FP32) | `0.0771 ms` | `0.2260 ms` | `1.0175 ms` | `2.0685 ms` |
| `4. zorder_f32_neon` (contiguous Z-order, NEON FP32) | `0.0320 ms` | **`0.0429 ms`** | `0.1064 ms` | `0.1894 ms` |
| `5. zorder_sq8_scalar` (portable C++ scalar SQ8 + FP32 rerank) | `0.0780 ms` | `0.1275 ms` | `0.3923 ms` | **`0.7339 ms`** |
| `6. zorder_sq8_neon` (contiguous Z-order + ARM NEON `vdotq_s32`) | `0.0394 ms` | `0.0475 ms` | **`0.0725 ms`** | **`0.1022 ms`** |

- **Cold-Cache Speedup Attribution (`S = 1.0%`):** Contiguous Z-order + `CRoaring` (`scattered → zorder` on FP32 NEON) = **`7.69×`**; `SQ8` bandwidth reduction (on scalar) = **`2.82×`**; ARM NEON over portable scalar C++ (`SQ8`) = **`7.18×`**; combined speedup = **`28.73×` cold (`33.64×` warm)**.
- **Portability:** Pure portable scalar C++ (`5_zorder_sq8_scalar`) with **zero SIMD instructions** still achieves `100.0%` Recall@10 in `0.1275 ms` (`S=0.1%`) to `0.7339 ms` (`S=1.0%`) under cold cache.

---

### `R4` — $O(1)$ Single-Edge Subtree Scaling (`128 → 490,419` Chunks) & Concurrent `ZedToken` Race (§6.5 · `PR4: SUPPORTED`)

**Part A — Persistent PostgreSQL 17 SpiceDB Single-Edge Subtree Scaling (`n = 5` trials per scale, `0` vector writes):**
| Docs Revoked | Chunks Revoked | Graph Edges Deleted | Median Latency (Min–Max) | Vector Writes |
| :---: | :---: | :---: | :---: | :---: |
| `1` | `128` | `1` | `1.65 ms` (`1.45–4.32`) | `0` |
| `8` | `1,024` | `1` | `1.10 ms` (`0.86–16.79`) | `0` |
| `64` | `8,192` | `1` | `1.68 ms` (`1.20–4.73`) | `0` |
| `512` | `65,536` | `1` | `0.88 ms` (`0.78–1.09`) | `0` |
| `1,024` | `131,072` | `1` | `0.85 ms` (`0.77–0.92`) | `0` |
| `2,048` | `262,144` | `1` | `0.79 ms` (`0.78–0.84`) | `0` |
| `3,840` | `490,419` | `1` | `0.79 ms` (`0.71–1.00`) | `0` |

**Part B — Concurrent 4-Thread In-Flight Query Race + Live Postgres SpiceDB Revocation (`131,072` chunks revoked mid-flight):**
- **Total concurrent C++ H-HNSW queries across 4 reader threads:** **`11,767`** (`5,778` pre-revocation on `zeta=1`, `5,989` post-revocation on `zeta=2`).
- **In-flight queries actively crossing atomic cutoff `t_swap`:** **`4`** (all completed cleanly on immutable `zeta=1` snapshot isolation without crashes or torn reads).
- **Queries started after atomic swap using old `zeta=1`:** **`0`**.
- **Chunks leaked from revoked subtree on any `zeta >= 2` query:** **`0 / 5,989`**.
- **Persistent PG17 SpiceDB commit time:** **`60.35 ms`** · **Atomic UBP + CRoaring snapshot compile & swap window:** **`0.096 ms` (`96 µs`)**.

---

### `R5` — Dynamic Document Ingestion & Background Z-Order Compaction (§6.3 · `PR5: SUPPORTED`)

| New Batch Size | Total Vectors | Online Delta-Buffer Append (`µs/vec`) | Async Background Z-Order Compaction | C++ HNSW CSR ID Remap (`500k` nodes) |
| :---: | :---: | :---: | :---: | :---: |
| `+1,000` | `501,000` | `21.21 ms` (`21.21 µs/vec`) | `2,556.6 ms` | `118.98 ms` |
| `+5,000` | `505,000` | `65.89 ms` (`13.18 µs/vec`) | `1,842.8 ms` | `111.08 ms` |
| `+10,000` | `510,000` | `84.51 ms` (`8.45 µs/vec`) | `1,437.0 ms` | `118.35 ms` |
| `+25,000` | `525,000` | `129.36 ms` (`5.17 µs/vec`) | `1,763.9 ms` | `115.40 ms` |

---

## 3. Reconciliation of Reviewer Table (§6.6)

| Claim Reviewed | Exact Reconciliation & Source Reference |
| :--- | :--- |
| **`67.28 ms` vs `179.4 s` vs `138.2 s`** | `179.4 s` (`179,390.6 ms`) is the final `n=5` median `pgvector UPDATE` over `522,931` rows (`H4v3`, [`v3-confirmatory-001__H4_postgres.jsonl`](results/v3/raw/v3-confirmatory-001__H4_postgres.jsonl)). `138.2 s` appeared in a mid-animation frame (`77%` progress, `118,314 / 153,600` rows) in [`Scene7Revocation.tsx`](remotion_explainer/src/scenes/Scene7Revocation.tsx) while the live timer climbed to `179.4 s`. |
| **Zero Authorization Leaks** | `0` mismatches across `1,200` live SpiceDB principals in `H1v3`, `0` unauthorized IDs across `169,810` confirmatory query records, `0 / 10,000` fuzzing mismatches in `R1`, and `0 / 5,989` post-`ZedToken` leaks in `R4b`. |
| **`100%` Recall@10** | Exact authorized top-10 computed per query via exhaustive FP32 inner product over $\Phi(u, C_q, \zeta)$ ([`bench/experiments.py`](bench/experiments.py)). Mode 3 scans all `N_cand` contiguous SQ8 vectors and exact-FP32 reranks top `max(4k, 64)` candidates (`100.00%` verified across `S ∈ {0.01%, 0.1%, 0.5%, 1.0%}`). |
| **`+1.91%` Semantic Bridges** | Relative graph RAM overhead (`+32 B/node`); Recall@10 gain at `S=0.1%` is `+60.85` pts (`Quora`) and `+69.88` pts (`NQ`). Full Mode-3+SQ8 retains an auxiliary `+384 B/node` `SQ8` buffer (`+24.8%` total extra RAM, documented in Paper §V-B). |
| **`30.8×` SIMD Speedup / Hardware Baseline** | `v3` separates Python `O(N)` mask-marshaling floor cleanly, and `R3` isolates **`28.73×` cold (`33.64×` warm)** pure C++ speedup (`scattered FP32 scalar → Z-order SQ8 NEON`), proving portable scalar C++ still runs in `0.1275–0.7339 ms`. |
| **`100%` Theoretical Bound Satisfaction** | Proven in Theorem 1 (`|T_UBP+| <= k0 + m(b-1)L`, [`paper/prism_ann.tex`](paper/prism_ann.tex)) and empirically verified across `1,200 / 1,200` live SpiceDB principals (`H1v3`) and `10,000 / 10,000` randomized trees (`R1`). |
