# ADR-0005: Geometric Intra-Container Express Bridges (`H-HNSW v2`), Native C++ SIMD/CRoaring Kernel, and Multi-Corpus Persistent-SpiceDB Confirmatory Evaluation (Milestone 5 / Option A)

- **Status**: `accepted`
- **Date**: 2026-11-20
- **Scope**: `src/modules/prism_ann/hnsw_gls.py`, `src/modules/prism_ann/trimodal_planner.py`, `bench/prism_ckernel.cpp`, `results/v3/`
- **Builds Upon**: `ADR-0001` (UBP), `ADR-0002` (`H-HNSW` / `ACORN-GLS`), `ADR-0003` (Z-Ordered Tri-Modal Planner), `ADR-0004` (Raw-Record Provenance)

## Context
The Milestone 4 (`v2-confirmatory-002`) real-engine evaluation over 522,931 BEIR Quora passages validated SpiceDB UBP (`0/600` mismatches, `226.5×` local / `33.6×` live RPC speedup) and zero-write revocation (`2,400.1×` vs. PostgreSQL/`pgvector`), but exposed four technical gaps flagged by the independent Phase 15 peer review (`5.5 / 10`):
1. **Non-geometric ring-chord express bridges underperformed in graph-only mode** (`28.2%–53.3%` Recall@10 at $S \le 1\%$ vs. `hnswlib` `99.3%–99.9%`), and `prism-full` dropped to `24.55%` at `H3v2` ($S=2\%, r \le 0.5$) because Mode 3 cut off at $S = 1.5\%$.
2. **`P3b` was falsified** (`-2.00 pt` recall loss at $\tau_{\text{high}} = 0.25$ despite `5.33×` distance evaluation savings).
3. **Missing `InitEntryPortals` ablation** left the relative contribution of authorized entry portals vs. express bridges unmeasured.
4. **Python/NumPy Mode 3 (`1.10–2.14 ms`) trailed BLAS `exact-brute-force` (`0.25–1.94 ms`)**, and H2/H3 evaluated only one corpus (BEIR Quora) with in-memory SpiceDB.

## Decision
1. **Geometric Intra-Container & Intra-Magnet Express Bridges (`H-HNSW v2`, Experiment `E1`)**: Replace ID-ordered ring-chord express bridges with **semantic intra-container and intra-magnet k-NN / Vamana-style navigable bridges** ($M_{\text{bridge}} \in \{4, 8\}$ selected on a held-out dev split, pairing semantic nearest neighbors inside each container/magnet bucket with 1 diversity/medoid bridge), plus a **Local-Stall Mode-3 Escalation Guard** that falls back to native C++ Mode 3 when greedy search detects a depleted negative-correlation pocket ($\hat{S}_{\text{loc}} < \tau_{\text{stall}}$ with bounded candidate count $N_{\text{cand}} \le N_{\text{guard}}$).
2. **4-Way `InitEntryPortals` vs. Express-Bridge Ablation (Experiment `E2`)**: Measure `(a) FAISS M=16 (1 global entry)`, `(b) FAISS M=16 + Authorized Entry Portals`, `(c) H-HNSW v2 Geometric Bridges (no portals)`, and `(d) H-HNSW v2 + Portals + ACORN-GLS`.
3. **Native C++ / ARM NEON SIMD Kernel (`bench/prism_ckernel.cpp`, Experiment `E3`)**: Implement both Z-Ordered `CRoaring` interval (`[start, end)`) Mode-3 scanning (FP32 & SQ8 with ARM NEON intrinsics / `-O3 -mcpu=native`) and native C++ `H-HNSW` + `ACORN-GLS` traversal in a shared library loaded via `ctypes`—eliminating Python interpreter/FFI overhead and enabling apples-to-apples latency comparison against FAISS, upstream C++ `ACORN-1`/`ACORN-γ`, `hnswlib`, and `pgvector`.
4. **Two-Stage Exploratory-to-Confirmatory Discipline (Experiments `E4` & `E5`)**:
   - **Exploratory Stage (Phase 17):** Tune geometric bridge construction ($M_{\text{bridge}}$, $\tau_{\text{high}}$, local-stall guard) strictly on a **dev split** (`100k` subset + dev queries, logged as `exploratory` in `results/run_ledger.md`).
   - **Freeze & Pre-Register (Phase 18):** Freeze `src/modules/prism_ann/*.py` and `bench/prism_ckernel.cpp` in `FREEZE_v3.md` and commit `experiments/v3/PROTOCOL_v3.md`.
   - **Confirmatory Stage (Phase 19):** Run **one** 3-seed frozen confirmatory benchmark across **2 real public corpora** (`BEIR Quora 523k` + a second distinct-domain real corpus), **persistent PostgreSQL-backed SpiceDB** (`--datastore-engine postgres`, alongside memory mode), `PostgreSQL 17 + pgvector 0.8.7`, `FAISS 1.16.0`, upstream C++ `ACORN-1` & `ACORN-γ`, and `hnswlib 0.8.0` (plus `Qdrant` if runnable natively without Docker).

## Alternatives Considered (Design-It-Twice)
1. **Option B — Re-scope paper around SpiceDB UBP + Hybrid Planner only (7-day fast track)**: Safe, but leaves the filtered-HNSW data plane unresolved and limits target venue to workshops/applied tracks rather than VLDB/SIGMOD/SIGIR main track. Rejected per user's Option A choice.
2. **Keep Python traversal and report distance evaluations only**: Fails to validate Proposition 4's hardware SIMD crossover $\kappa$ empirically against BLAS `exact-brute-force`. Rejected in favor of a focused ~250-line C++ NEON kernel (`bench/prism_ckernel.cpp`).

## Mapped Paper Theorem
Upgrades §3.2 (`H-HNSW v2` Geometric Express Bridges & Local-Stall Guard), §4 (C++ NEON/`CRoaring` Kernel), and §5 (Multi-Corpus, Persistent-SpiceDB, 4-Way Portal Ablation & `ACORN-γ` Evaluation).

## Deep Module Seam
- `src/modules/prism_ann/index.py` (Algorithm seam; updated in Phase 17, then re-frozen in `FREEZE_v3.md` before Phase 19)
- `bench/prism_ckernel.cpp` -> `bench/_build/libprism_ckernel.dylib` (`prism_mode3_scan_ranges_f32`, `prism_mode3_scan_ranges_sq8`, `prism_search_hhnsw_gls`)

## Consequences
- **Positive**: Directly closes every substantive weakness from the Phase 15 peer review (`5.5/10`), elevating both the control plane and filtered-HNSW data plane to top-tier DB/IR venue standards.
- **Negative**: Longer build/benchmark cycle (~2 weeks including exploratory dev-split tuning, C++ kernel compilation, and 2-corpus confirmatory runs).
- **Reversibility**: `Two-Way Door` (Milestone 4 v2 raw records, `FREEZE.md`, and `results/v2/` remain archived and untouched).
