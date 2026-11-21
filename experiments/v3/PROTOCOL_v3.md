# Prism-ANN v3 — Pre-Registered Confirmatory Protocol (Milestone 5 / Option A)

- **Governing ADRs**: `ADR-0001`, `ADR-0002`, `ADR-0003`, `ADR-0004`, `ADR-0005`
- **Registered by**: planner/orchestrator, 2026-11-20, AFTER Phase 17 dev-split exploration (`[0..499]`) and BEFORE any Phase 19 confirmatory run
- **Frozen algorithm**: see `FREEZE_v3.md` (SHA-256 of `src/modules/prism_ann_v3/*.py`, `src/modules/prism_ann/ubp_resolver.py`, and `bench/prism_ckernel.cpp`)
- **Status**: `PRE_REGISTERED` (committed before Phase 19 starts)

## Shared Setup
- **Corpus 1 (Primary)**: Full BEIR Quora (`N = 522,931` passages, `all-MiniLM-L6-v2` 384-d L2-normalized). Test queries sampled strictly from indices **`[500..9,984]`** (`500` queries/condition/seed; 100% disjoint from Phase 17 dev queries `[0..499]` and from corpus).
- **Corpus 2 (Cross-Domain Generalization)**: Distinct-domain real BEIR Wikipedia corpus (`BeIR/nq` or `BeIR/hotpotqa`, `N = 250,000` passages, `all-MiniLM-L6-v2` 384-d L2-normalized or `BAAI/bge-base-en-v1.5` 768-d if available locally; exact corpus/encoder logged in `results/v3/ENVIRONMENT.md`), using strictly disjoint BEIR test queries (`500` queries/condition/seed).
- **Seeds**: `3` (`0, 1, 2`). Report 3-seed mean ± 95% $t$-CI and pooled medians/P95/P99.
- **Frozen v3 Prism Parameters (locked from Phase 17 dev split)**:
  - `M = 16`, `M_bridge = 8` (`4` geometric L3 folder + `2` geometric L2 parent + `2` geometric Meaning Magnet, RNG $\alpha = 1.0$ + medoid hub), `+1.91%` RAM at `d = 384`.
  - `tau_high = 0.55`, `tau_low = 0.02`, `tau_stall = 0.04`, `stall_check_hops = 16`, `N_guard = 25,000`, `efSearch = 64`, `k_0 <= 4` entry portals.
  - Mode 3: native C++ ARM NEON `sq8` (`vdotq_s32` + `rerank_k = max(4*k, 64)`) directly over Z-ordered `CRoaring` `[start, end)` intervals (`bench/prism_ckernel.cpp`).
- **Real Native Baselines**:
  - `FAISS 1.16.0` (`IndexHNSWFlat` + `IDSelectorBitmap`, `M=16` & `M=8` shared base graph)
  - Upstream C++ `stanford-futuredata/ACORN` (`acorn-1` with $\gamma=1$ AND `acorn-gamma` with $\gamma=4$ or $\gamma=10$)
  - `hnswlib 0.8.0` (`M=16`, filter callback)
  - `PostgreSQL 17.12 + pgvector 0.8.7` (`hnsw.iterative_scan = relaxed_order`, `EXPLAIN`-verified)
  - `exact-brute-force` (BLAS ground truth)
  - `v2-ring-chord-M4` (for direct v2 $\to$ v3 geometric bridge ablation)
  - `Qdrant` (if runnable natively without Docker; otherwise documented in `results/v3/DEVIATIONS.md`)
- **Raw Provenance**: Every query emits one raw JSONL record to `results/v3/raw/*.jsonl`; `results/v3/summary.json` is derived strictly via `bench/recompute_v3.py` (or extended `bench/recompute.py`) and verified bit-for-bit with `--check`.

## H1v3 — Live SpiceDB Equivalence & Pre-Filter Speedup (Memory AND Persistent PostgreSQL 17 Datastore)
- **P1a**: `0` doc / `0` chunk mismatches vs. live SpiceDB `LookupResources` across `n = 600` principals (`3` seeds × `200`, `0–20` `DENY`s).
- **P1b**: `100%` (`600/600`) within Theorem 1 bound $|T^+_{\text{UBP}}| \le k_0 + m(b-1)L$.
- **P1c**: On broad principals ($\ge 1{,}000$ auth docs), median UBP + `CRoaring` is $\ge 10\times$ faster than SpiceDB `LookupResources` + leaf bitmap on **both** `--datastore-engine memory` AND `--datastore-engine postgres` (PostgreSQL 17.12), also reporting live `ReadRelationships + UBP + CRoaring` latency.

## H2v3 — Multi-Corpus Random-Overlay Selectivity Sweep ($S \in \{0.1\%, 0.5\%, 1\%, 5\%\}$)
- **P2a**: On full `523k` BEIR Quora, `v3-geom-M8` (graph-only, C++) achieves $\ge 75\%$ Recall@10 at $S \in \{0.5\%, 1.0\%\}$, beating `faiss-hnsw-M16` by $\ge +40$ pts and `v2-ring-chord-M4` by $\ge +20$ pts at $S = 0.5\%$.
- **P2b**: `v3-geom-M8` beats compiled upstream C++ `acorn-1` on Recall@10 across all $S \in \{0.1\%, 0.5\%, 1\%, 5\%\}$ on both corpora, and uses $\le 0.5\times$ the extra index RAM of upstream C++ `acorn-gamma` ($\gamma \ge 4$) while staying within $-5$ pts Recall@10 of `acorn-gamma`.
- **P2c**: `v3-full-guard-sq8` achieves $\ge 99.0\%$ Recall@10 at $S \le 1\%$ on both corpora while beating BLAS `exact-brute-force` median latency by $\ge 2.0\times$ at $S \in \{0.5\%, 1.0\%\}$ and beating `hnswlib-M16` and `pgvector 0.8.7` median latency by $\ge 25\times$ at $S = 0.1\%$.

## H3v3 — Multi-Corpus Cluster-Aligned Correlation Study ($S = 2\%$, measured $r = S_{\text{loc}}/S$)
- **P3a**: At measured $r \le 0.5$, `v3-geom-M8` (graph-only) beats `faiss-hnsw-M16` by $\ge +40$ pts Recall@10, AND `v3-full-guard-sq8` (with Local-Stall Guard) achieves $\ge 95\%$ Recall@10 at $\le 1.5\text{ ms}$ median latency (eliminating v2's `24.55%` collapse).
- **P3b**: At measured $r \ge 2.0$, `v3-geom-M8` (`tau_high = 0.55`) uses $\le 0.65\times$ the distance evaluations of `v3-static-2hop` (GLS disabled) while keeping Recall@10 within $-1.0$ pt.

## H4v3 — Live Revocation (Persistent PostgreSQL-Backed SpiceDB vs. PostgreSQL 17 + `pgvector` 0.8.7 `UPDATE`)
- **P4a**: Revoking 1 folder edge covering `1,024` docs (`153,600` chunks) in persistent PostgreSQL-backed SpiceDB uses `0` vector writes.
- **P4b**: Real PostgreSQL/`pgvector` transactional `UPDATE` on `153,600` rows is $\ge 100\times$ slower than persistent PostgreSQL-backed SpiceDB `DeleteRelationships` + UBP + `CRoaring`.

## H5v3 — 4-Way `InitEntryPortals` vs. Geometric Express-Bridge Ablation (`523k` BEIR Quora, 3 seeds)
- **P5**: Across $S \in \{0.1\%, 0.5\%, 1.0\%\}$, `hhnsw-v2-geom-M8-noportal` (`0` entry portals) retains $\ge 85\%$ of the recall gain of `v3-geom-M8` over `faiss-hnsw-M16`, proving that geometric express bridges—not entry-portal seeding—drive the recall lift.

## Reporting Rules
- Every prediction (`P1a`–`P5`) is reported plainly as `SUPPORTED`, `FALSIFIED`, or `UNTESTABLE`, including any where baselines win.
- Any deviation is documented in `results/v3/DEVIATIONS.md` and the paper's Protocol Deviations table.
- Zero v1 or v2 exploratory numbers may be mixed into v3 confirmatory tables.
