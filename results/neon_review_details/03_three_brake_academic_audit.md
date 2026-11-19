# Detail Report 03: 3-Brake Academic & Systems Verification Audit — Live `ENH-0010` Build

**Reviewer**: `@neon-reviewer` (`adr-to-arxiv-factory`, `systems-paper-writing`, `ml-paper-writing`)  
**Automated Gate Command**: `python3 research_factory.py audit-paper` -> **EXIT CODE 0** (with manual adversarial findings documented below!)

---

## 1. Automated 3-Brake & Governance Results

- **GSD `ADR-0006` & Governance Gate (`verify-governance`)**: **PASS** — `.planning/ROADMAP.md` traces `12/12` phases (`100%`) to `ADR-0000..0003`; `.planning/STATE.md`, `PROJECT.md`, `REQUIREMENTS.md`, `config.json`, `CONTEXT.md`, `GLOSSARY.md`, and `experiments/H1..H4/protocol.md` are synchronized.
- **Node Citation Sensor (`checkLatexCitationBijection`)**: **PASS** (`passed: true`, `18` citedKeys == `18` definedKeys, `missingInBib: []`, `uncitedInBib: []`).
- **Brake 1 (`verify_prism_hallucinations.py`)**: Passed **258 / 258** row-scoped checks across Tables 2–5 and selected headline claims.
- **Brake 2 (`run_prism_paperviz_audit.py`)**: Reported **97.72 / 100** (`results/prism_paperviz_report.md`).
- **Brake 3 (`run_prism_scholarpeer_review.py`)**: Reported **STRONG ACCEPT (9.0 / 10)** (`results/prism_scholarpeer_review.md`).
- **LaTeX PDF**: `paper/prism_ann.pdf` and `prism_ann_paper.pdf` verified at **11 pages** (`510 KB`); `prism_ann_arxiv_package.tar.gz` at `405 KB`.

---

## 2. Adversarial Discrepancies Uncovered Beyond Automated Scripts (MUST FIX FOR CAMERA-READY)

### Critical Blocker A (Brake-1 Blindspot / Omitted-Selectivity Discrepancy in `paper/prism_ann.tex` & `fig1`):
Although `verify_prism_hallucinations.py` passed 258/258 checks, it only inspected the **6 columns displayed in Table 2** (`S in {10^-4, 10^-3, 5e-3, 10^-2, 10^-1, 1.0}`) and omitted `S in {5e-4, 0.02, 0.05, 0.25, 0.50}` from verification. Inspecting `results/prism_ann_benchmark_results.json` directly reveals:
- At $S = 0.50$ (plotted in `fig1`), `Prism_ANN_Full` recorded **`92.6%` Recall@10** and **`40.53 ms` P99 latency** (`key_highlights["min_prism_recall_across_all_S"] = 92.6`, `key_highlights["max_prism_p99_ms_across_all_S"] = 40.53`).
- At $S = 0.05$ (plotted in `fig1`), `Prism_ANN_Full` recorded **`97.2%` Recall@10** and **`8.43 ms` P99 latency**.
- **Contradiction**: `paper/prism_ann.tex` (Abstract line 47, Table 1 line 75, Fig. 1 caption line 332, Section 5.2 line 416, Conclusion line 506) and `generate_prism_ann_plots.py:158` (`fig1` Panel (b) callout box) claim **`95.6%--100.0%` Recall@10** and **`0.05--7.09 ms` (or `7.12 ms`) P99 latency** *"across all five orders of magnitude ($S \in [10^{-4}, 1.0]$)"*. Yet `fig1` Panel (b) visibly shows the teal `Prism-ANN` curve spiking up to **`40.53 ms`** at $S=50\%$ (`x = 50`)!
- **Required Fix**: Either re-run with clean multi-seed timing stability if `40.53 ms` was an OS/GC outlier and stabilize `S=0.50` recall, OR report the true full-sweep range (`92.6%--100.0%` Recall@10, `0.05--40.53 ms` P99 across all 11 $S$ points; `95.6%--100.0%` / `0.05--7.09 ms` on Table 2's 6 regimes) and harden `verify_prism_hallucinations.py` to assert `key_highlights["min_prism_recall_across_all_S"]` and `max_prism_p99_ms_across_all_S`.

### Critical Blocker B (Visual Inspection of 300-DPI PNGs & Stale Audit Report Text):
Direct `view_file` inspection of `paper/figures/fig1..fig4.png` confirmed:
- **`fig2`**, **`fig3`**, and **`fig4`** have crisp typography and zero label-to-curve or legend-to-curve overlaps (though `fig2` Panel (a) legend comes within a few pixels of the `m=15` Theorem 1 triangle).
- **`fig1` Panel (a)**: The `lower right` legend slightly overlaps `B5` (`S=50%-100%`) and touches `B6`'s trajectory around `S=25%-50%`.
- **`fig1` Panel (b)**: Renders literal `--` in `Prism-ANN: 0.05--7.12 ms P99` instead of an en-dash `–`, and the `7.12 ms` label contradicts the plotted `40.53 ms` peak at $S=50\%$ on the same subplot.
- **Stale Text in Audit Generators**:
  - `run_prism_paperviz_audit.py:218-225` still writes the pre-`ENH-0010` refinement log (`1.71 ms vs. 1.42 ms`, `(0.14%, 17.5%)`) into `results/prism_paperviz_report.md`.
  - `run_prism_scholarpeer_review.py:206-209` still writes pre-`ENH-0010` numbers (`<=43 tokens`, `+7.4% RAM`, `5.8x RAM`, `6.4x RAM`) into `results/prism_scholarpeer_review.md`.

### Critical Blocker C (Methodological Caveats from `hnsw_gls.py` / `run_prism_ann_benchmarks.py`):
- See Detail Report 01 Finding 2 (`num_portals = min(50, len(valid_indices))` covering 100% of candidates at $S=0.005$ on $N=10,000$; `TELEPORT` 24-node fallback; and `tau_high` coupled to `r_val` in H3).
