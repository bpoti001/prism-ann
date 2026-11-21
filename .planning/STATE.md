---
gsd_state_version: '1.0'
milestone: v5.0
milestone_name: Prism-ANN v3 Geometric H-HNSW v2, C++ ARM NEON Kernel & Multi-Corpus Persistent-SpiceDB Confirmatory Evaluation (ADR-0005)
current_phase: 19
current_phase_name: Single Frozen Multi-Corpus Confirmatory Evaluation, v3 Figures & Manuscript Rewrite
status: phase_19_complete_awaiting_phase_20_review
last_updated: '2026-11-21T08:46:00-06:00'
progress:
  total_phases: 20
  completed_phases: 19
  total_plans: 56
  completed_plans: 55
  percent: 98
---

# Project State: EpiGraph (`EngramRAG`) & `Prism-ANN` (Milestone 5 — ADR-0005)

## Current Position
- **Completed**: Phases 1–16 (M1–M4), Phase 17 (`17-01..17-03` dev-split E1–E3 engineering), Phase 18 (`18-01` `FREEZE_v3.md` & `PROTOCOL_v3.md`), and Phase 19 (`19-01..19-03` BEIR NQ 250k + persistent Postgres SpiceDB + `ACORN-gamma`, single frozen confirmatory run `v3-confirmatory-001`, `v3_fig1..5`, rewritten 11-page manuscript, `238/238` Brake-1 checks).
- **Next Phase**: **Phase 20 (`20-01`)** — Fresh Independent `pro` Review (provenance-first audit + runtime Brake 2/3 reviews of `paper/prism_ann.pdf` and `paper/figures/v3_fig*.png` -> `results/v3/review/`).
- **Algorithm Freezes**: `FREEZE.md` (v2, `5/5`) AND `FREEZE_v3.md` (v3, `7/7`) both match 100%.

## Confirmatory v3 Scorecard (`v3-confirmatory-001`, 2 Corpora, 3 Seeds, `169,810` Raw Records)
- **All 11 pre-registered predictions (`P1a`–`P5`) SUPPORTED**:
  - `P1a`/`P1b`/`P1c`: `0/1,200` mismatches (`600` memory + `600` persistent PostgreSQL 17 SpiceDB), `100%` within Theorem 1 bound, `225.9×` (mem) / `278.2×` (PG) local speedup (`29.1×` / `28.2×` strict live RPC).
  - `P2a`/`P2b`/`P2c`: `v3-geom-M8` hits `66.6%–95.3%` (Quora) / `75.6%–93.4%` (NQ), beating `FAISS M=16`, `v2-ring-chord-M4`, `ACORN-1`, and `ACORN-gamma` ($\gamma=4$, `0.143×` extra L0 RAM); `v3-full-guard-sq8` hits `100.00%` at $S \le 1\%$ in `0.05–0.11 ms` (`3.2×–30.8×` vs BLAS, `725×–2,430×` vs `pgvector`/`hnswlib`).
  - `P3a`/`P3b`: `r<=0.5` Guard hits `97.17%` (`0.35 ms`, Quora) / `96.42%` (`0.17 ms`, NQ); `r>=2.0` GLS cuts evals `3.82×` (Quora) / `3.11×` (NQ) within `-0.99` / `-0.93` pt R@10.
  - `P4a`/`P4b`: Persistent PostgreSQL 17 SpiceDB revocation `67.28 ms` (`0` vector writes) vs PostgreSQL 17/`pgvector 0.8.7` `UPDATE` `179.4 s` (**`2,666.2×`** faster).
  - `P5`: `H5v3` 0-portal `H-HNSW v2` retains `101.0% / 102.3% / 101.0%` of recall lift over `FAISS M=16`.

## Verification Status
- `tests/test_prism_ann.py` + `tests/test_bench_provenance.py` + `tests/test_prism_v3_kernel.py`: **19/19 passing (0 skipped)**.
- `bench/recompute_v3.py --check results/v3/summary.json`: **MATCH (bit-for-bit)**.
- `verify_prism_hallucinations.py` (Brake 1 v3): **238/238 checks passing, 0 errors**.
- Brake 2 & Brake 3 (`results/v3/review/`): pending Phase 20 fresh independent `pro` reviewer.
