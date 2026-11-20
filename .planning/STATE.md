---
gsd_state_version: '1.0'
milestone: v4.0
milestone_name: Prism-ANN v2 Provenance-Verified Real-Baseline Evaluation (ADR-0004)
current_phase: 14
current_phase_name: Real-Baseline Confirmatory Evaluation (BEIR Quora + MiniLM, FAISS/ACORN/hnswlib/pgvector, Real SpiceDB, Frozen Algorithm)
status: phase_14_complete_awaiting_phase_15
last_updated: '2026-11-20T15:35:00-06:00'
progress:
  total_phases: 16
  completed_phases: 15
  total_plans: 48
  completed_plans: 47
  percent: 98
---

# Project State: EpiGraph (`EngramRAG`) & `Prism-ANN` (Milestone 4 — ADR-0004)

## Current Position
- **Completed**: Phases 1–12 (M1–M3, with M3 v1 evaluation superseded by `ADR-0004`), Phase 13 (`13-01`..`13-03` provenance harness, literal-verdict removal, `--force` guard), Phase 14 (`14-01`..`14-04` real-engine confirmatory run `v2-confirmatory-002`, v2 figures, rewritten 10-page manuscript), and Phase 16 (`16-01` factory sensors).
- **Next Phase**: **Phase 15 (`15-01`)** — Fresh Independent Review (provenance-first audit + runtime Brake 2/3 reviews of `paper/prism_ann.pdf` and `paper/figures/v2_*.png` -> `results/v2/review/`).
- **Algorithm Freeze**: `FREEZE.md` SHA-256 hashes match `5/5` files (`freeze_match = YES`).

## Confirmatory v2 Scorecard (`v2-confirmatory-002`, Full `N=522,931` BEIR Quora MiniLM `384-d`, 3 Seeds, `62,410` Raw Records)

| Prediction | Criterion (`PROTOCOL_v2.md`) | Measured (`results/v2/summary.json`) | Verdict |
|---|---|---|---|
| **P1a** | `0` mismatches vs. live SpiceDB ($\ge 200$ principals) | `0` doc / `0` chunk mismatches (`600` principals) | **SUPPORTED** |
| **P1b** | $|T_{\text{UBP}}^+| \le k_0 + m(b-1)L$ in `100%` | `100.0%` (`600/600`); med `76`, max `296` tokens | **SUPPORTED** |
| **P1c** | Broad ($\ge 1\text{k}$ docs) median UBP+bitmap $\ge 10\times$ faster | `0.310 ms` vs. `70.150 ms` = **`226.5×`** (strict live RPC: `2.089 ms` = **`33.6×`**) | **SUPPORTED** |
| **P2a** | `prism-graph-only` $\ge$ `faiss-hnsw-M16` $+10$ pts at $S \le 0.5\%$ | `S=0.1%`: `+22.25 ± 2.54` pts; `S=0.5%`: `+23.49 ± 2.19` pts | **SUPPORTED** |
| **P2b** | `prism-graph-only` within `-2` pts of `acorn-1` at $\le 1.0\times$ evals | Wins recall at all $S$ (`+27.4` to `+49.4` pts), but dist ratio `1.04×–58.50×` | **FALSIFIED** |
| **P2c** | `prism-full` (Mode 3) $\ge 99\%$ at $S \le 0.5\%$ (completeness) | `100.00 ± 0.00%` at `S=0.1%` and `S=0.5%` (`1.10–1.82 ms`) | **SUPPORTED** |
| **P3a** | At $r \le 0.5$ ($S=2\%$), `prism-graph-only` $\ge$ `faiss-hnsw-M16` $+10$ pts | `+17.65 ± 3.09` pts (`23.34%` vs. `5.68%`, $n=735$) | **SUPPORTED** |
| **P3b** | At $r \ge 2$, `prism-graph-only` $\le 0.8\times$ `static-2hop` evals, R@10 $\ge -1$ pt | `0.188×` (`5.33×` fewer: `588.8` vs. `3136.1`), but R@10 `-2.00` pts (`97.10%` vs. `99.09%`) | **FALSIFIED** |
| **P4a** | Revoking `1` SpiceDB edge ($\ge 1\text{k}$ docs) uses `0` vector writes | `0` writes, median `76.05 ms` (`1,024` docs / `153,600` chunks, $n=5$) | **SUPPORTED** |
| **P4b** | Real PostgreSQL/`pgvector` `UPDATE` $\ge 100\times$ slower than P4a | `182,526.4 ms` (`182.5 s`) vs. `76.05 ms` = **`2,400.1×`** | **SUPPORTED** |

## Verification Status
- `tests/test_bench_provenance.py`: **9/9 passing (0 skipped)**, including bit-for-bit `test_committed_summary_matches_raw_exactly`.
- `verify_prism_hallucinations.py` (Brake 1 v2): **127/127 checks passing, 0 errors**.
- Brake 2 (`run_prism_paperviz_audit.py`) & Brake 3 (`run_prism_scholarpeer_review.py`): intentionally pending fresh independent Phase 15 reviewer (`results/v2/review/`).
