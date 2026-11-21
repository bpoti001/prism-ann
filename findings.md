# Research Findings & Narrative Synthesis (`findings.md`)

> **Governing Protocol (`ADR-0004` + `ADR-0005` + `experiments/v3/PROTOCOL_v3.md`):**
> All empirical findings below come exclusively from the single frozen confirmatory run `v3-confirmatory-001` (commit `41868bb`, `FREEZE_v3.md` 7/7 SHA-256 match = `YES`, `169,810` raw per-query records in `results/v3/raw/*.jsonl`, deterministically summarized in `results/v3/summary.json`, verified bit-for-bit via `bench.recompute_v3 --check`). Milestone 4 (`v2-confirmatory-002`) remains archived in `results/v2/`.

---

## 1. Multi-Corpus Real-Engine Confirmatory Setup (`v3-confirmatory-001`)
- **Corpus 1 (Primary)**: Full BEIR Quora (`522,931` real passages, `all-MiniLM-L6-v2` 384-d L2-normalized), strictly reserved held-out test query indices **`[500..9,984]`** (`9,485` queries; `0` corpus overlap, `0` overlap with Phase 17 dev queries `[0..499]`).
- **Corpus 2 (Cross-Domain Wikipedia)**: Official BEIR Natural Questions (`BeIR/nq`, first `250,000` Wikipedia passages, `all-MiniLM-L6-v2` 384-d), `3,452` strictly disjoint test queries (`0` ID/text overlap).
- **Live Native Engines**: Native SpiceDB `v1.57.1` on **both** `--datastore-engine memory` AND persistent `--datastore-engine postgres` (PostgreSQL `17.12`), PostgreSQL `17.12` + `pgvector 0.8.7` (`relaxed_order`, `EXPLAIN`-verified on BOTH corpora), `FAISS 1.16.0`, compiled upstream C++ `stanford-futuredata/ACORN` (`acorn-1` $\gamma=1$ AND `acorn-gamma` $\gamma=4, M_\beta=64$), `hnswlib 0.8.0` (`C++/Py-cb`), `pyroaring 1.2.0`, Accelerate BLAS `exact-brute-force`, and frozen native C++17 / ARM NEON Prism-ANN v3 (`bench/prism_ckernel.cpp`). `Qdrant` (no native macOS bottle without Docker) and `HoneyBee` (no public code) are excluded (logged in `results/v3/DEVIATIONS.md`).

---

## 2. Pre-Registered Confirmatory Findings (`P1a`–`P5`, **11/11 SUPPORTED**)

1. **H1v3 — Live Memory & Persistent PostgreSQL 17 SpiceDB (`P1a`, `P1b`, `P1c` — ALL SUPPORTED):**
   - `0/1,200` mismatches (`0/600` memory + `0/600` persistent PostgreSQL 17 SpiceDB); `100.0%` within Theorem 1 bound (median `76`, max `285` tokens).
   - Broad principals ($\ge 1,000$ docs, $n=271$): **Memory SpiceDB** `0.350 ms` vs. `79.14 ms` (**`225.9×`**, strict live `ReadRelationships` RPC `2.72 ms` = **`29.1×`**); **Persistent PostgreSQL 17 SpiceDB** `0.353 ms` vs. `98.30 ms` (`201.92 ms` P95) (**`278.2×`**, strict live RPC `3.49 ms` = **`28.2×`**).

2. **H2v3 — Multi-Corpus Random-Overlay Selectivity Sweep (`P2a`, `P2b`, `P2c` — ALL SUPPORTED):**
   - **Quora (`522,931`)**: `v3-geom-M8` (graph-only, C++, `+1.91%` RAM) reaches `66.60%` / `78.29%` / `85.99%` / `95.25%` (`0.32–0.64 ms`), beating `faiss-hnsw-M16` (`5.75%–77.51%`) by **`+49.15` to `+60.85` pts** at $S \le 1\%$, beating `v2-ring-chord-M4` (`46.06%–67.87%`) by **`+18.12` to `+21.88` pts**, and beating both `acorn-1` (`0.95%–31.66%`) and `acorn-gamma` ($\gamma=4$: `0.25%–87.69%`) at every $S$ using **`0.143×` (`7×` less)** extra level-0 RAM.
   - **BEIR NQ (`250,000`)**: `v3-geom-M8` reaches `75.57%` / `79.03%` / `84.51%` / `93.35%` (`0.27–0.58 ms`), again beating `FAISS M=16`, `v2-ring-chord-M4`, `acorn-1`, and `acorn-gamma` at every $S$.
   - **Native ARM NEON Mode 3 (`v3-full-guard-sq8`)**: **`100.00%` Recall@10** at $S \le 1\%$ on both corpora in **`0.09–0.11 ms` (Quora)** and **`0.05–0.08 ms` (NQ)** — beating BLAS `exact-brute-force` by **`4.5×` / `15.9×` / `30.8×` (Quora)** and **`3.2×` / `10.0×` / `18.9×` (NQ)**, and beating `hnswlib-M16` / `pgvector 0.8.7` by **`725×–2,430×`** at $S=0.1\%$.
   - **Honest Tradeoff**: Unbounded walks (`hnswlib-M16` `99.5%–99.9%`, `pgvector` `73.2%–97.4%`) retain higher graph-only recall at $S \le 1\%$ (and slightly higher recall at $S=5\%$ on Quora: `99.22%`/`97.15%` vs `95.25%`) at `7×–460×` higher latency.

3. **H3v3 — Multi-Corpus Cluster-Aligned Correlation & Local-Stall Guard (`P3a`, `P3b` — BOTH SUPPORTED):**
   - **`r <= 0.5` (`P3a`)**: `v3-geom-M8` beats `faiss-hnsw-M16` by **`+49.00 ± 3.57` pts** on Quora (`54.56%` vs `5.56%`) and **`+53.19 ± 2.57` pts** on NQ (`58.46%` vs `5.26%`). `v3-full-guard-sq8` escalates depleted queries on hop 1 (`667/728` Quora, `629/715` NQ), lifting Recall@10 to **`97.17%` (`0.35 ms` med / `1.56 ms` P99)** on Quora and **`96.42%` (`0.17 ms` med / `0.49 ms` P99)** on NQ (`131×–193×` faster than `hnswlib-M16`).
   - **`r >= 2.0` (`P3b`)**: Fast-path `ACORN-GLS` ($\tau_{\text{high}}=0.55$) cuts distance evaluations by **`3.82×` (`0.262×`)** on Quora (`749.8` vs `2,863.8`) and **`3.11×` (`0.322×`)** on NQ (`776.9` vs `2,416.1`) with Recall@10 within **`-0.99` pt** (Quora) and **`-0.93` pt** (NQ).

4. **H4v3 — Persistent PostgreSQL 17 SpiceDB Revocation (`P4a`, `P4b` — BOTH SUPPORTED):**
   - Persistent PostgreSQL 17 SpiceDB `DeleteRelationships` + mirror + UBP + `CRoaring`: **`67.28 ms` median, `0` vector writes** (`1,024` docs / `153,600` chunks, $n=5$) vs. PostgreSQL 17 + `pgvector 0.8.7` transactional `UPDATE`: **`179.4 s` (`179,390.6 ms`)** = **`2,666.2×` slower**.

5. **H5v3 — 4-Way `InitEntryPortals` Ablation (`P5` — SUPPORTED):**
   - Adding 4 portals to `FAISS M=16` changes recall by only `-0.56` to `+0.62` pts (`6.37%`/`21.71%`/`36.29%` vs `5.75%`/`22.07%`/`36.85%`).
   - Disabling portals completely on `H-HNSW v2` (`hhnsw-v2-geom-M8-noportal`) retains **`101.0%` / `102.3%` / `101.0%`** of `v3-geom-M8`'s recall gain over `FAISS M=16` across $S \le 1\%$ (`67.18%` / `79.59%` / `86.51%`), proving geometric bridges drive the gain.

---

## 3. Next Gate
- Proceed to **GSD Phase 20 (`20-01`)**: Fresh independent `pro` provenance-first audit and runtime Brake 2/3 reviews of `paper/prism_ann.pdf` and `paper/figures/v3_fig*.png` -> `results/v3/review/`.
