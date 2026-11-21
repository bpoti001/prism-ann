# Prism-ANN (SpiceDB ReBAC + Filtered HNSW): Executive Summary, Remaining Experiments & 2-Week Publication Roadmap

See full visual artifact: `prism_ann_2week_publication_roadmap.md`

## 1. What We Are Trying to Do
Solve the dual-graph bottleneck when Enterprise Multimodal Knowledge Platforms (EMKPs) enforce hierarchical **SpiceDB / Zanzibar ReBAC** (with non-monotonic `but not` / `DENY` ethical walls) and **Ontological Meaning Magnets** over **HNSW vector indexes**:
1. **Control Plane:** Subtractive-Aware Upward Boundary Pruning ($\mathcal{P}_{\text{UBP}}$, Theorem 1: $|T^+_{\text{UBP}}| \le k_0 + m(b-1)L$) eliminates SpiceDB's $\Theta(b^L)$ `LookupResources` leaf-disjunction bottleneck and enables $0$-write revocation.
2. **Data Plane:** Filtered HNSW + Z-Ordered `CRoaring`-SIMD hybrid routing eliminates the sub-1% and negative-correlation ($r = S_{\text{loc}}/S < 1$) recall–latency cliff.

## 2. What Is Proven Today vs. What Failed (Confirmatory v2 on 522,931 BEIR Quora + Real Engines)
- **Proven Wins (`62,410` raw JSONL records, 3 seeds, `FREEZE.md` 5/5 match):**
  - `H1v2` (Real SpiceDB `v1.57.1` + `CRoaring`): **`0/600` mismatches**, `100%` within Theorem 1 bound, **`226.5×`** faster pre-filter bitmap build locally (`0.310 ms` vs. `70.150 ms`) and **`33.6×`** via live `ReadRelationships` RPCs (`2.089 ms`).
  - `H4v2` (Real SpiceDB vs. Real PostgreSQL 17.12 + `pgvector` 0.8.7): **`0` vector writes**, **`76.05 ms`** vs. **`182.5 s`** (**`2,400.1×` faster**) to revoke `1,024` docs (`153,600` rows).
  - `H2v2` / `H3v2`: Proved `FAISS M=16` (`5.95%`) and upstream C++ `ACORN-1` (`0.85%`, stalls at `11.4` evals) collapse at $S=0.1\%$, while `hnswlib` (`131.5 ms`) and `pgvector` (`338.2 ms` med / `915.1 ms` P95) pay steep tail latency. Mode 3 achieves `100.00%` R@10 at $S \le 1\%$ in `1.10–2.14 ms`.
- **Remaining Weaknesses (Independent Phase 15 Review: `5.5 / 10` Borderline / Major Revision):**
  - Non-geometric $M_{\text{bridge}}=4$ ring-chord bridges reach only `28.2%–53.3%` graph-only R@10 at $S \le 1\%$, and `prism-full` falls to `24.55%` at $S=2\%, r \le 0.5$ (`H3v2`).
  - `P2b` and `P3b` falsified (`-2.00 pt` recall drop at `5.33×` eval savings for `P3b`).
  - Missing `InitEntryPortals` vs. express-bridge ablation.
  - Python Mode 3 (`1.10–2.14 ms`) slower than BLAS `exact-brute-force` (`0.25–1.94 ms`).
  - Single dataset (`BEIR Quora`) and in-memory SpiceDB datastore.

## 3. Remaining Experiments
- **E1 (Critical, Days 1–3):** Geometric intra-container bridges (`H-HNSW v2`) + local-stall Mode-3 guard for negative-correlation queries at $S=2\%$.
- **E2 (Critical, Day 3):** 4-way `InitEntryPortals` vs. Express-Bridge ablation.
- **E3 (High, Days 4–5):** C++ / NEON SIMD Mode-3 + `H-HNSW` kernel (`bench/prism_ckernel.cpp`) over Z-ordered `CRoaring` runs.
- **E4 (High, Days 8–10):** Second public corpus (`d=768`, e.g., BEIR MS-MARCO / FANNBench arXiv) + persistent PostgreSQL-backed SpiceDB (`--datastore-engine postgres`).
- **E5 (Medium, Days 8–10):** Dev-split $\tau_{\text{high}}$ calibration + native `Qdrant` and upstream `ACORN-γ` baselines.

## 4. Can We Publish in 2 Weeks?
- **arXiv Preprint (`cs.DB` / `cs.IR`):** **Yes (10–14 days for Option A full paper; 7 days for Option B focused SpiceDB UBP + Hybrid Planner paper)**, assuming employer publication approval is initiated on Day 1.
- **Top Conference (VLDB / SIGMOD / SIGIR / CIKM):** **Submission-ready manuscript in 14 days** (peer review + publication follows conference schedule).
