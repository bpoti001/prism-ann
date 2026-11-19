# ADR-0004: Provenance-Verified, Real-Baseline Evaluation Protocol (Prism-ANN v2)

- **Status**: `accepted`
- **Date**: 2026-11-19
- **Scope**: `bench/` harness, `results/v2/`, all paper numbers in Milestone 4
- **Supersedes (for evaluation only)**: the v1 evaluation in `run_prism_ann_benchmarks.py` (retained as exploratory history)

## Context
The v1 evaluation (Milestone 3) had four defects, documented in the session retrospective:
1. The first pass contained calibrated, hardcoded curves and formula-generated latencies, and these passed every gate.
2. The "LoCoMo embeddings" were hash projections, not encoder outputs, and the queries were corpus points plus noise.
3. All baselines (ACORN, HoneyBee, UNG, pgvector) were Python reimplementations, and SpiceDB was never called.
4. The Brake 2 and Brake 3 scripts printed hardcoded scores ("97.72/100", "STRONG ACCEPT 9.0/10").

## Decision
1. **Raw-record provenance.** Every measurement is emitted by one harness (`bench/harness.py`) as a per-query raw record in `results/v2/raw/*.jsonl`. Each record contains: run_id, git SHA, system, seed, selectivity/r, query_id, wall_ns from `perf_counter_ns`, distance computations when the system exposes them, result IDs, ground-truth IDs, and recall. Summary JSON is derived only from raw records, and `bench/recompute.py` must reproduce it bit-for-bit.
2. **Real data and held-out queries.** The corpus is BEIR Quora (~523k passages, real text) encoded with the locally cached `sentence-transformers/all-MiniLM-L6-v2` (384-d, normalized). Queries are the BEIR Quora test queries, encoded with the same model and never inserted into the corpus.
3. **Real baselines where obtainable.** These are FAISS `IndexHNSWFlat` with `IDSelector` filtering, FAISS ACORN if present in the installed wheel, hnswlib with a filter callback, pgvector 0.8 iterative scan on a real PostgreSQL instance, and exact filtered brute force (ground truth). Systems with no public implementation (HoneyBee) are discussed but not plotted as measured baselines.
4. **Real SpiceDB as oracle and timing source.** A SpiceDB instance (`serve-testing` or in-memory datastore) holds the hierarchy schema and tuples. Its `LookupResources` output is the correctness oracle for UBP, and its latency is measured over gRPC.
5. **Hardware-independent primary metrics.** These are Recall@10 and distance computations. Latency is secondary and reported with its implementation language (the Prism-ANN reference traversal is Python, while FAISS and pgvector are C/C++).
6. **One confirmatory run.** It happens at the frozen algorithm SHA recorded in `FREEZE.md`. Any later change is an exploratory run, logged in `results/run_ledger.md` and labeled as exploratory in the paper.
7. **Human-model reviews instead of scripted scores.** Brake 2 (figures) and Brake 3 (peer review) are written by a fresh reviewer agent that reads the compiled PDF and PNGs at review time. Scripts may only check that review files exist and reference the SHA-256 of the current artifacts. They may not contain literal scores or verdicts.

## Alternatives Considered (Design-It-Twice)
1. **Keep v1 numbers and add caveats.** Rejected: the numbers come from synthetic vectors and self-built baselines, and caveats can't repair provenance.
2. **Full C++ re-implementation of Prism-ANN inside FAISS before evaluating.** Rejected for this milestone because the cost is too high. Hardware-independent metrics (recall, distance computations) allow a fair algorithmic comparison now. A C++ port becomes a follow-up ADR if the algorithmic results hold.
3. **Docker-based SpiceDB, Postgres, and Qdrant.** Not available because the Docker daemon is down. Native Homebrew binaries give the same engines.

## Mapped Paper Theorem
Evaluation methodology for §5. Theorems 2–4 are reclassified as **Propositions under stated assumptions** unless their proofs are tightened.

## Deep Module Seam
`bench/harness.py` -> `run_condition(system, queries, filter_bitmap, k, seed) -> Iterator[RawRecord]`; `bench/recompute.py` -> `recompute_summary(raw_dir) -> dict`.

## Consequences
- **Positive**: Every number is traceable to raw records, real data, and real systems. The fabrication failure mode is closed structurally rather than by regex.
- **Negative**: Expensive setup (encoding, Postgres, SpiceDB). Python-traversal latency isn't comparable to C++ latency, so it can't be a headline.
- **Reversibility**: `Two-Way Door`.
