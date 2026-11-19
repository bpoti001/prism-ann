# Detail Report 01: Thermo-Nuclear Code Quality Review — Live `ENH-0010` Build

**Reviewer**: `@neon-reviewer` (`Neon High Thinking`)  
**Scope**: `src/modules/prism_ann/*`, `run_prism_ann_benchmarks.py`, `tests/test_prism_ann.py`, plus Software Factory sensors (`checkReadPathPurity`, `checkBenchmarkEmpiricalPurity`)  
**Standards Applied**: `thermo-nuclear-code-quality-review`, `CODING_STANDARDS.md`, `GLOSSARY.md`, `ADR-0001`..`0003`

---

## 1. Automated Software Factory Sensor Results (Executed via Node)

Invoking `/Users/tejap/software_factory/src/modules/sensors/index.mjs` directly on `/Users/tejap/memory_paper`:
- `checkReadPathPurity`: `[]` (**0 violations** — no `np.random.seed`/`random.seed` inside `src/modules/prism_ann/`, no `distance_computations += int(...)` synthetic padding).
- `checkBenchmarkEmpiricalPurity`: `[]` (**0 violations** — `run_prism_ann_benchmarks.py` contains zero hardcoded metric arrays or `curves = {...}` dictionaries; all metrics derive from live execution over `N = 10,000` `LoCoMo` chunks, `d = 128`).

---

## 2. File Size & Deep Module Seam Audit

| File | Current Lines | Limit (`< 1,000`) | Status | Notes |
|---|---|---|---|---|
| `src/modules/prism_ann/__init__.py` | 45 | PASS | Clean | Exports `index.py` public contract only (`search_pgvector_iterative` added) |
| `src/modules/prism_ann/index.py` | 119 | PASS | Clean | `PrismANNIndex` facade stays crisp |
| `src/modules/prism_ann/ubp_resolver.py` | 312 | PASS | **Upgraded** | $O(m \cdot L^2)$ upward taint computation (`lines 257-281`) |
| `src/modules/prism_ann/hnsw_gls.py` | 579 | PASS | **Flagged Caveat** | Added `actual_memory_bytes()`, `_select_upper_layer_entry`, `search_pgvector_iterative`, but see Finding 2 |
| `src/modules/prism_ann/trimodal_planner.py` | 449 | PASS | Clean | Unchanged clean Tri-Modal + `RoaringRunBitmap` algebra |
| `tests/test_prism_ann.py` | 327 | PASS | Clean | `4 / 4` tests pass in `0.145s` |
| `run_prism_ann_benchmarks.py` | **1,041** | **FAIL (`> 1,000`)** | **Presumptive Blocker** | Exceeds 1,000-line ceiling (`run_h2_h3` = 459 lines, 10x dict copy-paste in `H4`) |

---

## 3. Detailed Thermo-Nuclear Findings (Beyond Regex Sensors)

### Finding 1 (Presumptive Blocker — `thermo-nuclear-code-quality-review` Rule 1): `run_prism_ann_benchmarks.py` Exceeds 1,000 Lines (1,041 LOC)
- **Location**: `run_prism_ann_benchmarks.py:299-758` (`run_h2_h3_selectivity_and_gls_experiments`, 459 lines) and `851-972` (`index_footprint_comparison`, 122 lines).
- **Problem**: Replacing hardcoded curves with live execution bloated `run_prism_ann_benchmarks.py` from `539` lines to `1,041` lines (`49.8 KB`). The H2+H3 runner mixes index construction, mask generation, 10-system query dispatch, and GLS sweeps inside a single 459-line function, while `index_footprint_comparison` copy-pastes 10 nearly identical dictionary literals over 122 lines.
- **Remedy**: Extract a shared `_build_footprint_row(...)` factory for H4, split `run_h2_selectivity_sweep(...)` and `run_h3_gls_sweep(...)` into focused helpers (or a `benchmarks/` helper module), and reduce `run_prism_ann_benchmarks.py` below `750` lines.

### Finding 2 (Methodological Validity & Algorithmic Purity — HIGH): Entry-Portal Saturation (`num_portals = 50`) and Sweep-Coupled `tau_high(r_val)`
- **Locations**:
  - `src/modules/prism_ann/hnsw_gls.py:326-336` (`num_portals = min(50, len(valid_indices))`)
  - `src/modules/prism_ann/hnsw_gls.py:399-405` (`if len(results_map) < k * 3:` injecting `24` `valid_indices`)
  - `run_prism_ann_benchmarks.py:682` (`tau_h = max(0.08, min(0.30, 0.32 - 0.08 * r_val))`)
- **Problem**:
  1. When `use_express_bridges=True`, `search_hnsw_gls` pulls up to `50` entry portals directly from `valid_indices = np.flatnonzero(mask)`. On `N = 10,000` at $S = 0.005$ (`n_cand_target = 50`), `min(50, 50) = 50` injects **100% of all authorized documents** into `entry_seeds` before HNSW traversal even begins—turning Mode 2 into an exhaustive portal scan of the entire candidate set (`100.0%` recall vs. `33.2%` for `Ablation 2`). Even at $S = 0.01$ (`100` candidates), 50% of candidates are pre-seeded. Furthermore, `TELEPORT` line 399 injects up to `24` additional `valid_indices` whenever `len(results_map) < 30`.
  2. In Experiment H3 (`run_prism_ann_benchmarks.py:682`), `Prism-ANN` passes `tau_high = max(0.08, min(0.30, 0.32 - 0.08 * r_val))`, varying the internal threshold dynamically as a function of the benchmark sweep variable `r_val`, whereas Algorithm 2 (`paper/prism_ann.tex:251`) fixes `(\tau_low = 0.02, \tau_high = 0.25)`.
  3. Notice `hnsw_gls.py:373-379` also causes static `ACORN-1` (`use_gls_adaptive=False`) to evaluate `np.dot` on unauthorized hubs (`n1`) and re-expand already-evaluated authorized `n1` neighbors, whereas `ACORN-GLS` expands only `n1[~n1_auth_mask]`.
- **Remedy**: Bound `num_portals` to a fixed `O(1)` constant (`<= 4` or `<= 8`, matching `Theorem 3`'s bounded portal metadata), remove the `24`-node `valid_indices` teleport fallback in favor of genuine `express_bridges` graph hops, and use a fixed constant `tau_high = 0.25` in `H3`.

### Finding 3 (Positive Architectural Highlight): `ubp_resolver.py` $O(m \cdot L^2)$ Upward Taint Upgrade
- **Location**: `src/modules/prism_ann/ubp_resolver.py:257-281`.
- **Verification**: Replaced the previous $\Theta(b^L)$ `get_descendants(g0_pos)` materialization with a pure upward ancestor walk from `v_neg` (`z_anc = self.get_strict_ancestors(z)`), achieving true sub-linear query scaling (`0.01–0.34 ms` in live `H1` sweeps) while maintaining 100% equivalence (`0 FP / 0 FN`) across all `376` adversarial scenarios in `verify_blast_radius_ubp.py`.
- **Minor Code-Cleanliness Note**: In `hnsw_gls.py:367-370`, `1HOP` evaluates `index.express_bridges[curr]` (which is fine, though Algorithm 2 Line 6 lists only `\mathcal{N}_1(v)` for Case 1 `1HOP`). Also `Optional` import in `hnsw_gls.py:17` is unused again.

---

## 4. Verification Commands Run

```text
python3 -m unittest tests/test_prism_ann.py -v
-> Ran 4 tests in 0.145s -> OK
```
