# Neon High-Thinking Gate-6 Adversarial Review & 3-Brake Audit (`ENH-0010` Live Build)

- **Target Repository**: `/Users/tejap/memory_paper` (`Prism-ANN` Live Empirical Build `ENH-0010`, `N = 10,000` `LoCoMo` chunks, `d = 128`)
- **Reviewer Persona**: `@neon-reviewer` (`thermo-nuclear-code-quality-review`, `blast-radius`, `adr-to-arxiv-factory`, `systems-paper-writing`, `ml-paper-writing`)
- **Date**: 2026-11-19
- **Final Gate-6 Verdict**: **CONDITIONAL PASS / CHANGES REQUESTED FOR CAMERA-READY** *(All automated sensors, unit tests, 376-scenario Blast Radius proof, GSD `ADR-0006` parity, and `audit-paper` CLI checks pass exit code `0`, while deep adversarial inspection uncovered 3 substantive blockers that must be resolved before final submission.)*

---

## 1. Executive Summary & Automated Gate Scorecard

`@hydrogen-builder`'s `ENH-0010` pass genuinely eliminated every hardcoded benchmark curve from `run_prism_ann_benchmarks.py`, replacing them with live `N = 10,000` `LoCoMo` embeddings, live `ZanzibarAuthGraph` traversals, live `actual_memory_bytes()` accounting, live `search_pgvector_iterative()`, and an upgraded $O(m \cdot L^2)$ upward taint computation in `ubp_resolver.py`. All Software Factory Node sensors (`checkReadPathPurity` = `[]`, `checkBenchmarkEmpiricalPurity` = `[]`, `checkLatexCitationBijection` = `true` for `18/18` references), all `4/4` seam TDD unit tests (`0.145s`), all `376/376` Blast Radius zero-leakage scenarios, GSD `ADR-0006` (`12/12` phases traced), and `python3 research_factory.py audit-paper` (`258/258` Brake-1 checks, PaperViz `97.72/100`, ScholarPeer `9.0/10`) pass with exit code `0`.

However, applying strict **Thermo-Nuclear Code Quality** and **Adversarial Peer Review** beyond regex sensors caught three real issues that automated scripts missed: (1) an omitted-selectivity metric contradiction at $S = 0.50$ (`92.6%` Recall@10, `40.53 ms` P99 in JSON & `fig1` vs. `95.6%--100.0%` and `0.05--7.09/7.12 ms` claimed across all $S \in [10^{-4}, 1.0]$ in `paper/prism_ann.tex` and `fig1`); (2) entry-portal saturation (`num_portals = min(50, len(valid_indices))`) in `hnsw_gls.py` plus sweep-coupled `tau_high(r_val)` in `run_prism_ann_benchmarks.py`; and (3) `run_prism_ann_benchmarks.py` exceeding the 1,000-line ceiling (`1,041` lines). Full subsystem evidence resides in [`01_thermo_nuclear_code_quality.md`](./neon_review_details/01_thermo_nuclear_code_quality.md), [`02_blast_radius_proof.md`](./neon_review_details/02_blast_radius_proof.md), and [`03_three_brake_academic_audit.md`](./neon_review_details/03_three_brake_academic_audit.md).

---

## 2. Thermo-Nuclear Code Quality & Sensor Verification

Every module under `src/modules/prism_ann/` respects the `< 1,000`-line boundary (`__init__.py`: 45, `index.py`: 119, `ubp_resolver.py`: 312, `hnsw_gls.py`: 579, `trimodal_planner.py`: 449) and passed both `checkReadPathPurity` and `checkBenchmarkEmpiricalPurity` with `0` violations. Moreover, `ubp_resolver.py:257-281` now computes $G_{\text{taint}}(u)$ via a genuine $O(m \cdot L^2)$ upward ancestor walk instead of materializing $\Theta(b^L)$ descendants.

Two structural/algorithmic issues require remediation in [`01_thermo_nuclear_code_quality.md`](./neon_review_details/01_thermo_nuclear_code_quality.md). First, [`run_prism_ann_benchmarks.py`](file:///Users/tejap/memory_paper/run_prism_ann_benchmarks.py) expanded to **`1,041` lines** (`> 1,000` presumptive blocker), driven by a 459-line `run_h2_h3_selectivity_and_gls_experiments` monolith and 122 lines of duplicated dictionary literals in `index_footprint_comparison`. Second, [`hnsw_gls.py:328`](file:///Users/tejap/memory_paper/src/modules/prism_ann/hnsw_gls.py#L326-L335) pulls `num_portals = min(50, len(valid_indices))` entry portals directly from `valid_indices`—which equals 100% of the authorized candidate set at $S = 0.005$ on $N = 10,000$ ($50$ candidates)—and [`run_prism_ann_benchmarks.py:682`](file:///Users/tejap/memory_paper/run_prism_ann_benchmarks.py#L682) tunes `tau_high` dynamically from `r_val` instead of using Algorithm 2's fixed $\tau_{\text{high}} = 0.25$.

---

## 3. Blast Radius Safety Proof (`verify_blast_radius_ubp.py`)

Running [`verify_blast_radius_ubp.py`](file:///Users/tejap/memory_paper/verify_blast_radius_ubp.py) directly against the upgraded $O(m \cdot L^2)$ `ubp_resolver.py` and `search_pgvector_iterative` confirmed exact set equivalence ($\bigcup_{t \in T_{\text{UBP}}^+(u)} B_t \setminus \bigcup_{z \in T_{\text{UBP}}^-(u)} B_z = \bigcup_{r \in D_{\text{auth}}(u)} B_r$) across all **376 adversarial scenarios** (9 edge cases, 150 randomized balanced trees, 100 multi-parent diamond DAGs, 100 post-revocation mutations, and 17 end-to-end `PrismANNIndex.search()` queries across Modes 1/2/3). Zero privilege leaks (`0 FP`) and zero dropped documents (`0 FN`) occurred, as proved in [`02_blast_radius_proof.md`](./neon_review_details/02_blast_radius_proof.md).

---

## 4. Visual PNG Inspection & 3-Brake Academic Discrepancies

Visual inspection of the 4 regenerated 300-DPI PNGs confirmed that `fig2`, `fig3`, and `fig4` render cleanly without curve/annotation overlap, while `fig1` exhibits minor lower-right legend proximity to `B5`/`B6` at $S = 50\%\text{--}100\%$ and literal `--` typography in Panel (b)'s teal box. More critically, reconciling [`results/prism_ann_benchmark_results.json`](file:///Users/tejap/memory_paper/results/prism_ann_benchmark_results.json) against [`paper/prism_ann.tex`](file:///Users/tejap/memory_paper/paper/prism_ann.tex) and `fig1` Panel (b) revealed that `Prism_ANN_Full` hits **`92.6%` Recall@10** and **`40.53 ms` P99** at $S = 0.50$ (and `8.43 ms` at $S = 0.05$). Because Table 2 omits $S \in \{0.05, 0.50\}$, `verify_prism_hallucinations.py` missed that the paper's global claims (`"95.6%--100.0% Recall@10"` and `"0.05--7.09/7.12 ms P99 across [10^-4, 1.0]"`) directly contradict both `key_highlights` and the visible `40.53 ms` teal spike in `fig1`. Additionally, [`run_prism_paperviz_audit.py:218-225`](file:///Users/tejap/memory_paper/run_prism_paperviz_audit.py#L218-L225) and [`run_prism_scholarpeer_review.py:206-209`](file:///Users/tejap/memory_paper/run_prism_scholarpeer_review.py#L206-L209) retain stale pre-`ENH-0010` log/table strings. Details reside in [`03_three_brake_academic_audit.md`](./neon_review_details/03_three_brake_academic_audit.md).

---

## 5. Two-Axis Merge / Submission Danger Score & Required Remediations

| Axis | Score / Classification | Rationale |
|---|---|---|
| **Axis 1: Engineering & Safety Integrity** | **8.4 / 10 (`Two-Way Door`)** | Core `src/modules/prism_ann/` modules are clean, sensor-verified, and mathematically proven leak-free (`376/376`, `0 FP/0 FN`); `run_prism_ann_benchmarks.py` needs `< 1,000`-line modularization and `num_portals` / `tau_high` decoupling. |
| **Axis 2: Submission / Reproducibility Danger** | **MEDIUM-HIGH (`6 / 10` until fixed)** | Automated Brake 1–3 scripts exit `0`, but submitting `paper/prism_ann.tex` while claiming `0.05--7.09 ms` / `95.6%--100.0%` across `[10^-4, 1.0]` when `fig1` visibly spikes to `40.53 ms` (`92.6%`) at $S = 0.50$ creates immediate reviewer rejection risk. |

### Recommended Remediation Sequence Before Final Submission
1. **Fix `hnsw_gls.py` & `run_prism_ann_benchmarks.py`**: Cap `num_portals <= 8` (removing `50`-portal saturation and `24`-node teleport fallback), fix `tau_high = 0.25` in H3, refactor `run_prism_ann_benchmarks.py` below `750` lines, and re-run live benchmarks (stabilizing `S = 0.50` P99).
2. **Synchronize `paper/prism_ann.tex`, `fig1`, and Audit Scripts**: Ensure Abstract, Table 1, Table 2 (or full 11-$S$ summary), `fig1` callout (`–` en-dash + exact `max_prism_p99_ms`), and `run_prism_paperviz_audit.py` / `run_prism_scholarpeer_review.py` match `min_prism_recall_across_all_S` and `max_prism_p99_ms_across_all_S` 100%, then recompile `paper/prism_ann.pdf` and `prism_ann_arxiv_package.tar.gz`.
3. **Software Factory Nudges (`@factory-overseer`)**: (a) Add full-sweep `min_*` / `max_*` range checks to `verify_hallucinations` (`ENH-0011`); (b) Enforce a `<= 1,000`-LOC ceiling on benchmark scripts and flag sweep-dependent hyperparameter coupling in `sensors.mjs` (`ENH-0012`).
