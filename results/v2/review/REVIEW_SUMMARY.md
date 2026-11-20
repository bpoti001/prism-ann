# Prism-ANN v2 (Milestone 4) — Independent Provenance, Protocol, Integrity & Review Summary

- **Auditor**: Independent Reviewer (GSD Phase `15-01`)
- **Date**: 2026-11-20
- **Repo**: `/Users/tejap/memory_paper` (HEAD `819746d`, confirmatory run `v2-confirmatory-002` at `c819e65963d0ad26cf99909766b6f8add4f4e868`)
- **Policy Followed**: Zero modifications made to `paper/prism_ann.tex`, `bench/`, `src/`, or `results/v2/summary.json`.

---

## 1. Provenance-First Audit (Headline Numbers, Freeze, Recompute, Tests)

### 1.1 Freeze & Reproducibility Checks
- **`shasum -a 256 src/modules/prism_ann/*.py` vs. `FREEZE.md`**: **5/5 EXACT MATCH** (`__init__.py`: `c01944f4...`, `hnsw_gls.py`: `46705bce...`, `index.py`: `c224a8c1...`, `trimodal_planner.py`: `59cf1824...`, `ubp_resolver.py`: `9098e975...`). `git diff f6bcaa0..HEAD -- src/modules/prism_ann/` is completely empty.
- **`.venv-bench/bin/python -m bench.recompute --raw-dir results/v2/raw --check results/v2/summary.json`**: **`[recompute] MATCH: results/v2/summary.json`** (bit-for-bit match across all 62,410 raw records: H1=2,400, H2=48,000, H3=12,000, H4=10; every record carries `run_id="v2-confirmatory-002"`, `run_type="confirmatory"`, `git_sha="c819e65963d0ad26cf99909766b6f8add4f4e868"`, `freeze_match=True`).
- **`.venv-bench/bin/python -m unittest tests/test_bench_provenance.py -v`**: **9/9 OK** (`0` skipped).
- **`.venv-bench/bin/python verify_prism_hallucinations.py`**: **127/127 checks passed, 0 errors**.

### 1.2 Independent End-to-End Trace of Headline Numbers (Raw JSONL -> Code -> Paper)
I independently parsed `results/v2/raw/v2-confirmatory-002__H{1,2,3,4}.jsonl` in Python (`scipy.stats.t`) without calling `bench/recompute.py` and traced 6 headline numbers across H1–H4:

1. **H1v2 (`P1a`, `P1c`): `0` mismatches across `600` principals; `226.5x` (`0.310 ms` vs. `70.15 ms`) and `33.6x` (`2.089 ms`) broad-principal speedup** (`paper/prism_ann.tex:46,297,299,325`):
   - *Generating code*: `bench/experiments.py:160-237` (invoking `SpiceDBService` gRPC `LookupResources` / `ReadRelationships` in `bench/engines.py:210-249`, `ZanzibarAuthGraph.upward_boundary_prune` in `src/modules/prism_ann/ubp_resolver.py:218-300`, and symmetric `pyroaring.BitMap` unions).
   - *Raw JSONL (`v2-confirmatory-002__H1.jsonl`, 2,400 records)*: `600` `H1-oracle-check` records (200/seed × 3 seeds) sum to `mismatch_docs = 0`, `mismatch_chunks = 0`, `mismatch_strict_chunks = 0`, `within_bound = 600/600 True`, `tokens_pos` median `76.0` / max `296`. Across `n = 274` broad principals (`n_auth_docs >= 1000`), pooled medians are `0.3097 ms` (`UBP+bitmap`), `2.0889 ms` (`SpiceDB-ReadRelationships+UBP+bitmap`), and `70.1500 ms` (`SpiceDB-LookupResources+leaf-bitmap`), giving `70.1500 / 0.3097 = 226.52x` and `70.1500 / 2.0889 = 33.58x`. **Confirmed exact.**
2. **H2v2 (`P2a`): `prism-graph-only` Recall@10 = `28.21%` vs. `faiss-hnsw-M16` `5.95%` (`+22.25 ± 2.54 pts`) at `S=0.1%`, and `45.93%` vs. `22.44%` (`+23.49 ± 2.19 pts`) at `S=0.5%`** (`paper/prism_ann.tex:46,301,346,352,364`):
   - *Generating code*: `bench/experiments.py:272-366` and `bench/systems.py:61-143,407-448` (`FaissHNSWSystem` + `PrismGraphOnlySystem` calling frozen `search_hnsw_gls`).
   - *Raw JSONL (`v2-confirmatory-002__H2.jsonl`, 48,000 records)*: Per `S`, 1,500 records/system (500 queries × 3 seeds). Independent aggregation gives `prism-graph-only` `28.21 ± 2.42%` (`dist 664.7 ± 5.8`, `med_lat 7.46 ms`) and `faiss-hnsw-M16` `5.95 ± 1.32%` (`dist 797.9 ± 6.8`, `med_lat 0.93 ms`) at `S=0.001`; `45.93 ± 1.09%` vs. `22.44 ± 1.74%` at `S=0.005`. **Confirmed exact.**
3. **H2v2 (`P2b` FALSIFIED): `acorn-1` Recall@10 = `0.85%` (`dist 11.4`) at `S=0.1%`, `dist_ratio` `1.04x–58.50x`** (`paper/prism_ann.tex:46,302,348,365`):
   - *Generating code*: `bench/systems.py:146-230`, `bench/acorn_cwrap.cpp:65-95` calling compiled upstream C++ `stanford-futuredata/ACORN` (`acorn_stats.n3 + 1`).
   - *Raw JSONL (`v2-confirmatory-002__H2.jsonl`)*: `acorn-1` at `S=0.001` yields `0.85 ± 0.10%` Recall@10 and `11.362` (`11.4 ± 1.4`) distance evals (`664.7 / 11.362 = 58.50x`), rising to `1254.7` vs. `1301.0` (`1.037x`) at `S=0.05`. **Confirmed exact.**
4. **H2v2 (`hnswlib` & `pgvector` baseline superiority + `prism-full` Mode 3): `hnswlib` `99.91%` (`131.52 ms`), `pgvector` `75.49%` (`338.15 ms`, P95 `915.1 ms`), `prism-full` `100.00%` (`1.10 ms`) at `S=0.1%`** (`paper/prism_ann.tex:46,88,349-353,366`):
   - *Generating code*: `HnswlibSystem` (`bench/systems.py:232-286`), `PgvectorSystem` + `PostgresPgvectorService` (`bench/engines.py:357-417`), `PrismFullSystem` (`bench/systems.py:451-482`).
   - *Raw JSONL (`v2-confirmatory-002__H2.jsonl`)*: Independent recomputation matches every number (`99.91 ± 0.08%`, `131.52 ms`; `75.49 ± 1.03%`, `338.15 ms` median / `915.10 ms` P95; `100.00 ± 0.00%`, `510.7` evals, `1.10 ms`). **Confirmed exact.**
5. **H3v2 (`P3a` supported, `P3b` FALSIFIED): `r <= 0.5` (`n=735`) `+17.65 ± 3.09 pts` (`23.34%` vs. `5.68%`); `r >= 2.0` (`n=751`) `588.8` vs. `3,136.1` evals (`0.188x` / `5.33x` fewer) with `-2.00 pts` Recall@10 (`97.10%` vs. `99.09%`)** (`paper/prism_ann.tex:46,305-306,387-395,404-407`):
   - *Generating code*: `bench/experiments.py:391-509` (`r_measured = s_loc_100 / s_actual`), `search_hnsw_gls` with `use_gls_adaptive=True` vs. `False`.
   - *Raw JSONL (`v2-confirmatory-002__H3.jsonl`, 12,000 records)*: Independent binning reproduces `n=735` (`23.34 ± 4.52%` vs. `5.68 ± 1.85%`, `534.0` vs. `795.1` evals) and `n=751` (`97.10 ± 0.42%` / `588.8` evals vs. `99.09 ± 0.57%` / `3,136.1` evals). **Confirmed exact.**
6. **H4v2 (`P4a`, `P4b`): SpiceDB revocation `76.05 ms` (`0` vector writes) vs. PostgreSQL/`pgvector` `UPDATE` `182.5 s` (`182,526.4 ms`, `2,400.1x` slower) over `1,024` docs / `153,600` rows** (`paper/prism_ann.tex:46,308-309,420`):
   - *Generating code*: `bench/experiments.py:582-665` (`sp.delete_parent_edge` + mirror + UBP + CRoaring vs. `pg.update_acl_for_folder` in `bench/engines.py:419-427`).
   - *Raw JSONL (`v2-confirmatory-002__H4.jsonl`, 10 records)*: `5` trials per system; medians `76.0487 ms` (`min 62.1224`, `max 170.8728`, `vector_writes=0`) and `182,526.3982 ms` (`min 180,486.2911`, `max 219,252.6126`, `rows_affected=153,600`). Ratio `2,400.12x`. **Confirmed exact.**

---

## 2. Protocol & Honesty Audit (`experiments/v2/PROTOCOL_v2.md`)

- **Query Disjointness**: Independently verified against `data/beir/quora/corpus.parquet` (`522,931`), `queries.parquet`, `qrels_test.tsv`, and `query_ids_disjoint.json` (`9,985`): **0 ID overlap, 0 text overlap**, all 4,624 distinct H2 query IDs and 1,414 distinct H3 query IDs in raw JSONL belong strictly to `query_ids_disjoint.json`.
- **Seeds, CIs & All 4 Hypotheses**: 3 seeds (`0, 1, 2`) with 95% $t$-CIs across H1–H3 (5 trials for H4); all 10 pre-registered predictions (`P1a`–`P4b`) reported verbatim. Falsified predictions `P2b` and `P3b`, plus where `hnswlib` and `pgvector` outperform `prism-graph-only`, are foregrounded in Abstract, Table II, Figures 2–3, §V-C/D, and §VI.
- **Upstream `ACORN` Patch (`D5`)**: Diffed the exact source checkout recorded in `bench/_build/libacorn_faiss.dylib` (`/Users/tejap/.gemini/antigravity/brain/633092f6-1277-42e2-81f5-7140dd9d6bb2/scratch/acorn_src`) against clean upstream `stanford-futuredata/ACORN` (`c259f11cdbec` at `/Users/tejap/src/ACORN`). Confirmed the only code changes are a 1-line CMake generator-expression fix and the 3-line C++ memory-safety patch (`ACORN.cpp:757,829` negative `nodeId` guard before `metadata[nodeId]`; `ACORN.cpp:1060` `ep_per_level(max_level + 1)`), plus `bench/acorn_cwrap.cpp` selector/metric wiring—**zero algorithmic skew**.
- **Theorems 2–4 Reclassified**: Confirmed `paper/prism_ann.tex:202-263` retains Theorem 1 & Corollary 1 and explicitly reclassifies percolation/crossover claims as **Propositions 2–4 under stated assumptions**.
- **Completeness of `DEVIATIONS.md` & Table V**: All 9 deviations (`D1`–`D9`) are mirrored consistently across `results/v2/DEVIATIONS.md` and `paper/prism_ann.tex:422-443` (`tab:deviations`).

---

## 3. Integrity Scan

- **Software Factory Sensors (Node run against `/Users/tejap/memory_paper`, 63 scanned files)**:
  - `checkBenchmarkEmpiricalPurity`: **0 violations** (clean).
  - `checkReadPathPurity`: **0 violations** (clean).
  - `checkFileSizeCeiling`: **0 violations** (clean; max < 1,000 lines).
  - `checkLatexCitationBijection`: **PASSED** (19 cited keys = 19 defined bibitems, 0 missing, 0 unused).
  - `checkNoScriptedVerdicts`: **0 violations in v2 files** (`run_prism_paperviz_audit.py` and `run_prism_scholarpeer_review.py` are clean; only legacy EngramRAG v0/v1 root files `run_paperviz_audit.py` and `run_scholarpeer_review.py` still trigger).
  - `checkRawRecordProvenance`: Flags 8 legacy v1/EngramRAG `results/*.json` files (`missing-raw-jsonl-records`) and flags `results/v2/summary.json` as `summary-newer-than-raw-records` (`15:24:26` vs. `15:24:08`, an 18-second false positive caused by running `bench.recompute` after `bench.harness` — see Sensor Improvements below).
- **Manual Audit of `bench/` and `bench/plot_v2.py`**: Zero hardcoded or formula-generated metrics in `bench/harness.py`, `bench/experiments.py`, `bench/systems.py`, `bench/recompute.py`, `bench/verdicts.py`. One minor literal string (`"11.4 evals, 0.85% R@10"`) appears in `bench/plot_v2.py:191` (matches `summary.json` exactly, though should be interpolated).
- **Anti-v1 / Anti-Scripted-Score Scan of `paper/prism_ann.tex`**: Zero occurrences of v1 metrics, `LoCoMo`, `ScholarPeer`, `PaperViz`, or `camera-ready`.
- **Brake 2 & Brake 3 SHA-256 Binding Scripts**: Verified after writing `figure_review.md` and `peer_review.md` (executed below).

---

## 4. Severity-Ranked Findings

### Blockers (Must Fix Before Submission)
1. **[BLOCKER] `paper/prism_ann.tex:81` — Unedited Writing-Template Placeholders in Introduction**:
   Line 81 of `paper/prism_ann.tex` (and page 1 of compiled `paper/prism_ann.pdf`) reads:
   `Prism-ANN (X) is designed for multi-tenant Ontology and Relationship-Based Access Control (ReBAC) filtered retrieval (Y) over HNSW vector indexes (Z).`
   These literal `(X)`, `(Y)`, `(Z)` scaffold markers must be removed before manuscript submission.

### Non-Blocking Issues
2. **[Non-Blocking / Experimental Completeness] `src/modules/prism_ann/hnsw_gls.py:362-375` — Missing Ablation for `InitEntryPortals` vs. Express Bridges**:
   `search_hnsw_gls` seeds `cand_queue` with up to 4 authorized IDs from `valid_indices`, while `faiss-hnsw-M16` and `acorn-1` start from a single global entry node. An ablation disabling `InitEntryPortals` is needed to isolate the contribution of $M_{\text{bridge}}=4$ ring-chord edges from authorized entry seeding.
3. **[Non-Blocking / Analysis Gap] `paper/prism_ann.tex:395,404-408` & `bench/systems.py:451-482` — Unreported `prism-full` Collapse in H3 ($S=2\%, r \le 0.5$) & Mode 3 vs. `exact-brute-force` Latency**:
   In H3 `r <= 0.5`, `prism-full` hits only `24.55%` Recall@10 because `n_cand` (~10,243) exceeds Mode 3's `0.015 * N` (`7,844`) cutoff on `725/735` depleted queries (`v2-confirmatory-002__H3.jsonl`). Additionally, §V-C does not discuss why BLAS `exact-brute-force` (`0.25–1.94 ms`) beats `prism-full` (`1.10–2.14 ms`) at $S \le 1\%$ (Python `from_bool_mask` + `sq8_vectors` `.astype(np.int32)` overhead).
4. **[Non-Blocking / Baseline Framing] `bench/systems.py:270` & `paper/prism_ann.tex:366` — `hnswlib` Python Callback FFI Overhead**:
   `hnswlib-M16` uses a Python lambda filter callback per visited node via `pybind11`, inflating its `131.52 ms` latency beyond pure C++ graph traversal; the prose should note this FFI cost alongside `C++/Py-cb` in Table III.
5. **[Non-Blocking / Visual] `paper/figures/v2_fig2_h2_selectivity_sweep.png` (`bench/plot_v2.py:153-162`) — Line Occlusion at $y=100\%$**:
   `Prism full`, `hnswlib`, and `Exact brute force` overlap at `100%` for $S \le 1\%$, hiding `Exact brute force` and partially masking `hnswlib`.
6. **[Non-Blocking / Figure Consistency] `bench/plot_v2.py:191,302-304,92-118`**:
   - Line 191 uses literal `"11.4 evals, 0.85% R@10"` instead of f-string interpolation from `summary.json`.
   - Fig. 4a annotates `76.0 ms` / `2400x slower` vs. `76.05 ms` / `2,400.1x` in caption/text; Fig. 1a plots 3-seed mean of medians (`70.13`, `0.31`) while the box quotes pooled-median ratios (`226.5x`).
7. **[Non-Blocking / Typography] `paper/prism_ann.tex:218,448,451,454` — Double Punctuation `.:` in IEEEtran `\paragraph{... .}`**:
   Trailing periods inside `\paragraph{...}` render as `.:` on Pages 4, 8, and 9.
8. **[Non-Blocking / Repo Hygiene] Legacy v1 Root Artifacts & Untracked `summary_smoke.json`**:
   Superseded v0/v1 scripts (`run_paperviz_audit.py`, `run_scholarpeer_review.py`) and `results/*.json` remain at repo root and trip repo-wide sensors; untracked `results/v2/summary_smoke.json` sits next to `raw/` rather than `raw_smoke/`.

---

## 5. Verdict

- **Provenance & Protocol Integrity**: **READY / VERIFIED** — All v2 numbers trace bit-for-bit from `paper/prism_ann.tex` -> `results/v2/summary.json` -> `results/v2/raw/*.jsonl` -> frozen `src/modules/prism_ann/` (`FREEZE.md` 5/5 SHA-256 match), with disjoint held-out queries, fair upstream C++ `ACORN-1` safety patch, and honest reporting of falsified `P2b`/`P3b` and baseline wins.
- **Manuscript Readiness**: **BLOCKED (1 Blocker)** — Fix the `(X)/(Y)/(Z)` template placeholders at `paper/prism_ann.tex:81` (and recompile `paper/prism_ann.pdf` + re-run Brake 3 review on the updated PDF hash) before submission; address the non-blocking visual, ablation, and discussion items as time permits.

---

## 6. Suggested Software Factory Sensor Improvements

1. **Fix False Positive in `checkRawRecordProvenance` (`sensors.mjs:626-639`)**:
   Flagging `summaryMtimeMs > maxRawMtimeMs` guarantees a false positive whenever `recompute.py` runs *after* `harness.py` finishes writing `raw/*.jsonl` (here, `15:24:26` vs. `15:24:08`, 18 seconds later). Replace or gate the mtime heuristic by actually executing `bench/recompute.py --check <summary.json>` (or only flagging if recomputation mismatches), and pair `summary_smoke.json` with `raw_smoke/` rather than ignoring it when `raw/` exists.
2. **Extend `checkDynamicReportInterpolation` (`sensors.mjs:427`) to Plotting Scripts**:
   Plotting scripts (`bench/plot_*.py`, `generate_*_plots.py`) currently bypass `checkDynamicReportInterpolation`, allowing literal annotation numbers (`bench/plot_v2.py:191`) to slip past. Adding `*plot*.py` to the scan regex closes this blind spot.
3. **Add a LaTeX Template-Placeholder & Punctuation Hygiene Sensor**:
   Scanning `*.tex` for unedited scaffold tokens (`(X)`, `(Y)`, `(Z)`, `TBD`, `TODO`, `XX%`, `??`) and IEEEtran `\paragraph{... .}` double punctuation (`.:`) would have caught `paper/prism_ann.tex:81` automatically prior to review.
4. **Add Scope / Superseded-Artifact Filtering (`v2` vs. archived `v1`)**:
   `checkNoScriptedVerdicts` and `checkRawRecordProvenance` currently scan superseded v0/v1 root files (`run_paperviz_audit.py`, `results/*.json`), obscuring whether the active evaluation path is clean. Support an explicit scope config or archive-directory exclusion so active-milestone verification yields clean pass/fail signals.
5. **Add Raw-Record Internal Consistency & Leakage Checks**:
   Verify inside `checkRawRecordProvenance` that all `raw/*.jsonl` records share a consistent `git_sha` and `freeze_match === true`, and check for a query-corpus disjointness verification artifact when `dataset.py` encodes held-out queries.
