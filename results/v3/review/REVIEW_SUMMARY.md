# Milestone 5 (Prism-ANN v3) Independent Review Summary

- **Manuscript Reviewed (Pass 1 Initial)**: `paper/prism_ann.pdf` (`sha256: 6d07a4434193f6c91575656f0219124081d5ce7e3391be1ab9f6546e1ecbdc37`) — Score **6.0 / 10** (Conditional Weak Accept; 3 Blockers)
- **Manuscript Reviewed (Pass 2 Sign-Off)**: `paper/prism_ann.pdf` (12 pages, `sha256: 422f8f587f34b0ef8537c1a292ade3448822ab07e3b4eb15873694bc71826bf5`) — Score **7.5 / 10** (**READY / ACCEPT — 0 Blockers Remaining**, see Section `(c)` Pass 2 Sign-Off below)
- **Provenance Status**: `FREEZE.md` (5/5), `FREEZE_v3.md` (7/7), `bench.recompute_v3 --check` (bit-for-bit MATCH over 169,810 raw JSONL records, 0 authorization leaks), query disjointness (`[0..499]` dev vs. `[500..9,984]` Quora & disjoint `250k` NQ), `verify_prism_hallucinations.py` (238/238), and direct `.venv-bench/bin/pytest` (19/19 via `pytest.ini`) all **PASS**.

---

## (a) Blockers (MUST Fix Before Calling Manuscript Ready)

1. **Unreported SQ8 Quantization Memory in RAM Claims (`+1.91%` vs. `+24.8%`)** — *Severity: High / Scientific Fairness*
   - **Evidence**: [`paper/prism_ann.tex:72`](file:///Users/tejap/memory_paper/paper/prism_ann.tex#L72) (Table I), [`paper/prism_ann.tex:46`](file:///Users/tejap/memory_paper/paper/prism_ann.tex#L46), [`paper/prism_ann.tex:224`](file:///Users/tejap/memory_paper/paper/prism_ann.tex#L224), and [`src/modules/prism_ann/trimodal_planner.py:194-196`](file:///Users/tejap/memory_paper/src/modules/prism_ann/trimodal_planner.py#L194-L196).
   - **Finding**: `+32 B/node (+1.91% at d=384)` accounts only for `v3-geom-M8` bridge edges (`16.73 MB`), ignoring `ZOrderedCorpus.sq8_vectors` (`522,931 * 384 * 1 B = 200.8 MB`, `+384 B/node`, `+22.9%` over base HNSW) retained alongside FP32 vectors by `v3-full-guard-sq8`. Combined extra RAM for `v3-full-guard-sq8` is `+416 B/node (+24.8%)`—nearly `2x` `ACORN-gamma`'s level-0 extra RAM (`+224 B/node`). Table I and Proposition 3 must explicitly distinguish graph-only `v3-geom-M8` (`+1.91%`) from `v3-full-guard-sq8` (`+24.8%` with SQ8 buffer).

2. **Undisclosed Python `O(N)` Mask-Prep Asymmetry & Cold-Start `cpp-mode3-sq8` Timing** — *Severity: High / Timing Fairness*
   - **Evidence**: [`bench/systems.py:48-51,131-133,210`](file:///Users/tejap/memory_paper/bench/systems.py#L131-L133), [`bench/harness_v3.py:379-382,478`](file:///Users/tejap/memory_paper/bench/harness_v3.py#L379-L382), [`bench/run_v3_dev_exploratory.py:83-105,178-194`](file:///Users/tejap/memory_paper/bench/run_v3_dev_exploratory.py#L83-L105), and [`paper/prism_ann.tex:352-360,384`](file:///Users/tejap/memory_paper/paper/prism_ann.tex#L384).
   - **Finding**:
     - Both `cpp-mode3-sq8` (`0.170–0.201 ms`) and `v3-full-guard-sq8` (`0.093–0.109 ms`) run the identical `_compile_ranges_from_tokens` + `mode3_scan_ranges_sq8` path at $S \le 1\%$; the ~2x gap on Quora is a cold-memory allocation/demand-paging artifact (`cpp-mode3-sq8` runs un-warmed right after ~1.0 GB `ZOrderedCorpus` allocation: measured `0.2019 ms` cold vs. `0.0517 ms` warm).
     - `FaissHNSWSystem.search` runs `q.mask[internal_to_orig]` + `np.packbits` over $N=522{,}931$ elements inside `perf_counter_ns()` (`0.823 ms` median overhead alone out of `0.950 ms` total, leaving only `~0.13 ms` for C++ FAISS traversal), and `Acorn1System`/`ExactBruteForceSystem` similarly execute `O(N)` NumPy permutation / `np.flatnonzero` + gather inside the timer, while Prism systems receive pre-resolved `ubp_tokens` (excluding `H1` UBP resolution latency). The paper must disclose this Python marshaling floor and separate C++ kernel latency from `O(N)` mask conversion (and state clearly that `H2`/`H3` latencies exclude UBP graph traversal).

3. **Algorithm 2 vs. C++ Kernel Fidelity Mismatch** — *Severity: Medium-High / Technical Accuracy*
   - **Evidence**: [`paper/prism_ann.tex:227-253`](file:///Users/tejap/memory_paper/paper/prism_ann.tex#L227-L253) vs. [`bench/prism_ckernel.cpp:784-827`](file:///Users/tejap/memory_paper/bench/prism_ckernel.cpp#L784-L827).
   - **Finding**: Algorithm 2 shows only the hop-1 `expansions == 1` entry-point stall check (lines 16–18), omitting the C++ kernel's hop-16 sustained-depletion check (`early_mean < tau_stall || n_auth_found < k`), post-loop depletion check (`n_auth_found < k || mean_s_loc_hat < tau_stall`), and `cand_queue.size() < 4` anti-starvation fallback.

---

## (b) Non-Blocking Improvements

1. **Explain ACORN Collapse Mechanistically** ([`ACORN.cpp:898-926,1327,766-787,1290`](file:///Users/tejap/src/ACORN/faiss/impl/ACORN.cpp#L1327)): Explain why `acorn-gamma` terminates with `1–2` distance evals (`0.25%` R@10) at $S=0.1\%$ (confirmed even under `ACORN/README.md`'s `gamma=12, M_beta=32, efConstruction=128` at `0.40%` R@10 / `1.5` ndis) and why `acorn-1` scores `31.66%` at $S=5\%$.
2. **Fix IEEEtran `\paragraph{}` Orphaned `a)` Headings & Figure Order** ([`paper/prism_ann.tex:214,274,485`](file:///Users/tejap/memory_paper/paper/prism_ann.tex#L214)): Replace single-use `\paragraph{}` calls producing `a)` without `b)`, reorder `Fig. 3` (`H5`) / `Fig. 4` (`H3`) / `Fig. 5` (`H4`) to match `H1..H5`, and cite `Fig. 5(b)` in Section V-C.
3. **Add `efSearch` Pareto Sweep**: Extend beyond the single `efSearch = 64` operating point in follow-up revision or appendix.
4. **Minor Polish & Metadata Fixes**:
   - Unify `S=0.001` vs. `S=0.1%` notation in `v3_fig5`, and remove empty y-spine headroom above `100%` in `v3_fig3(a)`.
   - Fix `972-line` -> `973-line` (`prism_ckernel.cpp`), add all co-authors to ref `[19]` (`potineni2026engramrag`), note `SeQureDB '26` for ref `[6]`, and align `DEVIATIONS.md` (`D7`) regarding `hnsw.max_scan_tuples` (default `20000` vs. explicit `SET`).
   - Add `PYTHONPATH=.` note or `pythonpath = .` in pytest config so `.venv-bench/bin/pytest` works without manual `PYTHONPATH=.`.

---

## (c) Final Verdict

- **Pass 1 Initial Verdict**: **NOT YET READY FOR FINAL CAMERA-READY RELEASE (3 Blockers)** — Score **6.0 / 10** (see Pass 1 blockers above: SQ8 buffer RAM omission in Table I/Prop. 3, unseparated `~0.82 ms` Python `O(N)` mask-prep bias / cold `cpp-mode3-sq8` timing, and Algorithm 2 divergence from `prism_ckernel.cpp`).

### Post-Revision Sign-Off (Pass 2)

- **Verified Revised PDF**: `paper/prism_ann.pdf` (12 pages, SHA-256 `422f8f587f34b0ef8537c1a292ade3448822ab07e3b4eb15873694bc71826bf5`)
- **Pass 2 Verification Status**:
  - `FREEZE.md` (5/5 `OK`) and `FREEZE_v3.md` (7/7 `OK`) verified intact; all 10 `paper/figures/v3_*.png|pdf` hashes unchanged; zero modifications in `src/`, `bench/`, or `results/v3/raw/`.
  - `bench.recompute_v3 --raw-dir results/v3/raw --check results/v3/summary.json` -> `[recompute_v3] MATCH: results/v3/summary.json` (exit 0).
  - `verify_prism_hallucinations.py` -> `SUMMARY: 238 checks passed, 0 errors.` (exit 0).
  - `.venv-bench/bin/pytest -q tests/test_prism_v3_kernel.py tests/test_bench_provenance.py tests/test_prism_ann.py` (with new `pytest.ini`, without `PYTHONPATH=.`) -> `19 passed in 3.80s`.
- **Blocker Disposition**:
  - **Blocker 1 (SQ8 RAM Accounting) — RESOLVED**: Abstract (`line 50`), Table I (`lines 76-77`), Contributions (`line 102`), Proposition 3 (`lines 227-230`), Section V-C `P2b` (`line 398`), Table V `D9` (`line 492`), Limitation #1 (`line 508`), Conclusion (`line 513`), and `results/v3/DEVIATIONS.md` (`D9`) explicitly split graph-only `+32 B/n` (`+1.91%`) from `+416 B/n` (`+24.8%`, `200.8 MB` auxiliary SQ8 buffer).
  - **Blocker 2 (Timing Boundary, Cold `cpp-mode3-sq8`, End-to-End H1+H2) — RESOLVED**: Section V-A (`line 302`), Section V-C `P2c` (`line 399`), Table V `D9` (`line 492`), Limitation #2 (`line 508`), Abstract (`line 50`), Conclusion (`line 513`), and `DEVIATIONS.md` (`D9`) disclose the `~0.823 ms` Python `O(N)` mask-prep floor, cold vs warm `cpp-mode3-sq8` (`0.17–0.20 ms` cold vs `~0.05 ms` warm), and end-to-end `H1v3+H2v3` totals (`~0.45 ms` cached local-mirror UBP; `~3.6 ms` live SpiceDB `ReadRelationships+UBP`).
  - **Blocker 3 (Algorithm 2 Fidelity) — RESOLVED**: Algorithm 2 (`paper/prism_ann.tex:232-267`) now matches `bench/prism_ckernel.cpp:784-827` 1:1 (`|Q_cand| < 4`, hop-1 guard, hop-16 guard `h_chk=16`, post-loop guard).
  - **Non-Blocking Fixes**: All verified (`ACORN.cpp` collapse mechanism, `\paragraph{}` removal, `Fig. 1..5` order + `Fig. 4(b)` citation, `RevokedSubtrees` text, refs `[6]` & `[19]`, `D7` wording, `pytest.ini`, balanced 12-page PDF). Remaining trivial nits (`972-line` `wc -l` vs `973` line count, `S=0.001` box in `Fig. 5`, pure-C++ `O(N)`-prepacked baseline sweep deferred cleanly to Limitations) are non-blocking.
- **Updated Score & Final Verdict**: **7.5 / 10 — READY / ACCEPT (0 Blockers Remaining)**.

---

## (d) Suggested Software-Factory Sensor Improvements

Running `/Users/tejap/software_factory/src/modules/sensors/lib/` (`sensors.mjs`, `research-sensors.mjs`, `provenance-sensors.mjs`) against `/Users/tejap/memory_paper` revealed five concrete sensor gaps:

1. **`checkBenchmarkEmpiricalPurity` Filename Blind Spot (`research-sensors.mjs:111`)**: `BENCHMARK_FILE_REGEX` only scans `/(?:^|\/)(?:run_.*benchmark|.*benchmark.*)\.(?:py|mjs|js|ts)$/i`, completely skipping `bench/harness_v3.py`, `bench/systems.py`, `bench/experiments.py`, `bench/run_v3_dev_exploratory.py`, `bench/plot_v3.py`, and `.cpp` kernels. Expand the glob to cover `bench/**/*.(py|cpp|c)` and `**/plot_*.py`.
2. **Legacy Root-Script Contamination Noise (`research-sensors.mjs:199,251`)**: `runSensors` flagged `run_paperviz_audit.py` (`24` violations) and `run_scholarpeer_review.py` (`33` violations) alongside `results/*.json` (`8` raw-record violations) from an older archived paper in the same repo, and `latex-citation-bijection` (`sensors.mjs:62-71`) combined an unrelated `.bib` (`paper/references.bib` from `main.tex`) with `paper/prism_ann.tex`. Scope citation bijection per `.tex` build root (`\bibliography{}` vs. inline `thebibliography`) and distinguish active target artifacts from legacy archived manuscripts.
3. **`checkRawRecordProvenance` Only Checks `bench/recompute.py` & `mtime` (`provenance-sensors.mjs:59-127`)**: Checking only for existence of `bench/recompute.py` misses versioned recomputers (`bench/recompute_v3.py`), and `summaryMtimeMs >= maxRawMtimeMs` does not verify `--check` parity or `freeze_match_all`. Add optional execution of `recompute*.py --check` and inspect `freeze_match_all` in `summary*.json`.
4. **Missing Benchmark Timing-Fairness / Warmup & Memory-Accounting Sensors**: Current sensors do not detect (a) `O(N)` Python/NumPy array permutations/copies (`mask[perm]`, `np.packbits`, `np.flatnonzero`) inside per-query timed `search()` methods when competing systems take pre-compiled range tokens, (b) missing warmup before cold `O(100MB+)` array scans (`cpp-mode3-sq8`), or (c) auxiliary quantized buffers (`sq8_vectors`) omitted from `memory_footprint_bytes()` / RAM claims.
5. **ADR Section Header Compatibility (`doc-sensors.mjs`) & `checkFileSizeCeiling` Language Gap (`research-sensors.mjs:384`)**: All 6 ADRs (`docs/adr/0000..0005`) failed `requiredSections` due to header naming mismatch, and `checkFileSizeCeiling` skips `.cpp`/`.tex` files (leaving `973`-line C++ kernels unchecked).
