---
gsd_state_version: '1.0'
milestone: v6.1
milestone_name: Prism-ANN v3.1, v3.2 & v3.3 Two-Round + Dynamic-DAG/E2E Reviewer Audit (R1-R11), Theorem 1/2 Exactness, Literature Reconciliation & Accessible Explainer Suite
current_phase: 22
current_phase_name: Second-Round & Third-Round Research Audit (R1-R11), Dynamic Multi-Parent DAG Support & Literature Reconciliation
status: milestone_6_complete_verified
last_updated: '2026-11-23T10:50:00-06:00'
progress:
  total_phases: 22
  completed_phases: 22
  total_plans: 62
  completed_plans: 62
  percent: 100
---

# Project State: EpiGraph (`EngramRAG`) & `Prism-ANN` (Milestone 6 — ADR-0005 & ADR-0006)

## Current Position
- **Completed**: All 22 Phases (62/62 plans, 100%) — including `v3-confirmatory-001` (`169,810` raw records, `11/11` predictions supported), `v3.1-reviewer-audit-001` (`R1`–`R5`, `22,533` raw records, `5/5` supported), `v3.2-reviewer-audit-001` (`R6`–`R8`, `6,821` raw records, `PR6` supported, `PR7`/`PR8` transparently falsified), and `v3.3-reviewer-audit-002` (commit `7ce7d44`, `R9a`, `R9b`, `R10`, `R11`, `8,524` raw records, `PR9a`/`PR9b`/`PR11` supported, `PR10` transparently falsified on `>=10x` live-RPC cutoff at `S=0.01%`).
- **Algorithm & Kernel Freezes**: `FREEZE.md` (v2, `5/5`), `FREEZE_v3.md` (v3, `7/7`), `FREEZE_v3_1.md` (v3.1/v3.2, `8/8`), and `FREEZE_v3_3.md` (`9/9` including `src/modules/prism_ann_v3/dynamic_dag_ubp.py`) all match 100%.

## Cumulative Evidence Scorecard (`207,688` Total Raw JSONL Records)
1. **Confirmatory `v3.0` (`v3-confirmatory-001`, `169,810` Raw Records, `11/11` `P1a`–`P5` SUPPORTED)**:
   - `P1a`/`P1b`/`P1c`: `0/1,200` mismatches (`600` memory + `600` persistent PG17 SpiceDB), `100.0%` within Theorem 1 bound, `225.9×` (mem) / `278.2×` (PG) local speedup (`29.1×` / `28.2×` live RPC).
   - `P2a`/`P2b`/`P2c`: `v3-geom-M8` (`+32 B/n`, `+1.91%` graph RAM) hits `66.60%–95.25%` (Quora) / `75.57%–93.35%` (NQ); `v3-full-guard-sq8` (`+416 B/n`, `+24.8%` w/ auxiliary `200.8 MB` SQ8 buffer) empirically hits `100.00%` at $S \le 1\%$ in `0.05–0.11 ms` kernel.
   - `P3a`/`P3b`: `r<=0.5` Guard hits `97.17%` (`0.35 ms` Quora) / `96.42%` (`0.17 ms` NQ); `r>=2.0` GLS cuts evals `3.82×` / `3.11×`.
   - `P4a`/`P4b`: Persistent PG17 SpiceDB revocation `67.28 ms` (`0` vector writes) vs. PG17/`pgvector 0.8.7` `UPDATE` `179.4 s` (**`2,666.2×`** faster).
   - `P5`: `H5v3` 0-portal `H-HNSW v2` retains `101.0% / 102.3% / 101.0%` of recall lift over `FAISS M=16`.
2. **First-Round Audit `v3.1` (`v3.1-reviewer-audit-001`, `R1`–`R5`, `22,533` Raw Records, `5/5` `PR1`–`PR5` SUPPORTED)**:
   - `PR1` (`R1`): `10,000` hierarchy trials (`5,000` std + `5,000` alternating `GRANT<->DENY`) -> `0` FP, `0` FN, `100.0%` bound satisfaction (`max 249` std / `164` alt).
   - `PR2` (`R2`, $S=0.01\%$): `v3-geom-M8` reaches `85.73%` (`0.538 ms` Quora) / `92.27%` (`0.273 ms` NQ) vs. `acorn-1` `0.33%` / `0.40%`; `v3-full-guard-sq8` reaches `100.00%` in `0.049 ms` (Quora) / `0.032 ms` (NQ), `0/1,200` leaks.
   - `PR3` (`R3`, 6-way Mode-3 attribution at $S=1.0\%$): Cold LLC (`64 MB` flush/query) achieves **`29.40×` total speedup** (`0.0976 ms` vs. `2.8695 ms`) = `7.35×` Z-order $\times$ `2.85×` `SQ8` $\times$ `7.46×` ARM NEON (`0.7281 ms` cold scalar SQ8); warm cache achieves **`34.18×`** (`0.0812 ms` vs. `2.7758 ms`).
   - `PR4` (`R4`): PG17 SpiceDB single-edge revocation across `128 -> 490,419` chunks stays flat at `0.74–1.66 ms` (`0` vector writes); `4`-thread local snapshot-swap concurrency test across `11,244` C++ queries (`5,205` pre + `6,039` post; `4` crossing cutoff) yields `0 / 6,039` post-swap leaks (`6.82 ms` PG17 commit, `0.091 ms` snapshot compile+swap).
   - `PR5` (`R5`, `+1k..+25k` vectors onto `500k` Quora): `5.30–23.93 µs/vec` online delta append, `1.30–2.36 s` background Z-order compaction, `116.30–121.61 ms` C++ CSR ID remap.
3. **Second-Round Audit `v3.2` (`v3.2-reviewer-audit-001`, `R6`–`R8`, `6,821` Raw Records)**:
   - `PR6` (`R6`, **SUPPORTED**): `5,000` permission/deny/revocation trials across `36` generated multi-parent DAGs (`3` initial + `33` replacements across `(4,5),(6,4),(8,4)`, `>= 672` / mean `1,170.0` secondary edges) -> `0 / 5,000` mismatches (`0` FP, `0` FN; median `20.0`, max `387` tokens).
   - `PR7` (`R7`, **FALSIFIED** on strict `<=0.35 ms` / `>=100×` fragmented-L5 thresholds; `0/1,500` leaks): Track 1 pure C++ vs. **composed request-latency estimate** (`H1v3` constants + filter compile + Track 1, w/ `H1v3` `CRoaring` bitmap overlap `~0.13–0.95 ms`): `v3-geom-M8` hits `87.4% / 79.2% / 71.4% / 73.6% / 93.0%` R@10 across $S \in \{0.01\%, 0.1\%, 0.5\%, 1\%, 5\%\}$ vs. `0.2%–31.2%` `acorn-1` & `6.0%–89.0%` in-repo `racorn-1-fallback` C++ proxy; `v3-full-guard-f32` (`0` extra vec RAM, `0.0206–0.4527 ms` Track 1) & `-sq8` (`0.0380–0.4344 ms` Track 1) hit `100.0%` R@10 at $S \le 1\%$ (`24.12×–28.07×` PG17 / `80.61×–163.75×` mirror composed estimate).
   - `PR8` (`R8`, **FALSIFIED** on strict `<=0.25 ms` exact-FP32 cutoff at fragmented $S=1.0\%$): `M_rerank=64` has `100.0%` mathematical guarantee at $S=0.01\%$ (`n_cand<=48`); `SQ8`+`M_rerank>=32` (`32, 64, 128`) achieves `100.0%` empirical R@10 at all $S \le 1.0\%$ (`>= 99.8%` criterion met, whereas `M=10` drops to `97.0%–98.0%`); exact `FP32` takes `0.0035 / 0.0235 / 0.1964 / 0.3289 ms` (`0.3289 ms > 0.25 ms` at `S=1%`).
4. **Third-Round Audit `v3.3` (`v3.3-reviewer-audit-002`, commit `7ce7d44`, `R9a`, `R9b`, `R10`, `R11`, `8,524` Raw Records)**:
   - `PR9a` (`R9a`, **SUPPORTED**): `1,000` genuinely independent multi-parent DAGs (`0` DAG reuse), `5,000` dynamic structural mutations (post-index `add_hierarchy_edge` onto denied parent, cross-parent & same-parent $P \to C$ / $P \to X \to C$ unlinks, final-path unlink, deny removal, grant/re-grant) -> **`0 / 5,000` FP, `0` FN, `0` search hit leaks**.
   - `PR9b` (`R9b`, **SUPPORTED**): **`13 / 13`** live SpiceDB v1.57.1 scenarios verified against `LookupResources` & `CheckPermission` (logging `write_zed_token`, `selected_read_revision`, `indexed_posting_revision`, oracle/compiled/search IDs, `latency_ms`, and `S10` fail-closed `StaleOrMissingSnapshotError` / `safe_leaf_fallback` behavior; `0` mismatches).
   - `PR11` (`R11`, **SUPPORTED**): `1,760` 8-thread concurrent live SpiceDB reads (`423` `at_exact_snapshot(zt_pre)` + `1,337` `at_least_as_fresh(zt_post)`, `1.481 ms` med RPC, `0.116 ms` index med search) -> **`0` oracle mismatches, `0` post-revocation leaks, `0` stale errors**.
   - `PR10` (`R10`, **FALSIFIED** on strict `>= 10x` live-RPC cutoff at `S=0.01%`, `0` total leaks across `1,750` queries): Single-timer **measured end-to-end latency** (live SpiceDB + filter compile + in-timer `SQ8` quantization + C++ search) achieves **`6.15×–6.50×`** at $S=0.01\%$ (`1.53–1.62 ms` vs `9.95 ms` `3`-leaf `LookupResources`) and **`11.50×–96.87×`** at $S \ge 0.1\%$ (`1.50–2.62 ms` vs `17.63–216.07 ms`), while mirror-cached E2E achieves **`185.22×–437.38×`** to $S=1\%$ and **`505.08×`** at $S=5\%$ (`0.0384 ms` `FP32` / `0.0537 ms` `SQ8` at $S=0.01\%$). Matched-recall `efSearch=32..512` sweep (`1,000` queries) shows `v3-geom-M8` reaching `98.0%` at $S=0.5\%$ in `1.968 ms` vs `FAISS` `69.6%` in `2.211 ms`.

## Verification Status
- `reproduce_clean_machine.sh --verify`: **ALL GATES PASSING (EXIT 0)**.
- `bench/recompute{,_v3,_v3_1,_v3_2,_v3_3}.py --check`: **5/5 BIT-FOR-BIT MATCH (`207,688` cumulative raw JSONL records + `62,410` v2 records)**.
