# Independent Peer Review — Prism-ANN v3 (Brake 3)

- **Reviewer**: Independent Milestone 5 / Phase 20 Reviewer (zero prior builder context)
- **Reviewed Manuscript (Pass 1 Initial)**: `paper/prism_ann.pdf` (11 pages, IEEEtran conference format; SHA-256 `6d07a4434193f6c91575656f0219124081d5ce7e3391be1ab9f6546e1ecbdc37`; Source TeX 562 lines) — Score **6.0 / 10** (3 Blockers)
- **Reviewed Manuscript (Pass 2 Post-Revision Sign-Off)**: `paper/prism_ann.pdf` (12 pages, IEEEtran conference format; **Full 64-Character SHA-256**: `422f8f587f34b0ef8537c1a292ade3448822ab07e3b4eb15873694bc71826bf5`; [`paper/prism_ann.tex`](file:///Users/tejap/memory_paper/paper/prism_ann.tex) 578 lines) — **Updated Score: 7.5 / 10 (Accept — 0 Blockers Remaining; see Section 8)**

---

## 1. Manuscript Summary

The paper presents **Prism-ANN v3**, an authorization-aware filtered Approximate Nearest Neighbor (ANN) retrieval architecture co-designed for enterprise Relationship-Based Access Control (ReBAC, modeled via Google Zanzibar / SpiceDB with subtractive `but not` / `DENY` exclusions) and ontological filtering (e.g., Meaning Magnets) over HNSW indexes. The architecture combines three components:
1. **Subtractive-Aware Upward Boundary Pruning ($\mathcal{P}_{\text{UBP}}$)**: Ingest-time immutable structural lineage stamping $\operatorname{Anc}(v_i)$ coupled with top-down taint splitting in SpiceDB, proving $|T_{\text{UBP}}^+(u)| \le k_0 + m(b-1)L$ and exact set equivalence (Theorem 1) with zero-write $O(1)$ revocation (Corollary 1).
2. **Geometric Express Bridges (`H-HNSW v2`) & `ACORN-GLS`**: Augments an $M=16$ FAISS HNSW base graph with $M_{\text{bridge}}=8$ Vamana/RNG-diverse intra-container (`4` L3 folder, `2` L2 parent) and intra-magnet (`2` Meaning Magnet) semantic links, navigated by local-selectivity-adaptive `ACORN-GLS` in native C++.
3. **Z-Ordered `CRoaring` Tri-Modal Planner & ARM NEON Kernel**: Lexicographically orders vectors by $(\operatorname{Anc}(v_i), \tau_1(v_i))$ so UBP tokens map to contiguous `RunContainer` intervals scanned by ARMv8.2-A `vdotq_s32` (`SQ8` + top-$\max(4k,64)$ FP32 rerank), reinforced by a Local-Stall Guard that escalates negative-correlation pockets ($r \le 0.5$) to Mode 3.

Evaluated in a frozen confirmatory run (`v3-confirmatory-001`, 169,810 raw records, 3 seeds) over BEIR Quora ($N=522{,}931$) and BEIR NQ Wikipedia ($N=250{,}000$) against live SpiceDB v1.57.1 (memory and persistent PostgreSQL 17), PostgreSQL 17.12 + `pgvector` 0.8.7, FAISS 1.16.0, compiled upstream C++ `ACORN-1` / `ACORN-gamma`, and `hnswlib` 0.8.0, all 11 pre-registered predictions (`P1a`–`P5`) are reported as supported.

---

## 2. Independent Provenance, Protocol & Fairness Audit

### 2.1 Provenance & Freeze Verification (Verified Clean)
- **Algorithm Freeze**: Both `FREEZE.md` (v2, 5/5 files) and `FREEZE_v3.md` (v3, 7/7 files: `ubp_resolver.py`, `src/modules/prism_ann_v3/*.py`, `bench/prism_ckernel.cpp`) match disk SHA-256 checksums (`git diff 6682dfd HEAD` and `git diff 41868bb HEAD` are empty on all 7 files).
- **Raw-Record Recomputation**: `.venv-bench/bin/python -m bench.recompute_v3 --raw-dir results/v3/raw --check results/v3/summary.json` outputs `[recompute_v3] MATCH` bit-for-bit across all 169,810 records (`freeze_match=True` on 169,810/169,810 records, `0` authorization leaks across all records).
- **Independent Raw JSONL Tracing**: Independently verified from `results/v3/raw/v3-confirmatory-001__*.jsonl` without using `bench.recompute_v3`:
  - `H1_memory` & `H1_postgres`: `0/1,200` mismatches, `1,200/1,200` within Theorem 1 bound, broad-principal (`n=271`) medians `79.14 ms` (mem SpiceDB) / `98.30 ms` (PG SpiceDB) vs. `0.35 ms` (`UBP+bitmap`) and `2.72 ms` / `3.49 ms` (`ReadRelationships+UBP+bitmap`).
  - `H2_quora` & `H2_nq`: All table recall means, eval counts, and pooled medians match raw logs (`v3-geom-M8` `66.60%..95.25%` Quora, `75.57%..93.35%` NQ; `v3-full-guard-sq8` `100.00%` at $S \le 1\%$ in `0.093–0.109 ms` Quora / `0.049–0.080 ms` NQ).
  - `H3_quora` & `H3_nq`: Depleted ($r \le 0.5$) and enriched ($r \ge 2.0$) metrics, escalation counts (`667/728` Quora, `629/715` NQ), and false escalations (`10/750`, `21/753`) match raw logs.
  - `H4_postgres`: `n=5` trials verified (`67.28 ms` median, `0` writes vs. `179,390.6 ms` median, `153,600` row writes).
  - `H5_quora`: Retained gains (`100.95%`, `102.30%`, `101.04%`) verified directly.
- **Query Disjointness**: Verified directly from raw `query_id`s that `H2_quora` (4,546 unique BEIR qids), `H3_quora` (1,421 qids), and `H5_quora` (4,546 qids) have **0 overlap** with Phase 17 dev queries `[0..499]` (and `v3_dev` raw logs use strictly `[0..499]`), and `H2_nq`/`H3_nq` are 100% subsets of the `3,452` corpus-disjoint NQ test queries.
- **Unit Tests & Integrity Scan**: All 19 unit/provenance tests pass (`PYTHONPATH=. .venv-bench/bin/python -m pytest`). No hardcoded curves, formula-derived metrics, or scripted verdicts exist in `bench/`, `src/`, `verify_prism_hallucinations.py`, `run_prism_paperviz_audit.py`, or `run_prism_scholarpeer_review.py` (though legacy v1 scripts `run_paperviz_audit.py` and `run_scholarpeer_review.py` remain at repo root).

### 2.2 Critical Code & Fairness Audit Findings
1. **Unreported SQ8 Quantization Buffer RAM (`+200.8 MB` / `+22.9%`)**:
   - `GeometricHHNSW.memory_footprint_bytes()` (`src/modules/prism_ann_v3/geometric_hhnsw.py:456-465`) computes `+1.91%` (`+32 B/node`, `16.73 MB` over `876.6 MB` base HNSW = `893.3 MB`) solely for `v3-geom-M8`.
   - However, `v3-full-guard-sq8`—the headline system in Abstract, Table I, and Section V—relies on `ZOrderedCorpus.sq8_vectors` (`src/modules/prism_ann/trimodal_planner.py:194-196`), an `N x d` `int8` buffer allocated alongside FP32 vectors (`522,931 * 384 * 1 B = 200.8 MB`, **`+384 B/node`**, or **`+22.9%`** over base HNSW!). Combined with `+32 B/node` bridges, `v3-full-guard-sq8` uses `+416 B/node` (`+24.8%` extra RAM)—nearly double `ACORN-gamma`'s level-0 extra RAM (`+224 B/node`). Table I (`paper/prism_ann.tex:72`) labels `Prism-ANN v3 (Proposed)` as `+32 B/n (+1.91% at d=384)` without separating graph-only `v3-geom-M8` from `v3-full-guard-sq8`.
2. **Baseline Timing Asymmetry (`O(N)` Python Mask Prep vs. Pre-Resolved UBP Tokens) & Cold-Start `cpp-mode3-sq8`**:
   - **`v3-full-guard-sq8` (`0.09–0.11 ms`) vs. `cpp-mode3-sq8` (`0.17–0.20 ms`)**: Tracing `bench/run_v3_dev_exploratory.py:83-105,178-194` and `src/modules/prism_ann_v3/trimodal_v3.py:158-241` confirms both execute the *exact same* `_compile_ranges_from_tokens` + `mode3_scan_ranges_sq8` path at $S \le 1\%$. Why was `cpp-mode3-sq8` ~2x slower on Quora (especially Seed 1: `0.2134 ms` vs. `0.0550 ms`)? In `bench/harness_v3.py:379-382`, `cpp-mode3-sq8` runs immediately after `ZOrderedCorpus` allocates ~1.0 GB (`vectors` + `sq8_vectors`) with **zero warmup**, paying macOS demand-paging/cold-TLB/SLC misses (reproduced directly: cold `0.2019 ms` vs. warm `0.0517 ms`, matching `v3-full-guard-sq8` warm `0.0499 ms`), whereas `v3-full-guard-sq8` executes at line 478 after `faiss_m16`, `v2-ring-chord-M4`, and `v3-geom-M8` have faulted those pages.
   - **FAISS / ACORN / Exact-Brute-Force Mask-Prep Penalty**: Inside `run_condition`'s `perf_counter_ns()` timer (`bench/harness.py:210-213`), `FaissHNSWSystem.search` (`bench/systems.py:131-133`) runs `q.mask[self.internal_to_orig]` + `np.packbits(...)` over all $N=522{,}931$ entries in Python/NumPy on every query. Independent timing on this host shows **those two Python/NumPy lines alone take `0.823 ms` median**—meaning **~87% of `faiss-hnsw-M16`'s `0.95 ms` latency is Python mask marshaling**, while C++ FAISS HNSW search itself is only `~0.13 ms`! Likewise, `Acorn1System.search` (`bench/systems.py:210`) runs `q.mask[self.perm]` in NumPy per query, and `ExactBruteForceSystem.search` (`bench/systems.py:48-51`) executes `np.flatnonzero(q.mask)` + fancy-index matrix copy inside the timer. Meanwhile, Prism-ANN v3 receives pre-resolved `q.extra["ubp_tokens"]` (excluding `resolve_ubp_tokens`'s `0.35–3.49 ms` cost from `H1`) and sets bitsets in `O(N_cand / 64)` via Z-order `RunContainers`. While `O(|R_\Phi|)` bitset setup is a legitimate architectural benefit of Z-order `CRoaring`, pitting C++ range-only timing against Python `O(N)` permutation+packbits without separating C++ search time from Python mask prep exaggerates latency speedups over `FAISS`, `ACORN`, and BLAS brute force.
3. **Upstream `ACORN` Audit (`acorn-1` and `acorn-gamma`)**:
   - Verified `bench/acorn_cwrap.cpp` faithfully links compiled upstream `stanford-futuredata/ACORN` (`c259f11cdbec`, `METRIC_L2` on unit vectors, `acorn.efSearch = ef_search`, `FilterMapSelector`).
   - Verified why `acorn-gamma` ($\gamma=4, M_\beta=64$) collapses to `0.25%` (Quora) / `0.43%` (NQ) R@10 with `2.3` / `1.9` distance evals (`93.3%–97.0%` of queries have `ndis <= 5`) at $S=0.1\%$: upstream `ACORN.cpp:898-926` disables upper-layer 2-hop traversal for $\gamma > 1$, and `ACORN.cpp:1327` restricts level-0 2-hop expansion to neighbor slots $j - \text{begin} \ge M_\beta$ (`>= 64`). At `efConstruction = 64` (`M * gamma = 64`), nodes rarely accumulate $> M_\beta$ tail neighbors; when none pass at $S=0.1\%$, the candidate heap empties after `1–2` evals. Critically, an independent 50k ablation confirmed that **even with `ACORN/README.md`'s parameters (`gamma=12, M_beta=32, efConstruction=128`)**, `acorn-gamma` still collapses to `0.40%` R@10 (`1.5` ndis) at $S=0.1\%$. Thus the collapse is a genuine upstream limitation under predicate-agnostic $S=0.1\%$ at bounded `efSearch=64`, though the paper does not explain this mechanism—nor why `acorn-1` drops to `31.66%` at $S=5\%$ and `27.29%` at `r >= 2.0` (driven by upstream `ACORN.cpp:766,787` double-incrementing `numIters` during construction and `ACORN.cpp:1290,1320` counting visited passing nodes toward the `2*M` expansion cutoff).
4. **PostgreSQL SpiceDB & `pgvector` Audit**:
   - Verified `H1_postgres`, `H2_quora`, `H2_nq`, and `H4_postgres` run against real local PostgreSQL 17.12 (`synchronous_commit=on`), `spicedb v1.57.1` (`migrate head`), and `pgvector 0.8.7` (`iterative_scan=relaxed_order`, `EXPLAIN`-verified HNSW usage).
   - Caveats: single-node loopback deployment; `H4_postgres` tests an inline `acl_allowed` boolean column (which §V-F honestly notes could be avoided via a normalized folder-join schema at query-time join cost); and `DEVIATIONS.md` (`D7`) states `hnsw.max_scan_tuples=20000` even though `bench/engines.py:532-537` relies on the default rather than explicitly setting it.

---

## 3. Strengths

1. **Exemplary Reproducibility & Provenance Infrastructure**: Two-stage dev/confirmatory split (`[0..499]` vs. `[500..9,984]` + disjoint NQ `250k`), cryptographic freeze (`FREEZE_v3.md`), 169,810 per-query JSONL records, bit-for-bit `recompute_v3` parity, and `0/169,810` authorization leaks set a remarkably high bar for systems benchmarking.
2. **Real Systems Integration**: Evaluates live SpiceDB (both memory and durable PostgreSQL 17), real `pgvector` 0.8.7, compiled upstream C++ `ACORN-1` and `ACORN-gamma`, `FAISS`, and `hnswlib`, rather than toy Python mocks.
3. **Clean Elimination of v2 Confounds & Decisive `H5v3` Ablation**: Extracting `GeometricHHNSW` directly from the exact `FAISS M=16` graph (`D6`) eliminates the v2 `M=8` vs. `M=16` base-graph confound, and the 4-way `InitEntryPortals` ablation (`H5v3`) cleanly isolates geometric express bridges (`101.0%–102.3%` gain retained at 0 portals) from portal seeding (`-0.56` to `+0.62` pts on FAISS).
4. **Cross-Domain Generalization & Honest Negative Tradeoffs**: Validating on both short-question BEIR Quora (`523k`) and long-passage BEIR NQ Wikipedia (`250k`) demonstrates robustness, and the authors transparently acknowledge where `hnswlib` and `pgvector` retain higher graph-only recall (`S <= 1%`, `S = 5%`).

---

## 4. Weaknesses & Major Issues

1. **Major — Incomplete RAM Accounting for `v3-full-guard-sq8` (`+1.91%` vs. `+24.8%`)**: Table I, Abstract, and Section III-B report `+32 B/node (+1.91%)` without disclosing the `+384 B/node` (`200.8 MB`, `+22.9%`) `sq8_vectors` buffer required by `v3-full-guard-sq8`. This materially alters comparisons against `ACORN-gamma` (`+224 B/node` level-0).
2. **Major — Unseparated Python `O(N)` Mask-Prep Overhead & Cold-Start `cpp-mode3-sq8`**: `FaissHNSWSystem`, `Acorn1System`, and `ExactBruteForceSystem` pay `~0.82 ms`+ of Python/NumPy `O(N)` mask permutation/packing inside `perf_counter_ns()`, inflating baseline latencies and exaggerating Mode 3 / `v3-geom-M8` speedups, while un-warmed `cpp-mode3-sq8` suffers `~2x` cold-page allocation penalties relative to `v3-full-guard-sq8`. Additionally, `H2v3`/`H3v3` latencies exclude `UBP` graph traversal time (`0.35–3.49 ms` in `H1v3`), which should be stated explicitly alongside Mode 3 latency claims.
3. **Major — Algorithm 2 / Code Fidelity Gap**: Algorithm 2 (`paper/prism_ann.tex:227-253`) shows only the hop-1 entry-point stall check (line 16), whereas `bench/prism_ckernel.cpp:800-827` implements **three** distinct stall triggers (hop-1 depleted entry, hop-16 sustained early depletion `early_mean < tau_stall || n_auth_found < k`, and post-loop `n_auth_found < k || mean_s_loc_hat < tau_stall`) plus an anti-starvation unauthorized-hop fallback (`lines 784-793`).
4. **Major — Single Operating Point (`efSearch = 64`) & Synthetic Hierarchy**: All graph baselines are evaluated at a single `(M=16, efc=64, efs=64)` setting rather than recall-vs-latency Pareto sweeps (`efSearch in {32, 64, 128, 256}`), leaving open how `ACORN-1`/`ACORN-gamma` or `v3-geom-M8` scale with higher `efSearch`. Moreover, the `L=4, b=8` balanced tree with random or spherical-$k$-means folder assignment is synthetic; real enterprise Zanzibar graphs often exhibit skewed multi-parent DAG fanout.
5. **Minor — Unexplained ACORN Collapse Mechanisms**: The paper notes `ACORN-1`/`ACORN-gamma` stall below $S \le 0.5\%$ without explaining why `ACORN-gamma` drops to `2.3` evals (`0.25%` R@10) or why `ACORN-1` underperforms `FAISS M=16` by `45.9` pts at $S=5\%$ (`31.66%` vs. `77.51%`).

---

## 5. Minor Presentation & Typography Issues

1. **IEEEtran `\paragraph{}` Formatting Glitch**: In `IEEEtran.cls`, `\paragraph{}` renders as enumerated `a)`, `b)`, `c)` subsubsection headings. This creates awkward orphaned `a)` headings with no `b)` on Page 4 (`a) Geometric Intra-Container...`) and Page 5 (`a) Two-Stage Exploratory...`), and starts Section VI directly with `a)` without an introductory sentence.
2. **Figure Ordering & Missing Cross-Reference**: `v3_fig5_h5_portal_ablation.pdf` appears as **Fig. 3** before `v3_fig3` (**Fig. 4**) and `v3_fig4` (**Fig. 5**), reversing `H3/H4/H5` order. Also, Fig. 5(b) (`H2v3 Native C++ / NEON Latency`) is never explicitly cited in Section V-C (`H2v3`).
3. **Minor Accuracy / Citation Nits**:
   - Line 268 describes `bench/prism_ckernel.cpp` as `972-line` (actual line count `973` with final newline / `972` newlines).
   - Reference `[19]` (`potineni2026engramrag`) omits co-authors (`L. Giri, A. Jain, V. Kutsyy, R. Pentakota` per `arxiv_metadata.txt`), listing only `B. Potineni`.
   - Reference `[6]` (`yalamarthi2026policy`) lists `Proc. ACM SIGMOD / arXiv:2606.19803`, whereas it appeared at the SIGMOD-colocated `SeQureDB '26` workshop.
   - `results/v3/DEVIATIONS.md` (`D7`) claims `hnsw.max_scan_tuples=20000` was set, though `bench/engines.py:532-537` relies on pgvector's default without issuing that `SET` command.
   - `Theorem 1` (`Algorithm 1` line 2) introduces `RevokedSubtrees(G_auth, zeta)`, which merits a brief sentence explaining how structural unlinks are tracked when edges are deleted from SpiceDB while immutable `Anc(v_i)` remains stamped on vectors (`ubp_resolver.py:108-117` uses `self.revoked_subtrees` / mirror tracking).
   - Float-dense pages (Pages 7 and 10 are ~85–90% floats with 4 lines of prose).

---

## 6. Questions for Authors

1. What is the pure C++ search latency of `FAISS M=16`, `ACORN-1`, and `ACORN-gamma` when `q.mask` is already in internal index ID space (excluding the `~0.82 ms` Python/NumPy permutation + `packbits`), and what is `v3-full-guard-sq8`'s end-to-end latency including live SpiceDB `ReadRelationships + UBP` (`2.72–3.49 ms`)?
2. Given that `v3-full-guard-sq8` allocates a `200.8 MB` (`384 B/node`) `sq8_vectors` buffer in addition to FP32 vectors, would Mode 3 FP32 (`prism_mode3_scan_ranges_f32`) eliminate that `+22.9%` RAM overhead while preserving `>2x` speedup over BLAS brute force?
3. How do `v3-geom-M8`, `ACORN-1`, and `ACORN-gamma` compare along a full `efSearch` Pareto curve (`32..512`), especially at $S=5\%$ where `v3-geom-M8` trails `hnswlib` by `3.97–5.60` pts?

---

## 7. Overall Assessment & Score

- **Rubric (1–10 Scale)**:
  - `1–3`: Flawed methodology, unverified claims, or major technical errors (Reject).
  - `4–5`: Interesting idea with major evaluation gaps or unfairness preventing publication as-is (Weak Reject / Major Revision).
  - `6`: Sound core contribution and strong provenance, but has substantive fairness/reporting omissions requiring targeted fixes before acceptance (Borderline / Weak Accept — Conditional on Revision).
  - `7–8`: Strong, well-validated systems paper ready for top-tier venue after minor polish (Accept).
  - `9–10`: Landmark paper (Strong Accept / Best Paper).
- **Independent Reviewer Score (Pass 1)**: **6.0 / 10**
- **Venue Recommendation (Pass 1)**: **Conditional Weak Accept / Minor-to-Major Revision** (for VLDB / SIGMOD / MLSys). The core engineering, multi-corpus reproducibility, live SpiceDB/PostgreSQL 17 integration, and `H5v3` ablation are genuinely strong, **but** the manuscript cannot be called camera-ready until it (1) discloses `v3-full-guard-sq8`'s `+200.8 MB` (`+22.9%`) SQ8 RAM overhead separately from `v3-geom-M8`'s `+1.91%`, (2) discloses/separates the `~0.82 ms` Python `O(N)` mask-prep overhead on `FAISS`/`ACORN`/`BLAS` and the cold-start `cpp-mode3-sq8` timing gap, and (3) aligns Algorithm 2 with `bench/prism_ckernel.cpp`.

---

## 8. Post-Revision Re-Review Addendum (Phase 20 Sign-Off Verification)

- **Reviewed Revised Artifact**: `/Users/tejap/memory_paper/paper/prism_ann.pdf` (12 pages, recompiled)
- **Verified PDF SHA-256**: `422f8f587f34b0ef8537c1a292ade3448822ab07e3b4eb15873694bc71826bf5`
- **Freeze & Reproducibility Verification**:
  - `FREEZE.md`: 5/5 `OK`; `FREEZE_v3.md`: 7/7 `OK` (all 12 frozen SHA-256 digests intact).
  - `bench.recompute_v3 --raw-dir results/v3/raw --check results/v3/summary.json`: `[recompute_v3] MATCH: results/v3/summary.json` (exit 0).
  - `verify_prism_hallucinations.py`: `SUMMARY: 238 checks passed, 0 errors.` (exit 0).
  - Direct `.venv-bench/bin/pytest -q tests/test_prism_v3_kernel.py tests/test_bench_provenance.py tests/test_prism_ann.py` (using new `pytest.ini`): `19 passed in 3.80s` without `PYTHONPATH=.`.
  - All 10 figure files (`paper/figures/v3_*.png|pdf`) remain hash-identical to Pass 1; zero files in `src/`, `bench/`, or `results/v3/raw/` were altered.

### Verification of Remediations

1. **Blocker 1 — SQ8 Buffer RAM Accounting: RESOLVED**
   - Abstract (`paper/prism_ann.tex:50`), Table I (`lines 76-77`), Contributions (`line 102`), Proposition 3 (`lines 227-230`), Section V-C `P2b` (`line 398`), Table V `D9` (`line 492`), Limitation #1 (`line 508`), Conclusion (`line 513`), and `results/v3/DEVIATIONS.md` (`D9`) now explicitly separate graph-only RAM overhead (`+32 B/n`, `+1.91%`) from the auxiliary full-vector SQ8 buffer (`+416 B/n`, `+24.8%`, `200.8 MB`), honestly acknowledging that full SQ8 buffering exceeds `ACORN-gamma`'s `+224 B/node` level-0 graph RAM while noting that `prism_mode3_scan_ranges_f32` avoids this copy at `0` extra vector RAM.
2. **Blocker 2 — Timing Boundary, Cold `cpp-mode3-sq8`, and End-to-End H1+H2 Latency: RESOLVED**
   - Section V-A (`line 302`, `Timing Boundary & Measurement Fairness`), Section V-C `P2c` (`line 399`), Table V `D9` (`line 492`), Limitation #2 (`line 508`), Abstract (`line 50`), Conclusion (`line 513`), and `results/v3/DEVIATIONS.md` (`D9`) explicitly document:
     - the `~0.823 ms` Python/NumPy `O(N)` `packbits`/permutation floor inside `faiss-hnsw-M16` (`~0.13 ms` pure C++ traversal) and similar `O(N)` NumPy marshaling in `acorn-1`/`acorn-gamma` and `exact-brute-force`;
     - un-warmed cold-page timing for `cpp-mode3-sq8` (`0.17–0.20 ms` cold vs `~0.05 ms` warm matching `v3-full-guard-sq8`);
     - exclusion of `H1v3` UBP graph-cut latency from `H2v3`/`H3v3`, alongside exact end-to-end `H1v3+H2v3` totals (`~0.45 ms` cached local-mirror UBP; `~3.6 ms` live persistent-Postgres SpiceDB `ReadRelationships+UBP`, yielding verified `5.5x–41x` over `hnswlib-M16` `19.83–147.18 ms` and `6.2x–19x` over `pgvector` `22.47–68.31 ms` at $S \le 1\%$).
3. **Blocker 3 — Algorithm 2 Fidelity to `bench/prism_ckernel.cpp`: RESOLVED**
   - Algorithm 2 (`paper/prism_ann.tex:232-267`) now matches `bench/prism_ckernel.cpp:784-827` 1:1, including the `|Q_cand| < 4` anti-starvation unauthorized-hub fallback (`lines 251-253`), `(a)` hop-1 depleted-entry guard (`lines 255-257`), `(b)` hop-16 sustained-depletion guard `h_chk=16` (`lines 258-260`), and `(c)` post-loop depletion guard (`lines 262-264`), cleanly linked from Section V-D (`line 440`).
4. **Non-Blocking Fixes & Remaining Trivial Nits: RESOLVED / ACCEPTED**
   - Verified fixes: `ACORN` collapse mechanism (`ACORN.cpp:898-926,1327` and 50k README defaults `0.40%` R@10 / `1.5` evals at `line 398`), removal of all `\paragraph{}` calls (zero orphaned `a)` headings in PDF), strict figure ordering `Fig. 1..5` matching `H1..H5` with `Fig. 4(b)` (`\ref{fig:v3_h4}(b)`) cited at `line 399`, `RevokedSubtrees` explanation (`line 202`), ref `[6]` (`SeQureDB Workshop`) and ref `[19]` (all 5 co-authors), `D7` alignment (`compiled default hnsw.max_scan_tuples=20000`), `pytest.ini`, and a balanced 12-page PDF layout (Table V + Refs `[5]..[19]` fill page 12 cleanly).
   - Remaining trivial non-blocking nits (do not impede acceptance): (i) `paper/prism_ann.tex:282` still writes `972-line` (matching `wc -l` newline count `972` vs `973` editor lines), (ii) `v3_fig5_h5_portal_ablation` retains `S=0.001` in the annotation box vs `S = 0.1%` tick labels (kept intentionally to preserve frozen figure hashes), and (iii) pure-C++ `O(N)`-prepacked baseline timings (`FAISS`/`ACORN`) and full Pareto `efSearch` sweeps are disclosed in Limitation #2 rather than re-run, properly preserving single-shot freeze discipline on `v3-confirmatory-001`.

### Updated Post-Revision Score & Verdict

- **Updated Independent Reviewer Score (Pass 2)**: **7.5 / 10**
- **Updated Venue Recommendation (Pass 2)**: **Accept — Ready for Publication (0 Blockers Remaining)**. All three substantive fairness/transparency/fidelity blockers from Pass 1 have been thoroughly resolved without altering frozen confirmatory data or code, leaving only negligible cosmetic/future-work nits already documented in Limitations.

---

## 9. v3.1 Supplementary Reviewer Audit Addendum (Phase 21 Sign-Off)

- **Reviewed Revised Manuscript**: `/Users/tejap/memory_paper/paper/prism_ann.pdf` (`12` pages, IEEEtran conference format)
- **Verified PDF SHA-256**: `98ca6c80aa2f63e7e8c0491ff76455604f6cd9aee36118baac4533dfaa21664c`
- **Clean Post-Freeze `v3.1` Run Verification**:
  - `FREEZE.md` (`5/5`), `FREEZE_v3.md` (`7/7`), and `FREEZE_v3_1.md` (`8/8`) SHA-256 manifests intact.
  - Pre-registered in `experiments/v3/PROTOCOL_v3_1.md` and executed zero-reuse on clean commit `e39260a` (`git_dirty=False`, `results/run_ledger.md` row `v3.1-reviewer-audit-001`), logging `22,533` raw JSONL records to `results/v3_1_audit/raw/v3_1_reviewer_audit.jsonl`.
  - Deterministic `bench.recompute_v3_1 --check results/v3/reviewer_audit_v3_1.json` exits `0` (`MATCH`), verifying `PR1`–`PR5` all `SUPPORTED`, `0` authorization leaks in `R2` (`0/1,200`) and `R4b` (`0/6,039` post-`ZedToken`), and `0/10,000` fuzzing mismatches in `R1`.
  - Visual & layout verification confirms Figure 6 (`v3_fig6_reviewer_audit.png`) resolves all label/legend collisions cleanly and Section V-G + Figure 6 integrate within the `12`-page camera-ready budget alongside updated Brakes 1, 2, and 3.

---

## 10. v3.2 Second-Round Research Audit Addendum (Phase 22 Sign-Off)

- **Reviewed Revised Manuscript**: `/Users/tejap/memory_paper/paper/prism_ann.pdf` (`12` pages, IEEEtran conference format)
- **Verified PDF SHA-256**: `c48a841794c5cb9959c71a4ee7d00e096d8cac2b26d7a47b4d16458585aed4a2`
- **Second-Round Remediation & `v3.2` Verification**:
  - **Theoretical Tightening**: Theorem 1 split into **Theorem 1** (Single-Parent Tree Token Compression Bound) and **Theorem 2** (Multi-Parent DAG Exact Set Equivalence under Deny-Dominates-Grant Precedence) with separate standalone proofs; **Corollary 1** scoped strictly to `$0$` vector writes and `$O(1)$` edge deletion relative to `$N_{\text{chunks}}$` alongside decomposed end-to-end propagation `$T_{\text{revoke}}$` and pre-/post-`$\zeta_{\text{rev}}$` boundaries; Exact vs. Empirical Recall@10 scope clarified in Abstract, Proposition 4, Section V-G, and Section VI-C.
  - **Literature & Novelty Positioning**: Added Nov. 2026 baselines **RACORN** (`arXiv:2607.00768v2`) and **EMA** (`arXiv:2606.00734v2`) to Table I, Section VI-B, and References `[17]`, `[18]`.
  - **Additive `v3.2` Empirical Verification (`R6`–`R8`)**: Executed zero-reuse on clean commit `a435bab` (`git_dirty=False`, `FREEZE_v3_1.md` `8/8` intact), logging `6,821` raw JSONL records to `results/v3_2_audit/raw/v3_2_reviewer_audit.jsonl` recomputed bit-for-bit by `bench/recompute_v3_2.py --check results/v3/reviewer_audit_v3_2.json`: `R6` (`0 / 5,000` multi-parent DAG mismatches, `PR6: SUPPORTED`), `R7` (Two-Track fairness vs. `RACORN-1` and `FP32` Mode 3, `0 / 1,500` leaks), and `R8` (shortlist exactness audit), transparently flagging `PR7` and `PR8` as `FALSIFIED` against strict fragmented depth-5 latency cutoffs (`0.434 ms > 0.35 ms`, `82.19x < 100x`, `0.329 ms > 0.25 ms`).
  - **Three-Tier Audience Suite**: Added [`docs/ONBOARDING_NEW_GRAD.md`](docs/ONBOARDING_NEW_GRAD.md), [`docs/ARCHITECTURE_SENIOR_ENGINEER.md`](docs/ARCHITECTURE_SENIOR_ENGINEER.md), and [`docs/RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md`](docs/RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md).
