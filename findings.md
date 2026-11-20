# Research Findings & Narrative Synthesis (`findings.md`)

> **Governing Protocol (`ADR-0004` + `experiments/v2/PROTOCOL_v2.md`):**
> All empirical findings below come exclusively from the single frozen confirmatory run `v2-confirmatory-002` (commit `c819e65`, `FREEZE.md` hash match = `YES`, `62,410` raw per-query records in `results/v2/raw/*.jsonl`, deterministically summarized in `results/v2/summary.json`). Superseded Milestone 3 (v1) synthetic results are not used for any claim.

---

## 1. Real-Engine Confirmatory Setup (`v2-confirmatory-002`)
- **Corpus & Held-Out Queries**: Full BEIR Quora (`522,931` real passages) encoded with locally cached `sentence-transformers/all-MiniLM-L6-v2` (`384-d`, L2-normalized, Apple MPS), evaluated with `9,985` strictly disjoint held-out BEIR Quora test queries (`0` ID overlap, `0` exact text overlap; `500` queries/condition across `3` seeds).
- **Real External Engines**: Native SpiceDB `v1.57.1` (gRPC), PostgreSQL `17.12` + `pgvector 0.8.7` (`hnsw.iterative_scan = relaxed_order`, `EXPLAIN`-verified), `FAISS 1.16.0` (`IndexHNSWFlat` + `IDSelectorBitmap`, `M=16` primary & `M=8` shared-graph secondary), compiled upstream C++ `stanford-futuredata/ACORN` (`ACORN-1`, commit `c259f11`), `hnswlib 0.8.0` (filter callback), `pyroaring 1.2.0` (`CRoaring`), and exact filtered brute force. `HoneyBee` (no public code) is omitted as a measured baseline.
- **Frozen Algorithm**: All 5 files in `src/modules/prism_ann/` match `FREEZE.md` SHA-256 hashes 100%; base level-0 graph construction was delegated to `FAISS IndexHNSWFlat(384, 8)` via `bench/systems.py` (authorized in `PROTOCOL_v2.md`, logged in `results/v2/DEVIATIONS.md`).

---

## 2. Pre-Registered Confirmatory Findings (`P1a`–`P4b`, 8 Supported / 2 Falsified)

1. **H1v2 — Live SpiceDB Equivalence & Pre-Filter Latency (`P1a`, `P1b`, `P1c` — ALL SUPPORTED):**
   - **Exactness (`P1a`)**: Across `600` sampled principals (`200`/seed × `3` seeds, $m \in [0, 20]$ `DENY` exclusions), UBP matched live SpiceDB `LookupResources` with **`0` doc mismatches and `0` chunk mismatches**.
   - **Bound (`P1b`)**: `100.0%` (`600/600`) of principals satisfied $|T_{\text{UBP}}^+| \le k_0 + m(b-1)L$ (median `76`, max `296` tokens vs. median `723` / up to `4,096` leaf docs).
   - **Latency (`P1c`)**: For broad principals ($\ge 1{,}000$ authorized docs, $n=274$), local-mirror `UBP+bitmap` achieved **`0.310 ms` median (`0.578 ms` P95)** vs. **`70.150 ms` median (`148.142 ms` P95)** for live SpiceDB `LookupResources` + `CRoaring` leaf union (**`226.5×` speedup**). Even under the stricter live-RPC variant (`SpiceDB-ReadRelationships+UBP+bitmap`, **`2.089 ms` median**), UBP achieved a **`33.6×` speedup**.

2. **H2v2 — Low-Selectivity Recall under Random Assignment (`P2a` & `P2c` SUPPORTED; `P2b` FALSIFIED):**
   - **`P2a` (SUPPORTED)**: Disabling Mode 3, `prism-graph-only` outperformed primary `faiss-hnsw-M16` by **`+22.25 ± 2.54` pts** at $S=0.1\%$ (`28.21 ± 2.42%` vs. `5.95 ± 1.32%`) and **`+23.49 ± 2.19` pts** at $S=0.5\%$ (`45.93 ± 1.09%` vs. `22.44 ± 1.74%`), at *fewer* distance computations (`664.7` vs. `797.9`; `718.1` vs. `794.6`).
   - **`P2b` (FALSIFIED)**: Against compiled upstream C++ `acorn-1`, `prism-graph-only` won decisively on Recall@10 at every selectivity (`28.21%` vs. `0.85%` at $0.1\%$, `45.93%` vs. `20.59%` at $0.5\%$, `53.27%` vs. `26.51%` at $1\%$, `80.69%` vs. `31.29%` at $5\%$), but **failed** the $\le 1.0\times$ distance-computation requirement (`58.50×`, `3.24×`, `1.99×`, `1.04×` of `acorn-1`'s evals) because upstream `acorn-1` stalls early on sparse frontiers (`11.4` evals at $S=0.1\%$).
   - **`P2c` (SUPPORTED, completeness only)**: `prism-full` achieved **`100.00 ± 0.00%`** Recall@10 at $S \in \{0.1\%, 0.5\%, 1\%\}$ in `1.10–2.14 ms` median via Mode 3 exact Z-Ordered Roaring-SIMD scan.
   - **Where Baselines Win**: On real 523k MiniLM vectors, `hnswlib-M16` (`99.34%–99.91%` Recall@10) and `pgvector-hnsw-iter` (`75.49%–97.51%`) substantially outperform `prism-graph-only` (`28.21%–80.69%`) on pure graph recall, at the cost of severe low-selectivity latency (`131.52 ms` and `338.15 ms` median / `915.10 ms` P95 at $S=0.1\%$). Thus practical sub-1% recall in Prism-ANN is carried by Mode 3, while non-geometric $M_{\text{bridge}}=4$ ring-chord bridges alone are insufficient for $\ge 95\%$ graph-only recall.

3. **H3v2 — Cluster-Aligned Correlation at $S=2\%$ (`P3a` SUPPORTED; `P3b` FALSIFIED):**
   - **`P3a` (SUPPORTED)**: Across depleted queries ($r \le 0.5$, $n=735$, mean measured $r=0.01$), `prism-graph-only` reached `23.34 ± 4.52%` Recall@10 vs. `5.68 ± 1.85%` for `faiss-hnsw-M16` (**`+17.65 ± 3.09` pts**, at `534.0` vs. `795.1` evals). `hnswlib-M16` reached `96.87%` at `39.75 ms` (`84.6×` slower than its `0.47 ms` enriched latency).
   - **`P3b` (FALSIFIED on recall tolerance)**: Across enriched queries ($r \ge 2.0$, $n=751$, mean measured $r=41.17$), `prism-graph-only` cut distance evaluations to **`0.188×`** of `prism-static-2hop` (**`5.33×` fewer**: `588.8 ± 10.1` vs. `3,136.1 ± 52.5`), but Recall@10 dropped **`-2.00` pts** (`97.10 ± 0.42%` vs. `99.09 ± 0.57%`), missing the pre-registered `-1.0` pt tolerance.

4. **H4v2 — Real-Engine Zero-Write Revocation (`P4a` & `P4b` — BOTH SUPPORTED):**
   - Revoking one container edge covering `1,024` docs (`153,600` chunks) via live SpiceDB `DeleteRelationships` + mirror + next-query UBP + `CRoaring` executed in **`76.05 ms` median** (`62.12–170.87 ms`, $n=5$ trials) with **`0` vector writes**, compared to **`182,526.4 ms` (`182.5 s`) median** for a real transactional PostgreSQL 17 + `pgvector 0.8.7` `UPDATE` of `acl_allowed` across `153,600` rows (**`2,400.1×` faster**).

---

## 3. Research Trajectory & Next Architectural Step
- **Proven Strengths**: Subtractive-aware UBP (`H1v2`), zero-write SpiceDB revocation (`H4v2`), and Mode 3 Z-Ordered Roaring-SIMD exact scans at $S \le 1\%$ are empirically validated on real engines at full `522,931` scale.
- **Open Research Gap (from falsified `P2b`/`P3b` & `hnswlib`/`pgvector` comparison)**: Closing the graph-only recall gap at $S \in [0.5\%, 5\%]$ requires *geometrically navigated* intra-container bridges (rather than ID-ordered ring chords) and calibrated GLS thresholds before porting traversal to C++/FAISS.
- **Next Gate**: Proceed to GSD Phase 15 (fresh independent provenance-first audit and runtime Brake 2/3 reviews of `paper/prism_ann.pdf` and `paper/figures/v2_*.png`).
