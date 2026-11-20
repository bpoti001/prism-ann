# Brake 2 — Independent Figure Review (Prism-ANN v2)

- **Reviewer**: Independent Auditor (Milestone 4, Phase 15-01)
- **Reviewed at**: 2026-11-20
- **Source Generator**: `bench/plot_v2.py` reading `results/v2/summary.json` (bit-for-bit matched to `results/v2/raw/*.jsonl` via `bench.recompute --check`)

## Artifact SHA-256 Registry

| Artifact Path | SHA-256 |
|---|---|
| `paper/figures/v2_fig1_h1_spicedb_ubp.pdf` | `425e7ec54e0cfaec797876a15b4a40f276b009fd1a07b933595391936ef960c9` |
| `paper/figures/v2_fig1_h1_spicedb_ubp.png` | `04acdbd05b9c57fcabbc0a3a7aeda6bb5b85c4113b3ec82d9d4124773cbea27d` |
| `paper/figures/v2_fig2_h2_selectivity_sweep.pdf` | `70026d80e02af360808d7f9c999dcae34ffd772e3b33b85b89354643a57429f2` |
| `paper/figures/v2_fig2_h2_selectivity_sweep.png` | `56cbd5ebfca7678a35d1e30782011d3ddfdb3d8d1f865d9d02b5732091f3f883` |
| `paper/figures/v2_fig3_h3_gls_correlation.pdf` | `f6a958d93c3106b92f2bd17b8658ffd4f0f3c44777781036680b7ef175f43cbb` |
| `paper/figures/v2_fig3_h3_gls_correlation.png` | `8bc098f2744da9b1aaff24acc7976845ff7183981cfdbcb768d0e4ef3e8938d0` |
| `paper/figures/v2_fig4_h4_revocation_and_latency.pdf` | `226ed3a054f8560dbc6655a0510b86784542cb03618d3123dc5c10b8e308d307` |
| `paper/figures/v2_fig4_h4_revocation_and_latency.png` | `ceaa23722ed8f993b5920db282115adadbc21cf595c011bc60bc54fc56379dde` |

> *Post-review hygiene addendum (2026-11-20):* `bench/plot_v2.py:191` now interpolates the ACORN-1 annotation dynamically from `summary.json`; all 4 rendered PNGs are bit-for-bit identical to the visually inspected images above, and regenerated PDF hashes are updated in the table.

---

## Per-Figure Visual & Faithfulness Critique

### Figure 1 (`v2_fig1_h1_spicedb_ubp.{png,pdf}`) — Experiment H1v2: SpiceDB Oracle Equivalence & Pre-Filter Latency
- **Data Faithfulness**: High. Plotted bar heights in Panel (a) (`0.22`, `1.86`, `27.90` ms for all $n=600$; `0.31`, `2.09`, `70.13` ms for broad $n=274$) match the 3-seed means of per-seed medians (`0.224`, `1.863`, `27.899` and `0.312`, `2.089`, `70.130` ms) in `results/v2/summary.json`, with 95% $t$-CI error bars. Panel (b) P95 bars (`0.52`, `2.54`, `146.52` ms; `0.58`, `2.64`, `148.14` ms) match `latency_ms_p95_pooled` exactly, and the invariant callout (`0 docs / 0 chunks`, `100% (600/600)`, `med 76, max 296`) matches `summary.json` and raw `v2-confirmatory-002__H1.jsonl`.
- **Minor Consistency Note**: In Panel (a), the orange callout box reports `226.5x (local mirror)` and `33.6x (strict live RPC)` from `summary["verdicts"]["P1c"]`, which are ratios of *pooled* medians (`70.150 / 0.3097 = 226.5x`), whereas the bar labels (`70.13` and `0.31`) come from `by_seed.latency_ms_median.mean` (`70.130 / 0.312 = 224.8x`). The caption explicitly distinguishes "(a) 3-seed mean of median latency ... (b) Pooled P95 tail latency", though readers dividing the printed bar numbers (`70.13 / 0.31 = 226.2x`) will notice a tiny `0.3x` rounding discrepancy.
- **Visual Design & Readability**: Clean two-panel layout, colorblind-safe Okabe-Ito palette, crisp log-scale ticks, zero label collisions, and uncluttered callout boxes.

### Figure 2 (`v2_fig2_h2_selectivity_sweep.{png,pdf}`) — Experiment H2v2: Random-Overlay Selectivity Sweep
- **Data Faithfulness**: Verified against `summary.json` and `v2-confirmatory-002__H2.jsonl` across all 8 systems (`exact-brute-force`, `faiss-hnsw-M16`, `faiss-hnsw-M8`, `acorn-1`, `hnswlib-M16`, `pgvector-hnsw-iter`, `prism-graph-only`, `prism-full`). Error bars accurately reflect 95% $t$-CIs across 3 seeds. Both `P2a` support and `P2b` falsification are clearly depicted, including `prism-graph-only` trailing `hnswlib` and `pgvector`.
- **Visual Overlap / Occlusion Issue (Non-Blocking)**: In Panel (a) at $S \in \{0.1\%, 0.5\%, 1\%\}$, `Prism full w/ Mode 3` (`100.00%`, orange dashed squares), `hnswlib M=16` (`99.34%–99.91%`, dark indigo dash-dot crosses), and `Exact brute force` (`100.00%`, grey dotted dots) overlap directly on top of one another at `y = 100%`. Consequently, `Exact brute force` is visually hidden across $S \le 1\%$ and `hnswlib` is partially masked behind `Prism full`'s square markers. Similarly, in Panel (b) for $S \le 1\%$, `Prism full` completely overlaps `Exact brute force` (`510.7`, `2553.3`, `5234.0`), though the sharp drop at $S=5\%$ (`1301.0`) clearly illustrates the Mode 3 crossover.
- **Code Hygiene Note**: In `bench/plot_v2.py:191`, the annotation text `"ACORN-1 early stall\n(11.4 evals, 0.85% R@10;\nP2b falsified on dist ratio)"` embeds literal values (`11.4`, `0.85%`) instead of formatting them dynamically from `summary["hypotheses"]["H2"]` like the rest of the script. The displayed numbers match `summary.json` (`11.362` evals, `0.847%` recall), so there is no numerical error, only an inconsistency in dynamic interpolation.
- **Readability**: Legend spans 4 columns cleanly below the axes, log axes are well labeled, and language tags appear directly in legend entries.

### Figure 3 (`v2_fig3_h3_gls_correlation.{png,pdf}`) — Experiment H3v2: Cluster-Aligned Correlation Study
- **Data Faithfulness**: Verified against `summary.json` (`r_le_0.5` $n=735$, mean $r=0.01$; `r_ge_2` $n=751$, mean $r=41.2$) and `v2-confirmatory-002__H3.jsonl`. The `P3b` callout honestly reports both the `5.33x` distance reduction (`0.188x` evals) and the `-2.00 pts` recall drop (`FALSIFIED vs -1 pt`).
- **Scope / Completeness Note**: `bench/plot_v2.py:217,244` plots 5 systems in Panel (a) and 4 in Panel (b) (omitting `hnswlib-M16` in (b) because `dist = N/A`, and omitting `prism-full`, `faiss-hnsw-M8`, and `exact-brute-force` present in Table IV). While keeping the bars focused on `P3a` and `P3b`, omitting `prism-full` (`24.55%` at $r \le 0.5$) slightly hides the fact that Mode 3 does not rescue `prism-full` at $S = 2\%$ when $r \le 0.5$.
- **Visual Design & Readability**: Very clean. Setting `ylim(0, 145)` with ticks capped at `[0, 20, 40, 60, 80, 100]` gives comfortable headroom so the rotated numeric bar labels (`96.9`, `99.1`, etc.) never collide with the `P3a` callout box. Zero overlapping labels.

### Figure 4 (`v2_fig4_h4_revocation_and_latency.{png,pdf}`) — Experiment H4v2: Revocation & Secondary H2v2 Latency
- **Data Faithfulness**: Panel (a) plots `76.049 ms` (`min 62.12`, `max 170.87`) vs. `182,526.4 ms` (`min 180,486.3`, `max 219,252.6`) over $n=5$ trials, matching `v2-confirmatory-002__H4.jsonl` exactly. Panel (b) matches `latency_ms_median.mean` in `summary.json` for the 7 plotted systems (`faiss-hnsw-M8` is omitted to reduce clutter around `faiss-hnsw-M16`'s flat `~0.93 ms` line).
- **Precision & Axis Notes**:
  1. Panel (a) bar annotations (`bench/plot_v2.py:302-304`) round to `76.0 ms` and `2400x slower`, whereas the caption immediately below (`paper/prism_ann.tex:413`) and Table II write `76.05 ms` and `2,400.1x`. Formatting the bar label to two decimals (`76.05 ms`) would align the bar text with the caption.
  2. In Panel (b), `ylim(0.15, 900)` places `exact-brute-force` at $S=0.1\%$ (`0.25 ms`) below the lowest printed major tick (`10^0 = 1 ms`), leaving only unlabeled minor log ticks in `[0.15, 1.0)`. Adding or ensuring a visible `10^-1` or `0.2` reference tick would improve quick visual reading of the sub-millisecond region.
- **Visual Design & Readability**: Implementation languages (`Py`, `Py/NP`, `C++`, `C++/Py-cb`, `C`, `BLAS`) are clearly noted on every legend entry so Python vs. C/C++ latencies are never conflated.

---

## Overall Brake 2 Judgment

- **Assessment**: **Pass with minor non-blocking visual refinements.**
- **Strengths**: All four figures are strictly derived from provenance-verified `results/v2/summary.json`, cleanly display 95% confidence intervals (and min–max bars for $n=5$ H4 trials), avoid cluttered overlays, clearly distinguish implementation languages on secondary latency plots, and highlight falsified hypotheses (`P2b`, `P3b`) and competing baseline wins (`hnswlib`, `pgvector`) rather than hiding them.
- **Recommended Polish (Non-Blocking)**:
  1. In `v2_fig2` Panel (a), offset markers slightly, reduce `Prism full` marker size/alpha, or add a small inset around `98%–100.5%` so `hnswlib` and `Exact brute force` remain distinguishable under `Prism full` at $S \le 1\%$.
  2. Dynamically format the `ACORN-1` callout in `bench/plot_v2.py:191` from `summary.json`, and match `76.05 ms` / `2,400.1x` precision in `v2_fig4` Panel (a).
  3. Consider adding `prism-full` to `v2_fig3` Panel (a) (or noting in its caption that `prism-full` behaves nearly identically to `prism-graph-only` at $S=2\%$) and labeling a `0.2` / `10^-1` tick in `v2_fig4` Panel (b).
