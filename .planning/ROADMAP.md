# Roadmap: EpiGraph (`EngramRAG`) & `Prism-ANN` (ADR-to-arXiv Research Factory)

## Overview

This GSD roadmap governs both foundational milestones of the **EngramRAG** agentic memory engine (`Milestone 1` & `Milestone 2`, Phases 1–8, governed by `ADR-0000`) and the **Prism-ANN** co-designed SpiceDB ReBAC & Ancestor-Stitched Filtered HNSW architecture (`Milestone 3`, Phases 9–12, governed by `ADR-0000`, `ADR-0001`, `ADR-0002`, and `ADR-0003`). Every phase enforces **GSD-to-ADR Traceability (`ADR-0006`)** and **Multi-Model Tier Routing (`ADR-0010`: `Argon` Planning/Research, `Hydrogen` Build/TDD, `Neon` Adversarial Review, `Factory Overseer`)**.

## Phases

### Milestone 1: Core Algorithmic Validation & Distributed Scaffolding (Complete)

- [x] **Phase 1: Local Algorithmic Engine & LoCoMo Benchmark Validation** - Core graph algorithms, baselines, and empirical validation across 496 LoCoMo questions (`ADR-0000`).
- [x] **Phase 2: Distributed Dual-Store & Ingestion Reliability** - Redis Stack (HNSW) + Neo4j (GDS) dual-brain integration mediated by Redis Streams with incremental deduplication (`ADR-0000`).
- [x] **Phase 3: Longitudinal SCDP Simulation & Ablation Suite** - 100-session synthetic longitudinal simulation, God Node emergence tracking, CATD scaffolding retention tests, and ablation profiling (`ADR-0000`).
- [x] **Phase 4: LaTeX Manuscript Preparation & arXiv Pre-Print Submission** - Publication-grade LaTeX paper compilation, TikZ vector architecture diagrams, and arXiv submission to `cs.AI` / `cs.CL` (`ADR-0000`).

### Milestone 2: Advanced Empirical Validation & Downstream Closed-Loop Suite (Complete)

- [x] **Phase 5: Closed-Loop Downstream LLM Generation QA Benchmark** - Real-time downstream LLM question-answering generation on LoCoMo contexts measuring Token F1, Exact Match (EM), and ROUGE-L (`ADR-0000`).
- [x] **Phase 6: LongMemEval Knowledge Update & Contradiction Resolution** - Benchmark directed `SUPERSEDES` and `CORROBORATES` edge filtering against mutating user facts; measure Split-Brain Hallucination Rate (`ADR-0000`).
- [x] **Phase 7: Hyperparameter Sensitivity Landscape & Embedding Invariance** - Sweep PageRank damping $d \in [0.65, 0.95]$, RRF $k \in [20, 100]$, and test embedding backbone invariance (`ADR-0000`).
- [x] **Phase 8: Manuscript Integration & Extended Camera-Ready Package** - Integrate downstream generation tables, update references, and regenerate 300 DPI figures (`ADR-0000`).

### Milestone 3: Prism-ANN — SpiceDB ReBAC Upward Boundary Pruning & Ancestor-Stitched Filtered HNSW (Complete)

- [x] **Phase 9: Literature Recon, ADR-to-Theorem Minting & Pre-Registered Protocols (Argon High)** - Survey 2018–2026 ReBAC & FANNS literature, mint `ADR-0001`–`ADR-0003`, synchronize `CONTEXT.md` & `GLOSSARY.md`, and lock `H1`–`H4` protocols in Git (`ADR-0000`, `ADR-0001`, `ADR-0002`, `ADR-0003`).
- [x] **Phase 10: Deep Module Build & Tracer-Bullet Seam TDD (Hydrogen High)** - Implement `ubp_resolver.py`, `hnsw_gls.py`, `trimodal_planner.py`, and `index.py` behind Deep Module seams and verify 100% set equivalence via `tests/test_prism_ann.py` (`ADR-0001`, `ADR-0002`, `ADR-0003`).
- [x] **Phase 11: 10-Baseline Empirical Benchmark Suite & Academic Plotting (Hydrogen High)** - Execute `H1`–`H4` benchmarks across 10 systems/ablations (`B1..B7`, `Ablation 1..2`, `Prism-ANN Full`) and render 4 dual-panel vector PDF figures (`ADR-0001`, `ADR-0002`, `ADR-0003`).
- [x] **Phase 12: Neon Gate-6 Adversarial Review, 376-Scenario Blast Radius Proof & Camera-Ready arXiv Bundle (Neon High & Overseer)** - Execute Thermo-Nuclear Code Judo, 376-scenario Blast Radius proof, 258-check Zero-Hallucination sensor, PaperVizAgent (`97.72/100`), ScholarPeer (`9.0/10`), compile 11-page `prism_ann_paper.pdf`, and push nudges `ENH-0006`–`ENH-0009` to Software Factory (`ADR-0000`, `ADR-0001`, `ADR-0002`, `ADR-0003`).

### Phase 13: Pipeline Integrity Fixes: provenance harness, remove scripted Brake 2/3 scores, guard destructive init (ADR-0000, ADR-0004)

**Goal:** Close the v1 failure modes structurally before any v2 measurement (`ADR-0004`).
**Requirements**: INT-01 raw-record harness + recompute; INT-02 no literal scores or verdicts in audit scripts; INT-03 `init-prism-ann --force` guard; INT-04 honest model labels
**Depends on:** Phase 12
**Plans:** 3 plans

Plans:

- [x] 13-01: `bench/harness.py` (raw JSONL per query) + `bench/recompute.py` (bit-for-bit summary) + unit tests (`ADR-0004`).
- [x] 13-02: Strip literal scores/verdicts from `run_prism_paperviz_audit.py` / `run_prism_scholarpeer_review.py`; turn them into checks that review files exist and match artifact SHA-256 (`ADR-0004`).
- [x] 13-03: Guard `research_factory.py init-prism-ann` with `--force`; replace Argon/Hydrogen/Neon labels with the actual invoked model options (`ADR-0000`).

### Phase 14: Real-Baseline Confirmatory Evaluation: BEIR Quora + MiniLM, FAISS/ACORN/hnswlib/pgvector, real SpiceDB, frozen algorithm (ADR-0001, ADR-0002, ADR-0003, ADR-0004)

**Goal:** Run the one confirmatory evaluation in `experiments/v2/PROTOCOL_v2.md` at the frozen SHA in `FREEZE.md`, on real data and real engines (`ADR-0001`, `ADR-0002`, `ADR-0003`, `ADR-0004`).
**Requirements**: EVAL2-01 BEIR Quora + MiniLM corpus/queries; EVAL2-02 real baselines (FAISS HNSW+IDSelector, FAISS ACORN if present, hnswlib, pgvector 0.8); EVAL2-03 real SpiceDB oracle + timing; EVAL2-04 3 seeds + CIs; EVAL2-05 deviations table
**Depends on:** Phase 13
**Plans:** 4 plans

Plans:

- [x] 14-01: Environment: `faiss-cpu`, `sentence-transformers`, `psycopg`, `authzed`; Homebrew `spicedb`, `postgresql`, `pgvector`; record versions in `results/v2/ENVIRONMENT.md` (`ADR-0004`).
- [x] 14-02: Dataset build: BEIR Quora download, MiniLM encoding (cached `.npy`), hierarchy overlays (random + cluster-aligned), exact ground truth (`ADR-0004`).
- [x] 14-03: Smoke run on a 20k subset (ledger: smoke), then the single confirmatory run H1v2–H4v2 (ledger: confirmatory) (`ADR-0001`, `ADR-0002`, `ADR-0003`).
- [x] 14-04: Figures and paper §5 rewritten from `results/v2/summary.json` only. Rename to "Zanzibar-style ReBAC" if SpiceDB isn't the measured path. Theorems 2–4 become propositions. Add a Protocol Deviations table (`ADR-0004`).

### Phase 15: Fresh Independent Review: provenance-first audit, runtime Brake 2/3 reviews of PDF and figures (ADR-0000, ADR-0004)

**Goal:** A reviewer with no prior context audits provenance first, then writes Brake 2/3 reviews by reading the compiled PDF and figures (`ADR-0000`, `ADR-0004`).
**Requirements**: REV2-01 trace 3+ headline numbers to code + raw records; REV2-02 rerun `bench/recompute.py`; REV2-03 written figure/peer reviews with no pre-set scores
**Depends on:** Phase 14
**Plans:** 1 plan

Plans:

- [x] 15-01: Provenance-first audit + runtime reviews -> `results/v2/review/` (`ADR-0004`).

### Phase 16: Factory Overseer: ENH-0013..0016 provenance sensors, honest model labels, local PR package for human review (ADR-0000, ADR-0004)

**Goal:** Encode the retrospective's lessons as factory sensors and prepare the branch for human review, without pushing (`ADR-0000`, `ADR-0004`).
**Requirements**: FAC-01 ENH-0013 dynamic report interpolation; FAC-02 ENH-0014 raw-record provenance sensor; FAC-03 ENH-0015 literal-score sensor; FAC-04 ENH-0016 honest model routing; FAC-05 one test per sensor; FAC-06 local PR description
**Depends on:** Phase 13 (runs in parallel with 14–15)
**Plans:** 1 plan

Plans:

- [x] 16-01: Implement and test ENH-0013..0016 on `feat/research-factory-enhancements`; write `PR_DESCRIPTION.md` for human review (`ADR-0000`).

### Phase 17: Exploratory Dev-Split Engineering (E1-E3): Geometric H-HNSW v2 bridges, local-stall Mode-3 guard, 4-way InitEntryPortals ablation, C++ NEON/CRoaring kernel (ADR-0002, ADR-0003, ADR-0005)

**Goal:** Close Phase 15 peer-review technical gaps on a held-out dev split before freezing v3 (`ADR-0002`, `ADR-0003`, `ADR-0005`).
**Requirements**: E1 geometric intra-container/magnet k-NN bridges + local-stall Mode-3 guard; E2 4-way InitEntryPortals ablation; E3 C++ NEON/CRoaring Mode-3 & H-HNSW kernel (`bench/prism_ckernel.cpp`) + parity tests; dev-split tau_high calibration
**Depends on:** Phase 16
**Plans:** 3 plans

Plans:

- [x] 17-01: Implement Geometric Intra-Container & Intra-Magnet Bridges (`H-HNSW v2`) + Local-Stall Mode-3 Guard (`ADR-0002`, `ADR-0005`).
- [x] 17-02: Implement C++ NEON/`CRoaring` kernel (`bench/prism_ckernel.cpp` -> `libprism_ckernel.dylib`) for Mode 3 interval scan & C++ `H-HNSW`/`ACORN-GLS` traversal with `0 FP / 0 FN` parity unit tests (`ADR-0003`, `ADR-0005`).
- [x] 17-03: Run exploratory dev-split evaluation (`100k` BEIR Quora dev queries only, logged as `exploratory` in `results/run_ledger.md`): 4-way `InitEntryPortals` ablation (`E2`), geometric bridge degree/$\tau_{\text{high}}$ sweep, and C++ Mode-3 vs. BLAS latency proof (`ADR-0004`, `ADR-0005`).

### Phase 18: v3 Algorithm Freeze & Pre-Registration: FREEZE_v3.md and experiments/v3/PROTOCOL_v3.md before confirmatory runs (ADR-0004, ADR-0005)

**Goal:** Lock final v3 algorithm hashes (`src/modules/prism_ann/*.py` + `bench/prism_ckernel.cpp`) in `FREEZE_v3.md` and pre-register falsifiable v3 hypotheses (`H1v3`–`H5v3`) in `experiments/v3/PROTOCOL_v3.md` prior to any confirmatory query (`ADR-0004`, `ADR-0005`).
**Requirements**: FRZ-01 `FREEZE_v3.md`; FRZ-02 `experiments/v3/PROTOCOL_v3.md` committed before Phase 19
**Depends on:** Phase 17
**Plans:** 1 plan

Plans:

- [x] 18-01: Write and commit `FREEZE_v3.md` and `experiments/v3/PROTOCOL_v3.md` (`ADR-0004`, `ADR-0005`).

### Phase 19: Single Frozen Multi-Corpus Confirmatory Evaluation (E4-E5): 2 real corpora, Postgres-backed SpiceDB, ACORN-1 & ACORN-gamma, FAISS, hnswlib, pgvector, v3 figures & paper rewrite (ADR-0001, ADR-0002, ADR-0003, ADR-0004, ADR-0005)

**Goal:** Execute one frozen 3-seed confirmatory benchmark (`v3-confirmatory-001`) across 2 real public corpora, persistent PostgreSQL-backed SpiceDB + memory SpiceDB, FAISS, upstream C++ `ACORN-1` & `ACORN-gamma`, `hnswlib`, `pgvector 0.8.7`, and `Qdrant` (if native), then regenerate `v3_fig*` and rewrite `paper/prism_ann.tex` strictly from `results/v3/summary.json` (`ADR-0001`, `ADR-0002`, `ADR-0003`, `ADR-0004`, `ADR-0005`).
**Requirements**: E4 2nd real corpus + Postgres-backed SpiceDB; E5 `ACORN-gamma` + `Qdrant` + 4-way portal ablation; raw JSONL + bit-for-bit `recompute.py`; v3 figures & paper compile
**Depends on:** Phase 18
**Plans:** 3 plans

Plans:

- [x] 19-01: Prepare 2nd real public corpus (encoded & cached, strictly disjoint queries) + persistent PostgreSQL-backed SpiceDB & upstream `ACORN-gamma` wrappers (`ADR-0004`, `ADR-0005`).
- [x] 19-02: Execute single frozen confirmatory run `v3-confirmatory-001` (`results/v3/raw/*.jsonl` -> `results/v3/summary.json`) and verify `recompute --check` + `FREEZE_v3.md` (`ADR-0004`, `ADR-0005`).
- [x] 19-03: Generate `paper/figures/v3_fig*.{pdf,png}`, rewrite `paper/prism_ann.tex`, recompile `prism_ann_paper.pdf` & `prism_ann_arxiv_package.tar.gz` (`ADR-0004`, `ADR-0005`).

### Phase 20: Fresh Independent v3 Review & Submission Package: provenance-first audit, runtime Brake 2/3 reviews of v3 PDF & figures (ADR-0000, ADR-0004, ADR-0005)

**Goal:** Fresh independent `pro` reviewer verifies v3 raw-record provenance, C++ kernel parity, all 2-corpus numbers, and writes fresh Brake 2 & Brake 3 reviews targeting submission readiness (`ADR-0000`, `ADR-0004`, `ADR-0005`).
**Requirements**: REV3-01 provenance-first raw trace; REV3-02 runtime `results/v3/review/{figure_review,peer_review,REVIEW_SUMMARY}.md`; REV3-03 zero blockers & factory sensor pass
**Depends on:** Phase 19
**Plans:** 1 plan

Plans:

- [ ] 20-01: Fresh independent v3 provenance + figure + peer review -> `results/v3/review/` (`ADR-0004`, `ADR-0005`).

---

## Phase Details

### Phase 1: Local Algorithmic Engine & LoCoMo Benchmark Validation

**Goal**: Build a standalone local prototype of EpiGraph, implement baseline systems, and quantitatively evaluate performance across all 10 multi-session conversations in LoCoMo (`ADR-0000`).  
**Depends on**: Nothing (Initial Phase)  
**Requirements**: CORE-01..CORE-08, BENCH-01..BENCH-05  
**Plans**:

- [x] 01-01: Build modular engine (`src/embeddings.py`, `src/bm25.py`, `src/graph_memory.py`, `src/rrf.py`, `src/epigraph_pipeline.py`) (`ADR-0000`).
- [x] 01-02: Implement baselines (`baselines/vector_rag.py`, `baselines/bm25_baseline.py`, `baselines/static_graph_rag.py`) (`ADR-0000`).
- [x] 01-03: Create automated runner `run_locomo_benchmark.py` and generate empirical evaluation report (`ADR-0000`).

### Phase 2: Distributed Dual-Store & Ingestion Reliability

**Goal**: Connect the local algorithmic engine to production distributed storage engines: Redis Stack and Neo4j Enterprise GDS decoupled via Redis Streams (`ADR-0000`).  
**Depends on**: Phase 1  
**Requirements**: DIST-01..DIST-04  
**Plans**:

- [x] 02-01: Implement Redis Stack adapter with RedisJSON documents and RediSearch HNSW indexing (`ADR-0000`).
- [x] 02-02: Implement Neo4j GDS driver with Cypher queries for directed `SUPERSEDES` and `CORROBORATES` edges (`ADR-0000`).
- [x] 02-03: Implement Redis Streams ingestion worker with retry logic and Dead Letter Queue (`ADR-0000`).
- [x] 02-04: Implement incremental HNSW + DBSCAN entity deduplication for the background Dreaming worker (`ADR-0000`).

### Phase 3: Longitudinal SCDP Simulation & Ablation Suite

**Goal**: Execute a simulated 90-day continuous deployment protocol (100 sessions across 4 domains) to measure God Node stability, CATD scaffolding retention, and component ablations (`ADR-0000`).  
**Depends on**: Phase 1  
**Requirements**: EVAL-01..EVAL-04  
**Plans**:

- [x] 03-01: Build longitudinal simulation harness (`run_longitudinal_simulation.py`) (`ADR-0000`).
- [x] 03-02: Run comparative Scaffolding Test: CATD vs. Wall-clock exponential decay over simulated 90 days (`ADR-0000`).
- [x] 03-03: Run LongMemEval Knowledge Update evaluation suite for `SUPERSEDES` validation (`ADR-0000`).
- [x] 03-04: Run component ablations (U-PPR vs. static PPR, Grace Period variations $N=1, 2, 4, 8$) (`ADR-0000`).

### Phase 4: LaTeX Manuscript Preparation & arXiv Pre-Print Submission

**Goal**: Author the complete publication-grade research manuscript in LaTeX, compile camera-ready figures, and package for arXiv (`ADR-0000`).  
**Depends on**: Phase 1, Phase 3  
**Requirements**: PAPER-01..PAPER-04  
**Plans**:

- [x] 04-01: Set up LaTeX document repository and `references.bib` (`ADR-0000`).
- [x] 04-02: Render professional vector figures (`ADR-0000`).
- [x] 04-03: Write full paper sections (`ADR-0000`).
- [x] 04-04: Compile final PDF and prepare arXiv submission package (`ADR-0000`).

### Phase 5: Closed-Loop Downstream LLM Generation QA Benchmark

**Goal**: Evaluate downstream generative QA accuracy across LoCoMo questions measuring Token F1, Exact Match (EM), and ROUGE-L (`ADR-0000`).  
**Depends on**: Phase 1, Phase 4  
**Requirements**: GEN-01..GEN-03  
**Plans**:

- [x] 05-01: Build closed-loop generation evaluator `run_closed_loop_qa.py` (`ADR-0000`).
- [x] 05-02: Execute closed-loop QA benchmark (`results/closed_loop_qa_results.json`) (`ADR-0000`).
- [x] 05-03: Format results into `paper/main.tex` (`ADR-0000`).

### Phase 6: LongMemEval Knowledge Update & Contradiction Resolution

**Goal**: Construct and evaluate a multi-session knowledge mutation benchmark to test directed `SUPERSEDES` edge filtering (`ADR-0000`).  
**Depends on**: Phase 1, Phase 2  
**Requirements**: KUPD-01..KUPD-02  
**Plans**:

- [x] 06-01: Build knowledge update test harness `run_knowledge_update_eval.py` (`ADR-0000`).
- [x] 06-02: Run comparative benchmark: Flat Vector vs. BM25 vs. EpiGraph `SUPERSEDES` filtering (`ADR-0000`).
- [x] 06-03: Save results to `results/knowledge_update_results.json` (`ADR-0000`).

### Phase 7: Hyperparameter Sensitivity Landscape & Embedding Invariance

**Goal**: Perform systematic sensitivity analysis on PageRank damping ($d$) and RRF smoothing ($k$) (`ADR-0000`).  
**Depends on**: Phase 1  
**Requirements**: SENS-01..SENS-02  
**Plans**:

- [x] 07-01: Implement parameter sweep harness `run_sensitivity_analysis.py` (`ADR-0000`).
- [x] 07-02: Generate sensitivity contour/line plot (`paper/figures/fig5_sensitivity_analysis.png`) (`ADR-0000`).

### Phase 8: Manuscript Integration & Extended Camera-Ready Package

**Goal**: Integrate all empirical results into `paper/main.tex`, update BibTeX, and run final automated verification (`ADR-0000`).  
**Depends on**: Phase 5, Phase 6, Phase 7  
**Requirements**: PAPER-05  
**Plans**:

- [x] 08-01: Update `paper/main.tex` with downstream QA and knowledge mutation sections (`ADR-0000`).
- [x] 08-02: Update `verify_hallucinations.py` and run full verification (`ADR-0000`).
- [x] 08-03: Commit and freeze milestone release (`ADR-0000`).

### Phase 9: Literature Recon, ADR-to-Theorem Minting & Pre-Registered Protocols (Argon High)

**Goal**: Conduct comprehensive 2018–2026 literature survey on ReBAC/Zanzibar in vector search (`HoneyBee`, `Policy-Aware Vector Search`) and Filtered HNSW (`ACORN`, `UNG`, `SeRF`, `UNIFY`, `SIEVE`, `Curator`, `FANNBench/GLS`), mint `ADR-0001` through `ADR-0003` using Design-It-Twice mapped 1:1 to Theorems 1–4, synchronize `CONTEXT.md` & `GLOSSARY.md`, and pre-register protocols `H1`–`H4` in Git (`ADR-0000`, `ADR-0001`, `ADR-0002`, `ADR-0003`).  
**Depends on**: Phase 8  
**Requirements**: PRISM-01, PRISM-02, PRISM-03  
**Plans**:

- [x] 09-01: Compile verified 18-paper survey in `literature/survey.md` and 1:1 Code-to-LaTeX symbol table in `GLOSSARY.md` (`ADR-0000`).
- [x] 09-02: Mint `ADR-0001` (SpiceDB Subtractive UBP -> Theorem 1), `ADR-0002` (Ancestor-Stitched HNSW & `ACORN-GLS` -> Theorems 2 & 3), and `ADR-0003` (Z-Ordered Roaring-SIMD Tri-Modal Planner -> Theorem 4) (`ADR-0001`, `ADR-0002`, `ADR-0003`).
- [x] 09-03: Lock pre-registered hypothesis protocols `experiments/H1..H4/protocol.md` in Git prior to execution (`ADR-0000`).

### Phase 10: Deep Module Build & Tracer-Bullet Seam TDD (Hydrogen High)

**Goal**: Implement the `Prism-ANN` Deep Modules (`src/modules/prism_ann/ubp_resolver.py`, `hnsw_gls.py`, `trimodal_planner.py`, `index.py`) and verify all mathematical invariants via `tests/test_prism_ann.py` (`ADR-0001`, `ADR-0002`, `ADR-0003`).  
**Depends on**: Phase 9  
**Requirements**: PRISM-04, PRISM-05, PRISM-06  
**Plans**:

- [x] 10-01: Implement `ZanzibarAuthGraph`, `upward_boundary_prune` ($\mathcal{P}_{\text{UBP}}$), and $O(1)$ zero-write edge revocation in `ubp_resolver.py` (`ADR-0001`).
- [x] 10-02: Implement `AncestorStitchedHNSW` ($M_{\text{bridge}}=4$) and `search_hnsw_gls` (`POPCNT` $\hat{S}_{\text{loc}}(v)$ adaptive traversal) in `hnsw_gls.py` (`ADR-0002`).
- [x] 10-03: Implement `RoaringRunBitmap`, `ZOrderedCorpus`, `contiguous_simd_sq8_scan`, and `TriModalQueryPlanner` in `trimodal_planner.py` + `tests/test_prism_ann.py` (`ADR-0003`).

### Phase 11: 10-Baseline Empirical Benchmark Suite & Academic Plotting (Hydrogen High)

**Goal**: Execute `run_prism_ann_benchmarks.py` across all 10 baselines/ablations (`B1..B7`, `Ablation 1..2`, `Prism-ANN Full`) for `H1`–`H4`, update `findings.md` & `research-state.yaml`, and render 4 dual-panel vector PDF figures via `generate_prism_ann_plots.py` (`ADR-0001`, `ADR-0002`, `ADR-0003`).  
**Depends on**: Phase 10  
**Requirements**: PRISM-07, PRISM-08  
**Plans**:

- [x] 11-01: Run `H1`–`H4` benchmark suite and serialize deterministic metrics to `results/prism_ann_benchmark_results.json` (`ADR-0001`, `ADR-0002`, `ADR-0003`).
- [x] 11-02: Generate `fig1_prism_selectivity_sweep.pdf` .. `fig4_prism_revocation_throughput.pdf` and author 11-page two-column manuscript `paper/prism_ann.tex` (`ADR-0000`, `ADR-0001`, `ADR-0002`, `ADR-0003`).

### Phase 12: Neon Gate-6 Adversarial Review, 376-Scenario Blast Radius Proof & Camera-Ready arXiv Bundle (Neon High & Overseer)

**Goal**: Execute Gate-6 Thermo-Nuclear Code Quality Review, 376-scenario Blast-Radius live fuzzer proof (`verify_blast_radius_ubp.py`), 3-Brake Academic Audit (`verify_prism_hallucinations.py`, `PaperVizAgent`, `ScholarPeer`), compile `prism_ann_paper.pdf` & `prism_ann_arxiv_package.tar.gz`, and codify learned sensors `ENH-0006`–`ENH-0009` in `/Users/tejap/software_factory` (`ADR-0000`, `ADR-0001`, `ADR-0002`, `ADR-0003`).  
**Depends on**: Phase 11  
**Requirements**: PRISM-09, PRISM-10  
**Plans**:

- [x] 12-01: Apply Thermo-Nuclear Code Judo across `src/modules/prism_ann/` and verify 0 leaks / 0 dropped docs across 376 adversarial DAG scenarios in `verify_blast_radius_ubp.py` (`ADR-0001`, `ADR-0002`, `ADR-0003`).
- [x] 12-02: Pass Brake 1 (`258/258` row-scoped metric checks, `0.0%` discrepancy, `18/18` verified citations), Brake 2 (`PaperVizAgent` `97.72/100`), and Brake 3 (`ScholarPeer` `9.0/10 STRONG ACCEPT`) (`ADR-0000`).
- [x] 12-03: Forward Gate-6 sensor nudges (`ENH-0006`–`ENH-0009`) to `@factory-overseer` and commit onto `/Users/tejap/software_factory` (`feat/research-factory-enhancements`, `50/50` tests passing) (`ADR-0000`).
