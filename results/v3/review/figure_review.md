# Independent Visual Figure Review — Prism-ANN v3 (Brake 2)

- **Reviewer**: Independent Milestone 5 / Phase 20 Reviewer (zero prior builder context)
- **Inspection Method**: Direct visual inspection of all five 300-DPI PNG files via multimodal image reader, combined with code inspection of [`bench/plot_v3.py`](file:///Users/tejap/memory_paper/bench/plot_v3.py) and exact numerical verification against [`results/v3/summary.json`](file:///Users/tejap/memory_paper/results/v3/summary.json) (recomputed bit-for-bit from `results/v3/raw/*.jsonl` via `bench.recompute_v3 --check`).

## 1. Exact SHA-256 Artifact Inventory (All 10 v3 Figure Artifacts)

| Figure Artifact | Full 64-Character SHA-256 |
|---|---|
| `paper/figures/v3_fig1_h1_spicedb_mem_and_postgres.pdf` | `c2c65c73a7784a30c997f7bfc642ffa7fd24defb83498bcf816231c48c1202b8` |
| `paper/figures/v3_fig1_h1_spicedb_mem_and_postgres.png` | `9453124ed4e76a8978227234c54587e9682a99d432e4332a4743e72ce26e4c9f` |
| `paper/figures/v3_fig2_h2_multi_corpus_recall.pdf` | `3c3a8ca2dbf38a172db51d58454e8c8d948b948a0c7a10bac968d4ebf4b471b7` |
| `paper/figures/v3_fig2_h2_multi_corpus_recall.png` | `a63d474b28612d1f63252edcad2a679970810a991387c55924dfc800d15c7955` |
| `paper/figures/v3_fig3_h3_correlation_guard.pdf` | `3ee3c6f1b26246abf58e356c3a47d72fa66b120180109257c8573debc734d26b` |
| `paper/figures/v3_fig3_h3_correlation_guard.png` | `bd767a41664f207141a110dcd9e3811aa973b97f61d6dc8f197abe70d87b28a5` |
| `paper/figures/v3_fig4_h4_revocation_and_neon_latency.pdf` | `825e10f250214f7359639c6bf1ba75ff4ce1d2b561f63ab007994a626207fa3d` |
| `paper/figures/v3_fig4_h4_revocation_and_neon_latency.png` | `90d1d667423af29aa3e1a15ad10cf81352d50b958dca8ca6410270fa788ffcef` |
| `paper/figures/v3_fig5_h5_portal_ablation.pdf` | `43913d04decc33a60cd933c0a5df9bed5899914ea2fb5f0986ebcf6988652fd2` |
| `paper/figures/v3_fig5_h5_portal_ablation.png` | `13c9f7709e59f574a6c00eaa0cec1eedea5770bbbf1ea5cd4cef2a57afeac98a` |
| `paper/figures/v3_fig6_reviewer_audit.pdf` | `f9b252cb62a471911c48f8494415cc49a66a9a2c34f616685b64ab6efcc6bba9` |
| `paper/figures/v3_fig6_reviewer_audit.png` | `25293eed34b39a093cb11fec9a02c446f2d9fc8260686852f6d04d1a69bf6998` |

---

## 2. Per-Figure Visual & Numerical Critique

### Figure 1 (Paper Fig. 1): `paper/figures/v3_fig1_h1_spicedb_mem_and_postgres.png`
- **Visual Clarity & Layout**: Two side-by-side log-scale grouped bar charts comparing (a) pooled median latency and (b) pooled P95 latency across SpiceDB Memory and SpiceDB PostgreSQL 17 (`Broad n=271`). No clipped text, no overlapping bar labels, and the bottom 3-column legend sits cleanly below the x-axis labels without occluding any data.
- **Log-Scale Readability**: Both y-axes span cleanly (`10^-1` to `>10^3` ms in (a); `~0.2` to `>10^3` ms in (b)) with subtle dashed horizontal gridlines. Explicit bar-top numeric labels (`0.35`, `2.72`, `79.14`, `98.30`; `0.62`, `3.34`, `166.50`, `201.92`) eliminate ambiguity when reading bar heights on a log scale.
- **Colorblind Safety & Units**: Uses Okabe-Ito vermilion (`#D55E00`), orange-gold (`#E69F00`), and blue (`#0072B2`) with clear spatial ordering matching the legend left-to-right. Units (`ms, log`) and broad-principal sample size (`n=271` per backend) are stated clearly.
- **Numerical Agreement with `summary.json`**: Exact match to `H1_memory` and `H1_postgres` pooled median and P95 (`79.14375`, `98.298208`, `166.5021`, `201.9209`, `0.3504`, `0.3534`, `2.7152`, `3.4897`) and callout ratios (`225.9x / 29.1x`, `278.2x / 28.2x`, `0/1200` mismatches, `100%` within Theorem 1 bound).
- **Minor Observations (Non-blocking)**:
  1. `UBP tokens: med 76, max 285` in Panel (b) is populated from `h1_mem` (`bench/plot_v3.py:138`); `h1_pg` happens to have identical token stats (`76`, `285`), though labeling it explicitly as shared across both runs or verifying both would be cleaner.
  2. No dispersion/IQR error bars are drawn on the median/P95 bars (acceptable given P95 is shown in Panel (b) and sample size $n=271$ is marked).

### Figure 2 (Paper Fig. 2): `paper/figures/v3_fig2_h2_multi_corpus_recall.png`
- **Visual Clarity & Layout**: Two side-by-side semi-log recall curves for Corpus 1 (BEIR Quora, `N=522,931`) and Corpus 2 (BEIR NQ Wiki, `N=250,000`) across $S \in \{0.1\%, 0.5\%, 1\%, 5\%\}$. Titles, axis labels, and 4×2 bottom legend are legible with zero truncation or legend occlusion.
- **Overlaps & Occlusion**: At $S \le 1\%$, `Prism v3 full + NEON SQ8` (`100.00%`) and `hnswlib M=16` (`99.47%–99.93%`) share the 100% ceiling; the `0.96` / `1.04` horizontal x-jitter (`bench/plot_v3.py:164`) plus hollow orange square vs. solid indigo X successfully separates both markers. At $S=5\%$ in Panel (a), `v3-geom-M8` (`95.25%`) and `v3-full-guard-sq8` (`95.25%`) sit at the same y-value, and in Panel (b) `pgvector` (`93.89%`), `v3-full-guard-sq8` (`95.13%`), and `v3-geom-M8` (`93.35%`) cluster tightly between `93%` and `95%`, though remaining distinguishable.
- **Log-Scale Readability & Error Bars**: X-axis uses log scale with clear percentage tick labels (`0.1%`, `0.5%`, `1%`, `5%`) and minor decade ticks. 3-seed 95% $t$-CI error bars are drawn cleanly with caps; `y_lim(-2, 108)` prevents clipping near 0% and 100%.
- **Colorblind Safety**: Mostly distinct Okabe-Ito/Tol hues plus distinct markers/linestyles; minor note that `ACORN-1` (`#009E73`) and `ACORN-gamma` (`#44AA99`) are similar green-teal tones, though distinguished by `P` vs. `h` markers and solid vs. dash-dot linestyles.
- **Numerical Agreement with `summary.json`**: 100% exact across all 8 systems × 4 selectivities × 2 corpora (`v3-geom-M8` `66.60..95.25` Quora / `75.57..93.35` NQ; `acorn-gamma` `0.25..87.69` / `0.43..82.19`, etc.).
- **Fairness/Context Note**: `exact-brute-force` and `cpp-mode3-sq8` are omitted from the plot (acceptable to avoid clutter at 100%, and both appear in `summary.json` / Table III for `exact-brute-force`, though `cpp-mode3-sq8` is omitted from Table III as well). Also recall error bars' sample basis (`3 seeds x 500 queries, ±95% t-CI`) is in the paper caption rather than the y-axis label.

### Figure 3 (Paper Fig. 4): `paper/figures/v3_fig3_h3_correlation_guard.png`
- **Visual Clarity & Layout**: Two grouped bar panels: (a) H3v3 Depleted (`r<=0.5`) Recall@10 and (b) H3v3 Enriched (`r>=2.0`) Distance Evaluations/Query, each spanning Quora (`523k`) and BEIR NQ (`250k`). Shared 6-item bottom legend has zero overlap with bars or x-axis labels.
- **Text & Axis Check**:
  - In Panel (a), rotated 90-degree numeric labels (`97.2`, `54.6`, `5.6`, `21.9`, `96.9` and `96.4`, `58.5`, `5.3`, `32.2`, `95.4`) sit cleanly above the 95% CI error bars without colliding with adjacent bars or the top callout box.
  - **Minor visual issue**: In Panel (a), `ax1.set_ylim(0, 148)` with `yticks([0, 20, 40, 60, 80, 100])` causes the left y-axis spine to extend almost 50% above the `100%` tick with no ticks above 100 (done to create headroom for the callout box, which looks slightly awkward on a `[0, 100]%` scale).
  - In Panel (b), `750 / 2864 / 791 / 1112` and `777 / 2416 / 810 / 1107` sit cleanly above CI caps; the pink callout box sits cleanly in upper whitespace.
- **Units, Sample Sizes & Agreement with `summary.json`**: Numbers and CIs match `H3_quora` and `H3_nq` (`r_le_0.5` and `r_ge_2`) in `summary.json` exactly. Sample sizes (`n=728`, `n=715`, `n=750`, `n=753`) are omitted from the PNG axis labels (present in Table IV and caption).
- **Manuscript Ordering Note (Non-visual / Placement)**: Placed as **Fig. 4** in `paper/prism_ann.pdf` (after `v3_fig5_h5_portal_ablation` which became **Fig. 3**), inverting the file name `v3_fig3` vs. paper figure number `Fig. 4`.

### Figure 4 (Paper Fig. 5): `paper/figures/v3_fig4_h4_revocation_and_neon_latency.png`
- **Visual Clarity & Layout**: Two log-y panels: (a) H4v3 Persistent Revocation (`n=5`, median + min–max bars) comparing PostgreSQL 17 SpiceDB (`67.28 ms, 0 writes`) vs. PostgreSQL 17 + pgvector `UPDATE` (`179.4 s, 2,666.2x slower`), and (b) H2v3 Native C++ / NEON pooled median latency across $S \in [0.1\%, 5\%]$ on BEIR Quora (`N=522,931`).
- **Overlaps & Readability**:
  - Panel (a) is very clean; min–max error bars (`51.20–83.46 ms` and `177.82–187.88 s`) and bold callouts have zero overlap.
  - Panel (b) log-log latency plot has minor marker overlaps where curves intersect or cluster: at $S=0.1\%$, `FAISS HNSW M=16` (`0.95 ms`), `ACORN-gamma` (`1.08 ms`), and `ACORN-1` (`1.15 ms`) crowd around `1 ms`; at $S=0.5\%$, `hnswlib` (`37.90 ms`) and `pgvector` (`40.06 ms`) intersect; at $S=5\%$, `v3-full-guard-sq8` (`0.61 ms`) and `v3-geom-M8` (`0.64 ms`) overlap at `~0.6 ms`. All remain readable because their trajectories separate across adjacent points.
- **Fairness / Visual Context**: Panel (b) plots only BEIR Quora (BEIR NQ latency is in Table III only), and per our code audit, the `~0.82 ms` fixed Python/NumPy mask permutation floor on `FAISS` and `ACORN` makes their lines appear nearly flat around `1.0–2.1 ms` rather than reflecting pure C++ traversal time.
- **Manuscript Ordering Note**: Placed as **Fig. 5** in `paper/prism_ann.pdf`, and Panel (b) (`H2v3` latency) is not cross-referenced inside Section V-C (`H2v3`).

### Figure 5 (Paper Fig. 3): `paper/figures/v3_fig5_h5_portal_ablation.png`
- **Visual Clarity & Layout**: Single-panel grouped bar chart of the 4-way `InitEntryPortals` ablation on BEIR Quora (`N=522,931`) across $S \in \{0.1\%, 0.5\%, 1.0\%, 5.0\%\}$. Bar-top labels (`5.8, 6.4, 67.2, 66.6`, etc.), 95% CI caps, green callout box (`101.0% | 102.3% | 101.0%`), and 2×2 bottom legend are completely free of overlap or truncation.
- **Minor Inconsistencies (Non-blocking)**:
  1. **Notation mismatch within the same figure**: X-axis tick labels express selectivity in percent (`S = 0.1%`, `S = 0.5%`, `S = 1.0%`, `S = 5.0%`), whereas the green callout box writes decimal fractions (`S=0.001`, `S=0.005`, `S=0.01`).
  2. **Rounding discrepancy vs. Table III**: `S = 1.0%` `FAISS HNSW M=16` bar label shows `36.8` (`36.8467%` formatted with `:.1f`), whereas Table III displays `36.85%`. Both are exact to their respective decimal places, though `36.8` vs. `36.85` can momentarily puzzle readers.
  3. **Colorblind pairing**: Dark forest green (`#117733`) vs. vermilion (`#D55E00`) are adjacent on the right two bars; luminance contrast and fixed left-to-right legend ordering keep them distinguishable, though texture/hatching would improve deuteranopia separation.

### Figure 6 (Paper Fig. 6, `v3.1` Supplementary Audit): `paper/figures/v3_fig6_reviewer_audit.png`
- **Visual Clarity & Layout**: Three side-by-side panels generated via `bench/plot_v3_1.py` from `results/v3/reviewer_audit_v3_1.json` (`22,533` clean raw records on commit `e39260a`, `git_dirty=False`): **(a)** Ultra-low $S=0.01\%$ Recall@10 on Quora (`523k`) and NQ (`250k`); **(b)** Cold-LLC ($64\text{ MB}$ volatile flush/query) 6-way Mode-3 component isolation across $S \in [0.01\%, 1.0\%]$; and **(c)** Persistent PG17 SpiceDB single-edge $O(1)$ subtree revocation scaling (`128 -> 490,419` chunks, `0` vector writes) with the concurrent `11,244`-query `ZedToken` race callout (`0/6,039 queries leaked`).
- **Overlaps & Readability (Verified after Remediation)**:
  - Panel (a) separates `100.0` (bold) and `100.0` (regular) over `Prism Full` cleanly with a crisp horizontal offset and `fontsize=5.8`.
  - Panel (b) extends the log y-axis headroom (`ylim(0.02, 14.0)`) and uses a compact `5.5 pt` legend box so all six curves (`Scattered FP32 Scalar` through `Z-Order SQ8 NEON`) sit cleanly below the legend with zero line clipping.
  - Panel (c) right-aligns the green `R4a/R4b` callout box above the flat `65k..490k` tail (`0.74–0.80 ms`), completely clear of the `128`-chunk `5.11 ms` upper whisker on the left.

---

## 3. Figure Review Verdict

- **Visual Blockers**: **None** strictly from rendering/overlap/truncation standpoints — all 5 PNGs are crisp at 300 DPI, free of occluded legends or overlapping text, and numerically consistent with `results/v3/summary.json`.
- **Non-Blocking Visual Improvements Recommended**:
  1. Reorder figures in `paper/prism_ann.tex` so file numbering and narrative order match (`Fig. 1` H1 -> `Fig. 2` H2 recall -> `Fig. 3` H3 correlation -> `Fig. 4` H4 revocation & latency -> `Fig. 5` H5 portal ablation), and cite `Fig. 5(b)` in Section V-C.
  2. In `v3_fig5`, unify selectivity formatting between the callout box (`0.1% | 0.5% | 1.0%`) and x-axis ticks (`S = 0.1% ...`).
  3. In `v3_fig3(a)`, avoid extending the y-axis spine visibly past `100%` (`148`) without upper framing, or place the callout box above the axes as a subtitle/header banner.
  4. In `v3_fig4(b)` / `v3_fig2`, consider annotating or noting in caption that `H2v3` latencies for `FAISS`/`ACORN` include Python `O(N)` bitset marshaling (`~0.82 ms`).
