# Pre-Registered Protocol v3.2 — Second-Round Research Audit (`R6`–`R8`)

- **Date Created:** 2026-11-23
- **Parent Confirmatory Protocol & Freeze:** [`experiments/v3/PROTOCOL_v3.md`](PROTOCOL_v3.md) (`FREEZE_v3.md` `7/7`), [`experiments/v3/PROTOCOL_v3_1.md`](PROTOCOL_v3_1.md) (`FREEZE_v3_1.md` `8/8`)
- **Rule:** None of the 8 frozen algorithm/kernel files in `FREEZE_v3_1.md`, nor `results/v3/summary.json`, nor `results/v3/reviewer_audit_v3_1.json` are altered. All `v3.2` experiments are strictly additive and logged per-record to `results/v3_2_audit/raw/v3_2_reviewer_audit.jsonl`, recomputed deterministically via `bench/recompute_v3_2.py --check results/v3/reviewer_audit_v3_2.json`.

---

## Pre-Registered Predictions (`PR6`–`PR8`)

### `PR6` (`R6`: Multi-Parent DAG Property-Based Fuzzing for Theorem 1B)
- **Dataset / Topologies:** `5,000` independently randomized **Multi-Parent Authorization DAGs** across `(b, L) ∈ {(8, 4), (4, 5), (6, 4)}` (`1..20` subtractive `DENY` exclusions, `1..4` positive grants). At levels `2..L`, `30%` of containers and leaf documents receive `1..2` additional secondary parents across distinct container subtrees (creating diamond and multi-path sharing).
- **Oracle:** Exhaustive DAG reachability under Zanzibar deny-dominates-grant precedence:
  $$D_{\mathrm{auth}}(u, \zeta) = \operatorname{Reach}_{E^+}(u) \setminus \operatorname{Reach}_{E^+ \cup E^-}^{\mathrm{deny}}(u).$$
- **Success Criterion (`PR6`):** `0 / 5,000` leaf-document set mismatches (`0` false positives, `0` false negatives) between $\mathcal{P}_{\text{UBP}}$ compiled with full descendant posting bitmaps $B_g$ and $D_{\mathrm{auth}}(u, \zeta)$.

### `PR7` (`R7`: Two-Track Fair Benchmark + `RACORN-1` & `FP32` Mode-3 Baselines)
- **Corpus & Workload:** Full BEIR Quora (`N = 522,931`, `384-d`, reserved held-out test queries `[500..9,984]`, `seed=0`, `50` queries per selectivity) across $S \in \{0.01\%, 0.1\%, 0.5\%, 1.0\%, 5.0\%\}$ (`1,500` per-query records).
- **Systems (all `M=16, efc=64, efs=64`):**
  1. `faiss-hnsw-M16` (pure C++ `IndexHNSWFlat + IDSelectorBitmap`),
  2. `acorn-1` (pure C++ compiled upstream `stanford-futuredata/ACORN` `γ=1`),
  3. `racorn-1-fallback` (pure C++ predicate-agnostic 2-hop + rejected-node traversal fallback matching *RACORN*, `arXiv:2607.00768v2`, executed on the exact same `M=16` HNSW graph),
  4. `v3-geom-M8` (pure C++ graph-only geometric bridges + GLS, `+1.91%` graph RAM),
  5. `v3-full-guard-f32` (pure C++ hybrid + exact `FP32` Mode-3 range scan via `prism_mode3_scan_ranges_f32`, **`0 B/node` extra vector RAM**, `+1.91%` total extra RAM), and
  6. `v3-full-guard-sq8` (pure C++ hybrid + `SQ8` Mode-3 range scan + top-64 `FP32` rerank, `+24.8%` total extra RAM).
- **Two Separate Timing Tracks:**
  - **Track 1 (Algorithmic / Pure C++ Kernel):** Every system receives its already-materialized native filter structure (`IDSelectorBitmap`, permuted `uint8` map, or pre-populated Z-order bitset/ranges) strictly **outside** `perf_counter_ns()`.
  - **Track 2 (End-to-End Request $T_{\mathrm{total}} = T_{\mathrm{auth}} + T_{\mathrm{filter\_compile}} + T_{\mathrm{ANN+rerank}}$):** Adds live-measured `filter_compile_ms` (`packbits`/`perm` vs. Z-order `CRoaring` range extraction + `O(N_cand/64)` bitset set/clear) and measured persistent PostgreSQL 17 SpiceDB `H1v3` broad-principal medians (`98.30 ms` `LookupResources` for leaf-bitmap baselines vs. `3.49 ms` live `ReadRelationships+UBP` and `0.35 ms` local-mirror `UBP`).
- **Success Criterion (`PR7`):** `0 / 1,500` authorization leaks; on Track 1, `v3-geom-M8` outperforms `faiss-hnsw-M16`, `acorn-1`, and `racorn-1-fallback` in Recall@10 at all $S \le 1.0\%$, and both `v3-full-guard-f32` and `v3-full-guard-sq8` achieve `100.0%` Recall@10 at $S \le 1.0\%$ in `<= 0.35 ms` pure C++ median latency; on Track 2 at $S \le 1.0\%$, `v3-full-guard-sq8` and `v3-full-guard-f32` achieve `>= 20x` speedup over persistent PG17 `LookupResources` baselines and `>= 100x` with mirror UBP.

### `PR8` (`R8`: Exact vs. Empirical Recall Shortlist & Zero-RAM `FP32` Parity Audit)
- **Corpus & Workload:** Full BEIR Quora (`N = 522,931`, `384-d`, `80` queries per selectivity across $S \in \{0.01\%, 0.1\%, 0.5\%, 1.0\%\}$, `320` per-query records).
- **Systems:** `SQ8 + top-M_rerank FP32` across $M_{\mathrm{rerank}} \in \{10, 32, 64, 128\}$ vs. exhaustive exact `FP32` Mode 3 (`audit_scan_zorder_f32_neon`, `0 B/node` extra vector RAM).
- **Success Criterion (`PR8`):** At $S = 0.01\%$, `100.0%` of queries satisfy $N_{\mathrm{cand}} \le 64$ (mathematical exactness guarantee for $M_{\mathrm{rerank}}=64$); for $S \in \{0.1\%, 0.5\%, 1.0\%\}$ ($N_{\mathrm{cand}} > 64$), `M_rerank=64` achieves `>= 99.8%` empirical Recall@10 while exact `FP32` Mode 3 delivers `100.00%` guaranteed top-10 recall in `<= 0.25 ms` median latency with `0` extra vector RAM.
