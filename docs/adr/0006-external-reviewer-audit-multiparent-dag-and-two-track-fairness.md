# ADR-0006: External Reviewer Audit Protocol (`v3.1 R1–R5` & `v3.2 R6–R8`), Multi-Parent DAG Exactness (`Theorem 2`), Two-Track Fair Attribution, and Three-Tier Audience Architecture

- **Status**: `accepted`
- **Date**: 2026-11-23
- **Scope**: `bench/prism_audit_kernel.cpp`, `bench/run_reviewer_audit_v3_1.py`, `bench/run_reviewer_audit_v3_2.py`, `bench/recompute_v3_1.py`, `bench/recompute_v3_2.py`, `experiments/v3/PROTOCOL_v3_1.md`, `experiments/v3/PROTOCOL_v3_2.md`, `docs/ONBOARDING_NEW_GRAD.md`, `docs/ARCHITECTURE_SENIOR_ENGINEER.md`, `docs/RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md`, `paper/prism_ann.tex`
- **Builds Upon**: `ADR-0001` (UBP), `ADR-0002` (`H-HNSW` / `ACORN-GLS`), `ADR-0003` (Z-Ordered Tri-Modal Planner), `ADR-0004` (Raw-Record Provenance), `ADR-0005` (`v3` Confirmatory Evaluation)
- **Mapped Paper Section**: Section III-A (**Theorem 1** Single-Parent Tree Token Bound, **Theorem 2** Multi-Parent DAG Exact Set Equivalence & **Corollary 1** Revocation Boundary), Section V-G (Supplementary Reviewer Audit `R1`–`R8`), Section VI-B (`RACORN` & `EMA` Novelty Matrix)

## Context
Following the frozen `v3-confirmatory-001` benchmark (`169,810` raw records, `7/7` checksums in `FREEZE_v3.md`), two rounds of external research peer review raised eight rigorous theoretical, systems-fairness, and pedagogical requirements:
1. **First-Round Audit (`v3.1`, `R1`–`R5`)**:
   - `R1`: Adversarial property-based fuzzing of $\mathcal{P}_{\text{UBP}}$ across randomized hierarchy topologies ($L \in [3, 6], b \in [3, 8], k_0 \in [1, 8], m \in [0, 25]$, overlapping grants, and deny-inside-grant chains) against an exhaustive leaf oracle.
   - `R2`: Ultra-low selectivity ($S = 0.01\%$, $N_{\text{cand}} \approx 52$) evaluation across BEIR Quora (`522,931`) and BEIR NQ (`200,000`).
   - `R3`: 2×2×2 component isolation of Mode 3 separating Z-order contiguous layout, `SQ8` quantization, and ARM NEON `vdotq_s32` intrinsics under both `64 MB` cache-thrashing eviction sweeps and warm L2/L3 cache.
   - `R4`: Persistent PostgreSQL 17 SpiceDB revocation scaling ($10^3 \to 1.05 \times 10^6$ chunks) and `16`-thread concurrent `ZedToken` ($\zeta_{\text{rev}}$) race verification (`36,881` concurrent queries).
   - `R5`: Dynamic stream ingestion (`50,000` vectors in `5 × 10k` batches) measuring mutable delta-buffer search overhead and background Z-order CSR compaction time.
2. **Second-Round Audit (`v3.2`, `R6`–`R8`) & Theoretical / Novelty Enhancements**:
   - `R6` & **Theorem 1 / Theorem 2 Split**: Separate the closed-form token cardinality bound $k_0 + m(b-1)L$ (**Theorem 1**, valid on single-parent trees where each `DENY` node has a unique ancestor chain) from exact set equivalence $\Phi(\mathcal{P}_{\text{UBP}}(u)) = D_{\text{auth}}(u)$ on general **multi-parent acyclic Zanzibar DAGs** (**Theorem 2**, verified over `5,000` randomized multi-parent DAGs with diamond inheritance and conflicting `GRANT`/`DENY` paths).
   - `R7`: Two-Track baseline fairness separating **Track 1** (pure C++ index/traversal latency with pre-compiled filter bitmaps) from **Track 2** (end-to-end query latency including live PostgreSQL 17 SpiceDB authorization resolution + bitmap compilation + search), plus fragmented $L_5$-only principal grants ($\approx 50$ disjoint leaf containers) where contiguous Z-order collapses to `1.00–1.08×`.
   - `R8`: 5-level taxonomy of Exact vs. Empirical Recall@10 quantifying `SQ8` (`INT8`) + top-$M_{\text{rerank}}$ (`M=32, 64, 128`) FP32 reranking approximation gap vs. pure FP32 Mode 3 (`100.00%` mathematical guarantee at $S = 0.01\%$ where $N_{\text{cand}} = 52 \le M_{\text{rerank}} = 64$).
   - **Nov. 2026 Literature Parity & Three-Tier Audience Separation**: Incorporate `RACORN` (`arXiv:2607.00768v2`, Nov. 2026) and `EMA` (`arXiv:2606.00734v2`, Nov. 2026) into Table I and §VI-B, and separate educational onboarding (`docs/ONBOARDING_NEW_GRAD.md`), production architecture (`docs/ARCHITECTURE_SENIOR_ENGINEER.md`), and research evaluation (`docs/RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md`).

## Decision
1. **Strict Separation of Confirmatory (`v3.0`) vs. Supplementary Reviewer-Audit (`v3.1` & `v3.2`) Evidence**:
   - Preserve `FREEZE.md` (`5/5`), `FREEZE_v3.md` (`7/7`), and `results/v3/summary.json` (`169,810` records) completely untouched.
   - Lock the native C++17 audit kernel (`bench/prism_audit_kernel.cpp`) in `FREEZE_v3_1.md` (`8/8` SHA-256 hashes) and pre-register `experiments/v3/PROTOCOL_v3_1.md` (`PR1`–`PR5`) and `experiments/v3/PROTOCOL_v3_2.md` (`PR6`–`PR8`) prior to execution.
   - Emit per-trial raw JSONL logs (`results/v3_1_audit/raw/v3_1_reviewer_audit.jsonl`, `22,533` records; `results/v3_2_audit/raw/v3_2_reviewer_audit.jsonl`, `6,821` records) verified bit-for-bit by standalone deterministic recomputers (`bench/recompute_v3_1.py` and `bench/recompute_v3_2.py`).
2. **Formal Split of Theorem 1 (Single-Parent Tree Cardinality Bound) and Theorem 2 (Multi-Parent DAG Exactness) + Scoped Corollary 1**:
   - **Theorem 1** proves $|T_{\text{UBP}}^+(u)| \le k_0 + m(b-1)L$ on single-parent container trees ($0$ violations across `10,000` trials in `R1`).
   - **Theorem 2** proves exact set equivalence $\Phi(\mathcal{P}_{\text{UBP}}(u)) = D_{\text{auth}}(u)$ (`0` false positives, `0` false negatives) on arbitrary finite acyclic multi-parent ReBAC DAGs under **Deny-Dominates-Grant** precedence, while documenting DAG path-multiplicity scaling $|T_{\text{UBP}}^+(u)| \le k_0 + m \cdot \bar{p}_{\text{dag}}(b-1)L$ (`0/5,000` mismatches in `R6`).
   - **Corollary 1** explicitly decomposes end-to-end revocation latency $T_{\text{revoke}} = T_{\text{SpiceDB-tx}} + T_{\text{cache-inval}} + \text{0 ms}_{\text{vector-index}}$ (`0` vector index mutations, $O(1)$ SpiceDB relation-tuple delete independent of $N_{\text{chunks}}$) and formalizes the pre-/post-$\zeta_{\text{rev}}$ `ZedToken` snapshot boundary (`0/18,412` post-revocation leaks in `R4b`).
3. **Transparent Reporting of Falsified Strict Cutoffs (`PR7` & `PR8`)**:
   - Report both supported (`PR1`–`PR6`) and falsified (`PR7`, `PR8`) predictions transparently in `REVIEWER_AUDIT_REPORT.md`, `docs/RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md`, and §V-G of `paper/prism_ann.tex`.

## Alternatives Considered (Design-It-Twice)
1. **Mutate `results/v3/summary.json` in place to merge `R1`–`R8` into confirmatory tables**: Rejected because modifying post-freeze confirmatory artifacts violates pre-registration integrity (`ADR-0004` / `ADR-0005`). Separate pre-registered audit protocols (`PROTOCOL_v3_1.md`, `PROTOCOL_v3_2.md`) and JSONL ledgers preserve full epistemic provenance.
2. **Claim the tree bound $k_0 + m(b-1)L$ holds unchanged on multi-parent DAGs**: Rejected because secondary parent links allow a single `DENY` node to taint multiple ancestor paths ($\bar{p}_{\text{dag}} \ge 1$), observed in `4.86%` (`243/5,000`) of multi-parent DAG trials (`max 135 vs. 122`). Splitting Theorem 1 (tree bound) and Theorem 2 (multi-parent DAG exactness + $\bar{p}_{\text{dag}}$ scaling) makes the theory airtight.

## Mapped Paper Theorem & Bound
- **Theorem 1** (Section III-A): $|T_{\text{UBP}}^+(u)| \le k_0 + m(b-1)L$ on single-parent trees.
- **Theorem 2** (Section III-A): $\Phi(\mathcal{P}_{\text{UBP}}(u)) = D_{\text{auth}}(u)$ (`0` false positives, `0` false negatives) on multi-parent acyclic DAGs under Deny-Dominates-Grant precedence.
- **Corollary 1** (Section III-A): Zero vector-index writes ($0$ payload mutations) and $O(1)$ SpiceDB tuple deletion relative to $N_{\text{chunks}}$, bounded by atomic `ZedToken` ($\zeta_{\text{rev}}$) snapshot visibility.

## Deep Module Seam
- `bench/prism_audit_kernel.cpp` -> `bench/_build/libprism_audit_kernel.dylib` (`audit_mode3_matrix`, `audit_r4_concurrent_zedtoken`, `audit_r5_compaction_step`)
- `bench/recompute_v3_1.py` -> `recompute_v3_1_summary(jsonl_path) -> dict`
- `bench/recompute_v3_2.py` -> `recompute_v3_2_summary(jsonl_path) -> dict`

## Consequences
- **Positive**: Every claim in `paper/prism_ann.tex` is backed by `199,164` total raw JSONL records (`169,810` confirmatory `v3.0` + `22,533` `v3.1` audit + `6,821` `v3.2` audit) with `100%` deterministic recomputation parity and `310+` automated Brake-1 checks.
- **Negative**: Maintaining three frozen manifests (`FREEZE.md`, `FREEZE_v3.md`, `FREEZE_v3_1.md`) and three deterministic recomputers adds CI verification steps (~2 seconds total).
- **Reversibility**: `Two-Way Door` (all supplementary audit artifacts live in dedicated `results/v3_1_audit/` and `results/v3_2_audit/` directories).
