# ADR-0006: External Reviewer Audit Protocol (`v3.1 R1–R5`, `v3.2 R6–R8`, `v3.3 R9–R11`, & `v3.4 R12`), Multi-Parent Dynamic DAG Exactness (`Theorem 2`), Atomic Snapshot Publication, and Three-Tier Audience Architecture

- **Status**: `accepted`
- **Date**: 2026-11-23
- **Scope**: `bench/prism_audit_kernel.cpp`, `src/modules/prism_ann_v3/dynamic_dag_ubp.py`, `src/modules/prism_ann_v3/consistent_snapshot_index.py`, `FREEZE_v3_3.md`, `FREEZE_v3_4.md`, `bench/run_reviewer_audit_v3_{1,2,3,4}.py`, `bench/recompute_v3_{1,2,3,4}.py`, `experiments/v3/PROTOCOL_v3_{1,2,3,4}.md`, `docs/ONBOARDING_NEW_GRAD.md`, `docs/ARCHITECTURE_SENIOR_ENGINEER.md`, `docs/RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md`, `paper/prism_ann.tex`
- **Builds Upon**: `ADR-0001` (UBP), `ADR-0002` (`H-HNSW` / `ACORN-GLS`), `ADR-0003` (Z-Ordered Tri-Modal Planner), `ADR-0004` (Raw-Record Provenance), `ADR-0005` (`v3` Confirmatory Evaluation)
- **Mapped Paper Section**: Section III-A (**Theorem 1** Single-Parent Tree Token Bound, **Theorem 2** Multi-Parent Dynamic DAG Exact Set Equivalence & **Corollary 1** Revocation / Atomic Snapshot Consistency), Section V-F (Supplementary Reviewer Audits `R1`–`R12`), Section VI-B (`Veda`, `RACORN`, `Curator`, & `EMA` Novelty Matrix)

## Context
Following the frozen `v3-confirmatory-001` benchmark (`169,810` raw records, `7/7` checksums in `FREEZE_v3.md`), three rounds of external research peer review raised formal, fairness, dynamic-hierarchy, and literature requirements:
1. **First-Round Audit (`v3.1`, `R1`–`R5`, `22,533` raw records)**:
   - `R1`: Adversarial property-based fuzzing of $\mathcal{P}_{\text{UBP}}$ (`10,000` trials: `5,000` standard + `5,000` alternate $L \in [3, 6], b \in [3, 8], k_0 \in [1, 8], m \in [0, 25]$) against an exhaustive leaf oracle (`0/10,000` mismatches; `100.0%` tree bound compliance, med/max `3.0/249` std, `48.0/164` alt).
   - `R2`: Ultra-low selectivity ($S = 0.01\%$, `150` queries/corpus, `0/1,200` leaks) across BEIR Quora (`522,931`) and BEIR NQ (`200,000`).
   - `R3`: 2×2×2 component isolation of Mode 3 separating Z-order contiguous layout (`7.35×`), `SQ8` quantization (`2.85×`), and ARM NEON `vdotq_s32` intrinsics (`7.46×`) under `64 MB` Cold-LLC cache-thrashing sweeps (`29.40×` cold, `0.0976 ms` vs `2.8695 ms`; `34.18×` warm, `0.0812 ms` vs `2.7758 ms`).
   - `R4`: `R4a` Persistent PostgreSQL 17 SpiceDB single-edge deletion scaling (`128` -> `490,419` chunks in `0.74–1.66 ms`, `0` vector writes); `R4b` `4`-thread local integer-version atomic snapshot-swap concurrency (`0.091 ms` swap, `6.82 ms` PG17 commit, `11,244` queries: `5,205` pre-swap / `6,039` post-swap, `4` crossing cutoff, `0/6,039` post-swap leaks). (Note: live SpiceDB `ZedToken` concurrency is tested separately in `v3.3 R11`).
   - `R5`: Dynamic stream ingestion (`+1k`..`+25k` vectors onto `500k` corpus) measuring `5.30–23.93 µs/vec` append, `1.30–2.36 s` compaction, and `116.30–121.61 ms` CSR remap.
2. **Second-Round Audit (`v3.2`, `R6`–`R8`, `6,821` raw records)**:
   - `R6` & **Theorem 1 / Theorem 2 Split**: Separate the tree cardinality bound $k_0 + m(b-1)L$ (**Theorem 1**) from exact set equivalence $\Phi(\mathcal{P}_{\text{UBP}}(u)) = D_{\text{auth}}(u)$ on multi-parent acyclic DAGs (**Theorem 2**). Disclosed scope: `R6` evaluated `5,000` permission trials across `36` generated DAGs (`3` initial + `33` replacements across `(4,5),(6,4),(8,4)`, `min 672`, `mean 1,170.0` secondary edges; `0/5,000` mismatches, med `20.0`, max `387`), exercising grant mutations rather than structural edge deletions.
   - `R7`: Two-Track baseline fairness separating **Track 1** (pure C++ kernel with pre-compiled bitmaps and out-of-timer `SQ8` query quantization) from **Track 2**—a **composed request-latency estimate** from `H1v3` `98.30 / 3.49 / 0.35 ms` medians (which already include `CRoaring` construction overlapping `filter_compile` by `~0.13–0.95 ms`)—across fragmented $L_5$-only principal grants, including an in-repo `racorn-1-fallback` C++ proxy (`github.com/naver/racorn` targets x86-64 AVX2/FMA/F16C `NumKong` on USearch). `PR7` was falsified (`0.4344/0.4527 ms > 0.35 ms` at $S=1\%$; `82.19×/97.72× < 100×`).
   - `R8`: Exact vs. Empirical Recall@10 across `320` queries (`M_rerank=64` mathematical guarantee at $S=0.01\%$ where $N_{\text{cand,max}}=48 \le 64$; `SQ8`+`M>=32` achieving `100.0%` at $S \le 1\%$; `PR8` falsified on exact FP32 latency `0.3289 ms > 0.25 ms` at $S=1\%$).
3. **Third-Round Audit (`v3.3`, `R9a`–`R11`, `8,524` raw records, commit `7ce7d44`) — Addressing Dynamic-DAG Security, Alternate Paths, Fail-Closed Snapshots & Measured E2E Timing**:
   - **Priority Findings 1 & 2 (`src/modules/prism_ann_v3/dynamic_dag_ubp.py`)**: Replaced static lineage stamping and global unlink blacklisting with `DynamicMultiParentAuthGraph` (exact edge-specific `remove_hierarchy_edge` vs. explicit `decommission_subtree` quarantine) and `VersionedLineageCorpus` (`CorpusRevisionSnapshot` atomically binding reachability-exact ancestor `token_bitmaps` + frozen `auth_snapshot` per `zed_token` with `0` vector writes, plus `StaleOrMissingSnapshotError` fail-closed / `safe_leaf_fallback` when expired or unavailable).
   - `R9a`: `1,000` independent DAGs (`0` reuse, `min 105`, `mean 486.0` secondary edges) across `5,000` dynamic mutations (`M1` edge additions, `M2` cross-parent & same-parent $P \to C$ / $P \to X \to C$ diamond unlinks, `M3` final-path unlinks, `M4` deny removals, `M5` grant/re-grants) -> `0` FP, `0` FN, `0` search leaks.
   - `R9b`: `13/13` live native SpiceDB v1.57.1 scenarios (logging `write_zed_token`, `selected_read_revision`, `indexed_posting_revision`, oracle/mask/search IDs, `latency_ms`, and `S10` fail-closed `StaleOrMissingSnapshotError` / `safe_leaf_fallback` parity) -> `0` mask, `0` search, `0` `CheckPermission` mismatches.
   - `R10`: Measured single-timer E2E latency (`750` queries incl. live SpiceDB/mirror RPC + UBP + bitmap + in-timer `SQ8` quant + C++ kernel + `efSearch={32..512}` `1,000`-query sweep, `0` leaks). Reported `PR10` honestly **falsified** at $S=0.01\%$ (`6.15×–6.50× < 10×` live RPC cutoff, while passing `11.50×–96.87×` for $S \ge 0.1\%$ and `185.22×–437.38×` / `505.08×` in mirror mode) and observed in-timer `FP32` beating in-timer `SQ8` for $S \le 0.1\%$.
   - `R11`: `1,760` 8-thread concurrent live SpiceDB reads (`423` pre-rev `at_exact_snapshot`, `1,337` post-rev `at_least_as_fresh`, `1.481 ms` SpiceDB med RPC, `0.116 ms` index med search) -> `0` oracle mismatches, `0` post-rev leaks, `0` stale errors.
   - **Nov. 2026 Literature Parity**: Added `amanbayev2026gls` (`arXiv:2602.11443`) for proposing Global-Local Selectivity $r = S_{\text{loc}}/S$ (`iff2025fannbench` for FANNBench), `veda2026` (`arXiv:2605.01342`), `RACORN` (`arXiv:2607.00768v2`, `github.com/naver/racorn`), and `EMA` (`arXiv:2606.00734v2`).
4. **Fourth-Round Concurrency & Unsynced-Mirror Audit (`v3.4`, `R12a`–`R12c`, `1,615` raw records, commit `afecb9d`, `FREEZE_v3_4.md` `10/10`)**:
   - **Snapshot Publication Race Closure (`src/modules/prism_ann_v3/consistent_snapshot_index.py`, research prototype)**: Preserving frozen `v3.3` `dynamic_dag_ubp.py` untouched (`FREEZE_v3_3.md` `9/9`), `AtomicVersionedLineageCorpus` captures `frozen_graph` under `auth_graph._lock` first, computes all reachability postings strictly from `frozen_graph`, and publishes monotonically. `R12a` (`24`-chunk DAG) reproduces `100/100` torn snapshots on frozen `v3.3` control while proving `0/200` torn snapshots (`100` double-injection + `100` out-of-order multi-publisher), `0` ordering regressions, and `0` leaks on `v3.4`.
   - **Opaque SpiceDB `ZedToken` Lag & Authoritative Fallback (`R12b`, `40`-chunk live SpiceDB)**: Across `13/13` live native SpiceDB v1.57.1 scenarios (reporting `requested_external_zed_token` separately from SpiceDB `looked_up_at` evaluated revision or `"unknown"`), `ConsistentDynamicPrismANNIndex` achieves `0` mismatches, `5` verified `fail_closed` refusals, and `4` verified live `spicedb_leaf_fallback` executions (never consulting a lagging local mirror).
   - **Multi-Threaded Public `search()` Stress (`R12c`, `24`-chunk DAG)**: `1,200` concurrent reads (`600` exact + `600` fresh, `0.033 ms` med / `1.327 ms` P99) across `101` audited snapshots yield `0` torn snapshots, `0` ordering regressions, and `0` leaks.

## Decision
1. **Strict Separation of Confirmatory (`v3.0`) vs. Supplementary Reviewer-Audit (`v3.1`, `v3.2`, `v3.3`, `v3.4`) Evidence**:
   - Preserve `FREEZE.md` (`5/5`), `FREEZE_v3.md` (`7/7`), `FREEZE_v3_1.md` (`8/8`), `FREEZE_v3_3.md` (`9/9`), and all prior datasets untouched.
   - Lock `src/modules/prism_ann_v3/consistent_snapshot_index.py` in `FREEZE_v3_4.md` (`10/10` SHA-256 hashes) and pre-register `experiments/v3/PROTOCOL_v3_{1,2,3,4}.md` prior to execution.
   - Emit per-trial raw JSONL logs verified bit-for-bit by `bench/recompute_v3_{1,2,3,4}.py`.
2. **Formal Split of Theorem 1, Theorem 2 (Dynamic Multi-Parent DAGs), and Atomic `ZedToken` Corollary 1**:
   - **Theorem 1** proves $|T_{\text{UBP}}^+(u)| \le k_0 + m(b-1)L$ on single-parent container trees (`0/10,000` violations in `R1`).
   - **Theorem 2** proves exact set equivalence $\Phi(\mathcal{P}_{\text{UBP}}(u)) = D_{\text{auth}}(u)$ (`0` FP, `0` FN) on arbitrary finite acyclic multi-parent ReBAC DAGs under **Deny-Dominates-Grant** precedence — provided structural edge mutations increment an atomic lineage revision (`CorpusRevisionSnapshot`) paired with `at_least_as_fresh` / `at_exact_snapshot` SpiceDB `ZedToken` checks.
   - **Corollary 1** decomposes revocation latency ($0$ vector writes, $O(1)$ SpiceDB tuple delete) and pins dynamic structural edits via atomic `CorpusRevisionSnapshot` swap.
3. **Transparent Reporting of Falsified Strict Cutoffs (`PR7`, `PR8`, `PR10`)**:
   - Report all supported and falsified pre-registered predictions (`PR7`, `PR8`, `PR10`) transparently across governance docs, `REVIEWER_AUDIT_REPORT.md`, and `paper/prism_ann.tex`.

## Alternatives Considered (Design-It-Twice)
1. **Mutate `results/v3/summary.json` or overwrite `v3.1`/`v3.2` raw files**: Rejected; preserving immutable prior audits (`v3.0`, `v3.1`, `v3.2`) alongside additive `v3.3` (`FREEZE_v3_3.md`) provides an auditable scientific trail without hindsight editing.
2. **Claim the static-lineage prototype handled arbitrary post-index hierarchy mutations**: Rejected after Priority Findings 1 & 2; implemented explicit `DynamicMultiParentAuthGraph` + `VersionedLineageCorpus` (`dynamic_dag_ubp.py`) and scoped legacy `PrismANNIndex`/`PrismANNIndexV3` strictly to static-hierarchy deployments.

## Mapped Paper Theorem & Bound
- **Theorem 1** (Section III-A): $|T_{\text{UBP}}^+(u)| \le k_0 + m(b-1)L$ on single-parent trees.
- **Theorem 2** (Section III-A): $\Phi(\mathcal{P}_{\text{UBP}}(u)) = D_{\text{auth}}(u)$ (`0` FP, `0` FN) on dynamic multi-parent acyclic DAGs under Deny-Dominates-Grant precedence with atomic lineage-revision publication.
- **Corollary 1** (Section III-A): Zero vector-index writes ($0$ payload mutations) and atomic `ZedToken` ($\zeta_{\text{rev}}$) + `CorpusRevisionSnapshot` visibility.

## Deep Module Seam
- `src/modules/prism_ann_v3/dynamic_dag_ubp.py` -> `DynamicMultiParentAuthGraph`, `VersionedLineageCorpus`, `DynamicPrismANNIndex` (frozen `v3.3`)
- `src/modules/prism_ann_v3/consistent_snapshot_index.py` -> `AtomicVersionedLineageCorpus`, `ConsistentDynamicPrismANNIndex`, `AtomicRevisionSnapshot` (frozen `v3.4` research prototype)
- `bench/prism_audit_kernel.cpp` -> `bench/_build/libprism_audit_kernel.dylib` (`audit_mode3_matrix`, `audit_r4_concurrent_zedtoken`, `audit_r5_compaction_step`)
- `bench/recompute_v3_{1,2,3,4}.py` -> `recompute_v3_{1,2,3,4}_summary(jsonl_path) -> dict`

## Consequences
- **Positive**: Every claim in `paper/prism_ann.tex` is backed by `209,303` cumulative v3-series JSONL records (`169,810` `v3.0` + `22,533` `v3.1` + `6,821` `v3.2` + `8,524` `v3.3` + `1,615` `v3.4`) with `100%` deterministic recomputation parity across `4` additive reviewer audit rounds.
- **Negative**: Maintaining five frozen manifests (`FREEZE.md`, `FREEZE_v3.md`, `FREEZE_v3_1.md`, `FREEZE_v3_3.md`, `FREEZE_v3_4.md`) and four audit recomputers adds ~3s to CI verification.
- **Reversibility**: `Two-Way Door` (all `v3.4` artifacts live cleanly inside `src/modules/prism_ann_v3/consistent_snapshot_index.py`, `FREEZE_v3_4.md`, and `results/v3_4_audit/`).
