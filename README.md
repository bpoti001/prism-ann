# Prism-ANN: Co-Designed SpiceDB ReBAC Upward Boundary Pruning, Geometric Express Bridges, and Native SIMD Tri-Modal Filtered HNSW

[![Verification](https://img.shields.io/badge/Provenance%20Audit-Verified%200%20Drift-brightgreen.svg)](#reproducibility--clean-machine-verification)
[![Unit Tests](https://img.shields.io/badge/pytest-27%2F27%20PASS-brightgreen.svg)](#reproducibility--clean-machine-verification)
[![Reviewer Audit](https://img.shields.io/badge/Reviewer%20Audit%20v3.1%2B3.2%2B3.3-R1--R11-blue.svg)](REVIEWER_AUDIT_REPORT.md)
[![Confirmatory Records](https://img.shields.io/badge/Raw%20Logs-207%2C685%20Records-blueviolet.svg)](results/v3/summary.json)

Official implementation, formal proofs, raw confirmatory & audit JSONL datasets, reproducible C++17 / ARM NEON kernels, interactive research report, executive presentation, and explainer videos for **Prism-ANN**.

> **Three-Tier Audience Guides (`New-Grad -> Senior Architect -> Researcher`):**
> - **New-Grad / Associate Engineer:** [`docs/ONBOARDING_NEW_GRAD.md`](docs/ONBOARDING_NEW_GRAD.md) (mirrored in [`prism_ann_onboarding_guide.md`](prism_ann_onboarding_guide.md)) + explainer video [`prism_ann_onboarding_explainer.mp4`](prism_ann_onboarding_explainer.mp4) (`4m 26s`) / [invideo](https://invideo.io/@bhavyateja-320639/prism-ann-v3-executive-explainer/tree/main/seq-5.1).
> - **Senior Systems Engineer / Architect:** [`docs/ARCHITECTURE_SENIOR_ENGINEER.md`](docs/ARCHITECTURE_SENIOR_ENGINEER.md) (CSR/Z-order layout, C++17 & NEON kernels, `ZedToken` snapshots, memory/latency budgets).
> - **Researcher / External Reviewer:** [`docs/RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md`](docs/RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md), [`REVIEWER_AUDIT_REPORT.md`](REVIEWER_AUDIT_REPORT.md), & [`prism_ann_paper.pdf`](prism_ann_paper.pdf) (`12 pages`, [`paper/prism_ann.tex`](paper/prism_ann.tex)).

---

## 🧭 Reviewer Navigation Map (Every Claim Mapped to Code, Proofs & Raw Logs)

| Review Question / Section | Exact Asset in This Repository | Summary Finding |
| :--- | :--- | :--- |
| **Paper & Formal Proofs (§3 Theorem 1, Corollary 1, Props 2–4)** | [`prism_ann_paper.pdf`](prism_ann_paper.pdf) · [`paper/prism_ann.tex`](paper/prism_ann.tex) | 12-page IEEE manuscript separating formal guarantees, frozen confirmatory data, & audit suites. |
| **Detailed Point-by-Point Reviewer Response & Novelty Matrix** | [`REVIEWER_AUDIT_REPORT.md`](REVIEWER_AUDIT_REPORT.md) · [`docs/RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md`](docs/RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md) | Reconciles §6.6 table items, splits Theorems 1–2, compares `Veda`/`RACORN`/`EMA`/`Curator` (`amanbayev2026gls` for GLS), & documents `R1`–`R11`. |
| **Algorithm 1: Subtractive UBP (`P_UBP`) & Dynamic DAGs** | [`ubp_resolver.py`](src/modules/prism_ann/ubp_resolver.py) · [`dynamic_dag_ubp.py`](src/modules/prism_ann_v3/dynamic_dag_ubp.py) | Frozen SHA-256 (`FREEZE_v3.md`, `FREEZE_v3_3.md` `9/9`). `DynamicMultiParentAuthGraph` + `VersionedLineageCorpus` handle dynamic DAG edge mutations (`0` FP/FN in `R9a` & `R9b`). |
| **Geometric Bridges & `ACORN-GLS` (`H-HNSW v2`)** | [`src/modules/prism_ann_v3/geometric_hhnsw.py`](src/modules/prism_ann_v3/geometric_hhnsw.py) | `M_bridge=8` Vamana/RNG edges (`+32 B/node` = `+1.91%` graph RAM) on shared FAISS `M=16` base graph. |
| **Native C++17 / ARM NEON + Local-Stall Guard Kernel** | [`bench/prism_ckernel.cpp`](bench/prism_ckernel.cpp) · [`src/modules/prism_ann_v3/trimodal_v3.py`](src/modules/prism_ann_v3/trimodal_v3.py) | Frozen C++ kernel (`FREEZE_v3.md`): NEON `vdotq_s32` (`SQ8`)+FP32 rerank & 3-stage stall guard. |
| **6-Way Mode-3 Isolation Kernel (`Z-Order / SQ8 / NEON vs Scalar`)** | [`bench/prism_audit_kernel.cpp`](bench/prism_audit_kernel.cpp) · [`bench/run_reviewer_audit_v3_1.py`](bench/run_reviewer_audit_v3_1.py) | Isolates contiguous Z-order (`7.35×`), `SQ8` (`2.85×`), NEON (`7.46×`) under 64 MB Cold LLC flush. |
| **Live SpiceDB & `pgvector` Benchmark Drivers** | [`bench/engines.py`](bench/engines.py) · [`bench/harness_v3.py`](bench/harness_v3.py) · [`bench/recompute_v3.py`](bench/recompute_v3.py) | Live SpiceDB `v1.57.1` (memory & PG17), PostgreSQL `17.12` + `pgvector 0.8.7`, FAISS `1.16.0`, ACORN, hnswlib. |
| **Frozen Confirmatory Logs (`169,810` queries)** | [`results/v3/raw/`](results/v3/raw) · [`results/v3/summary.json`](results/v3/summary.json) · [`results/v3/DEVIATIONS.md`](results/v3/DEVIATIONS.md) | Bit-for-bit verified by `python -m bench.recompute_v3 --check`. Zero permission leaks. |
| **Reviewer Audit Logs (`R1`–`R11`, `v3.1` + `v3.2` + `v3.3`)** | [`reviewer_audit_v3_1.json`](results/v3/reviewer_audit_v3_1.json) · [`reviewer_audit_v3_2.json`](results/v3/reviewer_audit_v3_2.json) · [`reviewer_audit_v3_3.json`](results/v3/reviewer_audit_v3_3.json) | `10k` tree + `36`-DAG `5k` + `1,000`-independent-DAG `5k` dynamic mutation fuzz, live SpiceDB `10/10` (`R9b`) & 8-thread opaque-`ZedToken` (`R11`), modeled `R7` + directly timed `R10` E2E (`ef=32..512`, in-timer `SQ8` quant). |
| **Unit, Parity & Provenance Tests** | [`tests/test_prism_ann.py`](tests/test_prism_ann.py) · [`tests/test_prism_v3_kernel.py`](tests/test_prism_v3_kernel.py) · [`tests/test_bench_provenance.py`](tests/test_bench_provenance.py) · [`verify_prism_hallucinations.py`](verify_prism_hallucinations.py) | `27/27` pytest passing + `420/420` Brake-1 raw-to-LaTeX anti-hallucination checks passing (`0` errors). |

---

## 🎥 Explainer Videos, Interactive Report & Slide Deck

| Asset | File / Link | Audience |
| :--- | :--- | :--- |
| **1. New-Grad Engineering Onboarding (`4m 26s`)** | [`prism_ann_onboarding_explainer.mp4`](prism_ann_onboarding_explainer.mp4) · [invideo Cut](https://invideo.io/@bhavyateja-320639/prism-ann-v3-executive-explainer/tree/main/seq-5.1) | Fresh graduates (RAG → Embeddings → HNSW → SpiceDB → 3 Traps → Prism-ANN + Query Flow). |
| **2. Pure-Idea Scientific Explainer (`1m 43s`)** | [`prism_ann_idea_explainer.mp4`](prism_ann_idea_explainer.mp4) · [invideo Cut](https://invideo.io/@bhavyateja-320639/prism-ann-v3-executive-explainer/tree/main/seq-4.1) | Researchers evaluating problem formulation, state of the art, Theorem 1–4 theory & architecture (zero benchmark status). |
| **3. Full Confirmatory Results Explainer (`4m 53s`)** | [`prism_ann_animated_explainer.mp4`](prism_ann_animated_explainer.mp4) · [invideo Cut](https://invideo.io/@bhavyateja-320639/prism-ann-v3-executive-explainer/tree/main/seq-2.1) | Systems & performance engineers (`169,810` confirmatory records, ablations, & live PG17 revocation race). |
| **Interactive HTML Research Report** | [`prism_ann_research_report.html`](prism_ann_research_report.html) | Deep-dive clickable dashboard with all charts, architecture diagrams, & theorem breakdowns. |
| **Executive Presentation (10 Slides)** | [`prism_ann_executive_presentation.pptx`](prism_ann_executive_presentation.pptx) | Boardroom / leadership deck with embedded benchmark figures & speaker notes. |
| **Remotion Animation Source Code** | [`remotion_explainer/`](remotion_explainer) | Complete TSX compositions for all 3 animated explainers. |

---

## 📊 Key Results Summary (`v3-confirmatory-001` + `v3.1` Reviewer Audit)

### A. Frozen Confirmatory Evaluation (`169,810` queries, `11/11` pre-registered predictions supported)
- **Theorem 1 UBP Equivalence (`H1v3`):** **`0 / 1,200` mismatches** on live SpiceDB v1.57.1 (in-memory & persistent PostgreSQL 17), `100%` bound satisfaction (`|T_UBP+| <= k0 + m(b-1)L`), cutting broad-principal pre-filtering by **`225.9×` (memory)** and **`278.2×` (PostgreSQL 17: `98.30 ms → 0.35 ms`)**.
- **Low-Selectivity Multi-Corpus Recall (`H2v3`, `S ∈ {0.1%, 0.5%, 1%, 5%}`):**
  - Graph-only **`v3-geom-M8`** (`+32 B/node` = `+1.91%` graph RAM) lifts `S=0.1%` Recall@10 from `5.75% → 66.60%` (BEIR Quora `522,931`) and `5.69% → 75.57%` (BEIR NQ `250,000`), beating `FAISS M=16`, v2 ring-chord bridges, `ACORN-1`, and `ACORN-γ`.
  - Complete **`v3-full-guard-sq8`** (`+24.8%` total extra RAM incl. auxiliary `SQ8` buffer) hits **`100.00%` Recall@10** at `S ≤ 1%` in **`0.05–0.11 ms` kernel latency**.
- **Negative-Correlation Local-Stall Guard (`H3v3`, `S=2%, r ≤ 0.5`):** Recovers Recall@10 from `5.56%` (`FAISS`) to **`97.17%` (Quora, `0.35 ms`) / `96.42%` (NQ, `0.17 ms`)**, `131×–193×` faster than `hnswlib`, while at positive correlation `r ≥ 2.0` cutting distance evals by **`3.82×` (Quora) / `3.11×` (NQ)**.
- **Zero-Write Persistent Revocation (`H4v3`):** Revoking `1,024` docs (`153,600` chunks) in persistent PostgreSQL 17 SpiceDB takes **`67.28 ms` with `0` vector writes** vs. **`179.4 s`** for `PostgreSQL 17 + pgvector 0.8.7 UPDATE` (**`2,666.2×` faster**).
- **Causal Entry-Portal Ablation (`H5v3`):** Disabling all entry portals on `H-HNSW v2` retains **`101.0%–102.3%`** of the recall lift over `FAISS M=16`.

### B. Five Supplementary Reviewer-Audit Experiments (`v3.1` — [`REVIEWER_AUDIT_REPORT.md`](REVIEWER_AUDIT_REPORT.md))
1. **`R1` (`10,000`-Hierarchy Fuzzing):** `0 / 5,000` mismatches on standard `but not` ReBAC + `0 / 5,000` mismatches on generalized depth-5 alternating `GRANT ↔ DENY` override trees (`100.0%` bound satisfaction).
2. **`R2` (`S = 0.01%` Ultra-Low Selectivity):** On depth-5 overlays (`S_actual ≈ 0.0091%`, `0` leaks), `FAISS` (`0.60%–0.87%`) and `ACORN-1` (`0.33%–0.40%`) collapse below `1%`, whereas `v3-geom-M8` hits **`85.73%–92.27%`** (`0.27–0.54 ms`) and `v3-full-guard-sq8` hits **`100.00%` in `0.032–0.049 ms`**.
3. **`R3` (6-Way Cold-LLC Component Isolation, `64 MB` flush/query):** At `S=1.0%`, combined speedup of **`29.40×` cold (`34.18×` warm)** decomposes into **`7.35×`** from Z-order + `CRoaring` contiguity (`FP32` NEON), **`2.85×`** from `SQ8` bandwidth reduction, and **`7.46×`** from ARM NEON (`64`-MAC `vdotq_s32`) over portable C++ scalar (`0.728 ms` cold scalar `SQ8` still runs sub-millisecond without SIMD!).
4. **`R4` (Single-Edge Subtree Scaling & Concurrent `ZedToken` Race):** Persistent PG17 SpiceDB single-edge deletions from `128 → 490,419` chunks stay flat at **`0.74–1.66 ms` with `0` vector writes**; across `11,244` concurrent C++ H-HNSW queries on `4` reader threads crossing a live `131,072`-chunk PG17 SpiceDB revocation (`6.82 ms` commit, `0.091 ms` atomic snapshot swap), **`0 / 6,039` post-`zeta_rev` queries** leaked any revoked chunk.
5. **`R5` (Dynamic Ingestion & Background Z-Order Compaction):** Online delta-buffer ingestion appends `+1k..+25k` vectors in **`5.3–23.9 µs/vector`** without blocking readers; background lexicographic compaction + C++ HNSW CSR ID remapping completes off-critical-path in **`1.30–2.36 s`** (`116.3–121.6 ms` for `500k` CSR remap).

### C. Second & Third-Round Research Audits (`v3.2` + `v3.3` — [`docs/RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md`](docs/RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md))
6. **`R6` (`5,000` Permission Trials on `36` Generated Multi-Parent DAGs, `PR6: SUPPORTED`):** `0 / 5,000` mismatches (`0` FP, `0` FN) with `>= 672` secondary parents (`1,170.0` mean), verifying Theorem 2 under static multi-parent DAG hierarchy edges.
7. **`R7` (Modeled Two-Track Benchmark + In-Repo `racorn-1-fallback` C++ Proxy & Zero-RAM `FP32`, `PR7: FALSIFIED` on strict `<=0.35 ms` / `>=100x` fragmented-L5 cutoffs; `0 / 1,500` leaks):** Track 1 excludes filter compilation and `SQ8` query quantization (`v3-geom-M8` achieves `71.4%–87.4%` R@10 at $S \le 1\%$ vs. `0.2%–31.2%` `ACORN-1`, `0.8%–76.6%` `FAISS`, `6.0%–89.0%` our in-repo `racorn-1-fallback` C++ proxy—not upstream `github.com/naver/racorn`), while `v3-full-guard-f32` (`0` extra vector RAM) and `v3-full-guard-sq8` hit **`100.0%` R@10** in **`0.0206–0.4527 ms`** / **`0.0380–0.4344 ms`**, cutting modeled Track-2 PG17 latency by **`24.18×–28.07×`**.
8. **`R8` (Exact vs. Empirical Recall Shortlist Audit, `PR8: FALSIFIED` on strict `<=0.25 ms` exact-FP32 cutoff at fragmented `S=1.0%`):** Exact `FP32` Mode 3 (`0.0035 ms` at `S=0.01%`, `0.0235 ms` at `S=0.1%`, `0.3289 ms` at `S=1.0%`) is mathematically exact with `0` extra vector RAM, while `SQ8 + M_rerank >= 32` retains `100.0%` empirical R@10 (`0.0780 ms` at `S=1.0%`).
9. **`R9a` & `R9b` (`1,000` Independent Dynamic Multi-Parent DAGs + `10/10` Live Native SpiceDB Dynamic Tests, `PR9a`/`PR9b: SUPPORTED`):** Addresses Priority Findings 1 & 2 via `DynamicMultiParentAuthGraph` + `VersionedLineageCorpus` (`FREEZE_v3_3.md` `9/9`): `0 / 5,000` FP/FN across `1,000` independent DAGs (`min 105`, `mean 486.0` sec edges) under edge additions, shared-child unlinks, deny removals, grant flips, & quarantines (`R9a`), and `0` mask/search/`CheckPermission` mismatches across `10/10` live SpiceDB scenarios (`R9b`).
10. **`R10` (Direct Unbroken E2E Timer + In-Timer `SQ8` Quantization + `efSearch={32..512}`, `750 + 1,000` Queries, `0` Leaks; `PR10: FALSIFIED` at $S=0.01\%$ live RPC):** Single unbroken `perf_counter_ns()` timer (`T_auth + T_filter + T_SQ8_quant + T_ANN`) hits **`6.20×–6.47×`** live RPC at $S=0.01\%$ (`PR10: FALSIFIED` vs `>=10×`) and **`11.39×–89.10×`** at $S \ge 0.1\%$ (`197×–522×` mirror). Exact `FP32` (`0.0422/0.0788 ms` mirror) beats in-timer `SQ8` (`0.0527/0.0909 ms`) for $S \le 0.1\%$, reversing at $S \ge 0.5\%$. At $S=0.5\%$, `v3-geom-M8` hits `52.8%–98.0%` across `ef={32..512}`.
11. **`R11` (`8`-Thread Live Native SpiceDB Opaque-`ZedToken` Concurrent Revocation, `1,760` Queries, `PR11: SUPPORTED`):** `427` `at_exact_snapshot` + `1,333` `at_least_as_fresh` live SpiceDB queries (`1.437 ms` med RPC, `0.111 ms` med search) yielded **`0` oracle mismatches, `0` post-revocation leaks, `0` stale errors**.

---

## 🛠 Reproducibility & Clean-Machine Verification

Run the one-command clean-machine verification or full audit re-execution runner ([`reproduce_clean_machine.sh`](reproduce_clean_machine.sh)):

```bash
# Fast clean-machine verification (~10s): compiles C++17 kernels if needed, runs unit tests,
# verifies FREEZE / FREEZE_v3 / FREEZE_v3_1 / FREEZE_v3_3 hashes, recomputes all 4 JSONL->JSON summaries bit-for-bit,
# and runs the 376-scenario Blast Radius proof + Brake 1..3 audit suite.
./reproduce_clean_machine.sh --verify

# Full standalone C++/Python audit re-execution (re-runs R1..R11 from scratch and verifies recompute checks):
./reproduce_clean_machine.sh --rerun-audits
```
