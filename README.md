# Prism-ANN: Co-Designed SpiceDB ReBAC Upward Boundary Pruning, Geometric Express Bridges, and Native SIMD Tri-Modal Filtered HNSW

[![Verification](https://img.shields.io/badge/Provenance%20Audit-238%2F238%20PASS-brightgreen.svg)](#reproducibility--provenance-verification)
[![Unit Tests](https://img.shields.io/badge/pytest-19%2F19%20PASS-brightgreen.svg)](#reproducibility--provenance-verification)
[![Reviewer Audit](https://img.shields.io/badge/Reviewer%20Audit%20v3.1-R1--R5%20Verified-blue.svg)](REVIEWER_AUDIT_REPORT.md)
[![Confirmatory Records](https://img.shields.io/badge/Raw%20Query%20Logs-169%2C810%20Records-blueviolet.svg)](results/v3/summary.json)

Official implementation, formal proofs, raw confirmatory & audit JSONL datasets, reproducible C++17 / ARM NEON kernels, interactive research report, executive presentation, and explainer videos for **Prism-ANN**.

> **New-Grad / Team Onboarding?** Start with our dedicated beginner explainer video ([`prism_ann_onboarding_explainer.mp4`](prism_ann_onboarding_explainer.mp4) · `4m 26s`) or interactive timeline on [invideo](https://invideo.io/@bhavyateja-320639/prism-ann-v3-executive-explainer/tree/main/seq-5.1).  
> **Research Reviewer Audit?** Start with [`REVIEWER_AUDIT_REPORT.md`](REVIEWER_AUDIT_REPORT.md) and [`prism_ann_paper.pdf`](prism_ann_paper.pdf) (`12 pages`, compiled from [`paper/prism_ann.tex`](paper/prism_ann.tex)).

---

## 🧭 Reviewer Navigation Map (Every Claim Mapped to Code, Proofs & Raw Logs)

| Review Question / Section | Exact Asset in This Repository | Summary Finding |
| :--- | :--- | :--- |
| **Paper & Formal Proofs (§3 Theorem 1, Corollary 1, Props 2–4)** | [`prism_ann_paper.pdf`](prism_ann_paper.pdf) · [`paper/prism_ann.tex`](paper/prism_ann.tex) | 12-page IEEE manuscript separating formal guarantees, frozen confirmatory data, & audit suites. |
| **Detailed Point-by-Point Reviewer Response (§6.1–§6.6)** | [`REVIEWER_AUDIT_REPORT.md`](REVIEWER_AUDIT_REPORT.md) | Reconciles all §6.6 table items & documents `R1`–`R5` hardening experiments. |
| **Algorithm 1: Subtractive UBP (`P_UBP`)** | [`src/modules/prism_ann/ubp_resolver.py`](src/modules/prism_ann/ubp_resolver.py) | Frozen SHA-256 (`FREEZE_v3.md`). `0/1,200` SpiceDB mismatches & `0/10,000` fuzzing mismatches. |
| **Geometric Bridges & `ACORN-GLS` (`H-HNSW v2`)** | [`src/modules/prism_ann_v3/geometric_hhnsw.py`](src/modules/prism_ann_v3/geometric_hhnsw.py) | `M_bridge=8` Vamana/RNG edges (`+32 B/node` = `+1.91%` graph RAM) on shared FAISS `M=16` base graph. |
| **Native C++17 / ARM NEON + Local-Stall Guard Kernel** | [`bench/prism_ckernel.cpp`](bench/prism_ckernel.cpp) · [`src/modules/prism_ann_v3/trimodal_v3.py`](src/modules/prism_ann_v3/trimodal_v3.py) | Frozen C++ kernel (`FREEZE_v3.md`): NEON `vdotq_s32` (`SQ8`)+FP32 rerank & 3-stage stall guard. |
| **6-Way Mode-3 Isolation Kernel (`Z-Order / SQ8 / NEON vs Scalar`)** | [`bench/prism_audit_kernel.cpp`](bench/prism_audit_kernel.cpp) · [`bench/run_reviewer_audit_v3_1.py`](bench/run_reviewer_audit_v3_1.py) | Isolates contiguous Z-order (`7.69×`), `SQ8` (`2.82×`), NEON (`7.18×`) under 64 MB Cold LLC flush. |
| **Live SpiceDB & `pgvector` Benchmark Drivers** | [`bench/engines.py`](bench/engines.py) · [`bench/harness_v3.py`](bench/harness_v3.py) · [`bench/recompute_v3.py`](bench/recompute_v3.py) | Live SpiceDB `v1.57.1` (memory & PG17), PostgreSQL `17.12` + `pgvector 0.8.7`, FAISS `1.16.0`, ACORN, hnswlib. |
| **Frozen Confirmatory Logs (`169,810` queries)** | [`results/v3/raw/`](results/v3/raw) · [`results/v3/summary.json`](results/v3/summary.json) · [`results/v3/DEVIATIONS.md`](results/v3/DEVIATIONS.md) | Bit-for-bit verified by `python -m bench.recompute_v3 --check`. Zero permission leaks. |
| **Reviewer Audit Logs (`R1`–`R5`, `v3.1`)** | [`results/v3/reviewer_audit_v3_1.json`](results/v3/reviewer_audit_v3_1.json) · [`results/v3_1_audit/raw/v3_1_reviewer_audit.jsonl`](results/v3_1_audit/raw/v3_1_reviewer_audit.jsonl) | `10,000` fuzz trees, `S=0.01%` Quora/NQ, Cold LLC isolation, `15,563`-query concurrent `ZedToken` race, dynamic Z-order compaction. |
| **Unit, Parity & Provenance Tests** | [`tests/test_prism_ann.py`](tests/test_prism_ann.py) · [`tests/test_prism_v3_kernel.py`](tests/test_prism_v3_kernel.py) · [`verify_prism_hallucinations.py`](verify_prism_hallucinations.py) | `19/19` pytest passing + `238/238` raw-to-LaTeX anti-hallucination checks passing. |

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
2. **`R2` (`S = 0.01%` Ultra-Low Selectivity):** On depth-5 overlays (`S_actual ≈ 0.0091%`), `FAISS` (`0.60%–0.87%`) and `ACORN-1` (`0.27%–0.40%`) collapse below `1%`, whereas `v3-geom-M8` hits **`85.73%–92.27%`** (`0.25–0.59 ms`) and `v3-full-guard-sq8` hits **`100.00%` in `0.032–0.056 ms`**.
3. **`R3` (6-Way Cold-LLC Component Isolation, `64 MB` flush/query):** At `S=1.0%`, combined speedup of **`28.73×` cold (`33.64×` warm)** decomposes into **`7.69×`** from Z-order + `CRoaring` contiguity (`FP32` NEON), **`2.82×`** from `SQ8` bandwidth reduction, and **`7.18×`** from ARM NEON (`64`-MAC `vdotq_s32`) over portable C++ scalar (`0.734 ms` cold scalar `SQ8` still runs sub-millisecond without SIMD!).
4. **`R4` (Subtree Scaling & Concurrent `ZedToken` Race):** Subtree deletes from `128` to `490,419` chunks on live PG17 SpiceDB run in **`0.94–8.34 ms` with `0` vector writes**; across `15,563` concurrent queries on `4` reader threads during a live `131,072`-chunk PG17 SpiceDB revocation (`60.73 ms` commit, `0.273 ms` atomic snapshot swap), **`0 / 8,916` post-`zeta_rev` queries** leaked any revoked chunk.
5. **`R5` (Dynamic Ingestion & Background Z-Order Compaction):** Online delta-buffer ingestion appends `+1k..+25k` vectors in **`5.2–23.8 µs/vector`** without blocking readers; background full lexicographic compaction + C++ HNSW CSR ID remapping completes off-critical-path in **`2.10–3.05 s`** (`103–138 ms` for `500k` CSR remap).

---

## 🛠 Reproducibility & Provenance Verification

```bash
# 1. Verify unit tests & C++ / Python kernel parity (19 tests)
.venv-bench/bin/python -m pytest -q

# 2. Verify SHA-256 freeze integrity & bit-for-bit raw JSONL -> summary.json recomputation
.venv-bench/bin/python -m bench.recompute_v3 --raw-dir results/v3/raw --check results/v3/summary.json

# 3. Verify 0.0% numerical drift between summary.json and paper/prism_ann.tex (238 checks)
.venv-bench/bin/python verify_prism_hallucinations.py

# 4. Run the 5 supplementary Reviewer Audit suites (R1..R5)
clang++ -O3 -mcpu=native -std=c++17 -shared -fPIC bench/prism_audit_kernel.cpp -o bench/_build/libprism_audit_kernel.dylib
.venv-bench/bin/python -m bench.run_reviewer_audit_v3_1
```
