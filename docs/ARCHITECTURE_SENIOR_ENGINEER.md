# Prism-ANN: Senior Systems Engineer & Architect Guide

> **Three-Audience Documentation Set:**
> - **New-Grad / Associate Engineer:** [`ONBOARDING_NEW_GRAD.md`](ONBOARDING_NEW_GRAD.md) (RAG & HNSW basics, analogies, end-to-end query trace).
> - **Senior Engineer / Architect (this file):** Data structures, CSR/Z-order memory layout, C++17 & NEON kernels, `ZedToken` snapshot concurrency, delta ingestion/compaction, and operational trade-offs.
> - **Researcher / External Reviewer:** [`RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md`](RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md) & [`../paper/prism_ann.tex`](../paper/prism_ann.tex).

---

## 1. End-to-End Architecture & Subsystem Ownership

| Component | Implementation | Key Design Choice |
| :--- | :--- | :--- |
| **Authorization Cut (`P_UBP`)** | [`src/modules/prism_ann/ubp_resolver.py`](../src/modules/prism_ann/ubp_resolver.py) | Decouples static ingest-time `Anc(v_i)` prefixes from mutable SpiceDB `E^+`/`E^-` permission tuples; halts at untainted containers (`Algorithm 1`). Legacy facade assumes static container hierarchy. |
| **Dynamic DAG + Atomic Lineage Revisions** | [`src/modules/prism_ann_v3/dynamic_dag_ubp.py`](../src/modules/prism_ann_v3/dynamic_dag_ubp.py) | `DynamicMultiParentAuthGraph` separates single-edge unlinks (`remove_hierarchy_edge`) from whole-subtree quarantine (`decommission_subtree`); `VersionedLineageCorpus` publishes immutable `CorpusRevisionSnapshot`s bound to `zed_token` (`FREEZE_v3_3.md` `9/9`). |
| **Z-Ordered Layout & `CRoaring`** | [`src/modules/prism_ann/trimodal_planner.py`](../src/modules/prism_ann/trimodal_planner.py) | Sorts vector IDs lexicographically by `(Anc(v_i), tau_1(v_i))`; primary containers become single `[start, end)` `RunContainer` intervals. |
| **H-HNSW v2 Geometric Bridges** | [`src/modules/prism_ann_v3/geometric_hhnsw.py`](../src/modules/prism_ann_v3/geometric_hhnsw.py) | Extracts upper-layer CSR + `2M=32` level-0 neighbors from FAISS `M=16` (`0` rebuild confusion) and appends `M_bridge=8` Vamana/RNG-diverse edges (`4` L3 folder, `2` L2 container, `2` Meaning Magnet). |
| **Tri-Modal Planner & Stall Guard** | [`src/modules/prism_ann_v3/trimodal_v3.py`](../src/modules/prism_ann_v3/trimodal_v3.py) | Mode 1 (`1-hop`), Mode 2 (`ACORN-GLS` + 3-stage stall guard), Mode 3 (contiguous `SQ8`+`FP32` or exact `FP32` range scan). |
| **Native C++17 / ARM NEON Kernel** | [`bench/prism_ckernel.cpp`](../bench/prism_ckernel.cpp) | `prism_ranges_{set,clear}_bitset`, `prism_mode3_scan_ranges_{f32,sq8}`, `prism_search_hhnsw_gls`, `prism_select_rng_bridges`, `prism_remap_hnsw_csr`. |
| **Live SpiceDB & PG17 Drivers** | [`bench/engines.py`](../bench/engines.py) | Real `SpiceDBPostgresService` (`spicedb v1.57.1`, PostgreSQL `17.12`, `synchronous_commit=on`, `pgvector 0.8.7`) and atomic `ZedToken` reader snapshot swap. |

---

## 2. Data Layout, Memory Footprint & Multi-Parent DAG Support

### 2.1 Memory Budgeting at `N = 522,931`, `d = 384`, `M = 16`
- **Base FAISS `IndexHNSWFlat`:** `~876.6 MB` (`1,536 B/node` FP32 vector + `128 B/node` level-0 `int32` neighbors + upper layers).
- **Geometric Bridges (`v3-geom-M8`):** Fixed `8 × 4 B = +32 B/node` (`16.73 MB`, **`+1.91%` graph RAM**, vs. `+224 B/node` level-0 extra graph RAM for `ACORN-gamma`, `gamma=4, M_beta=64`).
- **Two Mode-3 Storage Options:**
  - **Zero Extra Vector RAM (`v3-full-guard-f32`, `prism_mode3_scan_ranges_f32`):** Reuses the existing Z-ordered `FP32` corpus array directly (`+0 B/node` vector overhead; total index overhead remains `+1.91%`, mathematically exact top-$k$ over all $N_{\text{cand}}$ candidates).
  - **Bandwidth-Optimized Auxiliary `SQ8` (`v3-full-guard-sq8`, `prism_mode3_scan_ranges_sq8`):** Retains an auxiliary `N × d` `int8` copy alongside `FP32` vectors (`+384 B/node` = `+200.8 MB`, `+22.9%` over base HNSW; `+416 B/node` = **`+24.8%` combined**), accelerating large Mode-3 scans (`vdotq_s32`, 64 int8 MACs/iter) + top-`max(4k, 64)` exact `FP32` rerank (`vfmaq_f32`).

### 2.2 Multi-Parent DAG Secondary Parents & Dynamic Lineage Revisions
- For canonical tree-structured organizational folders, each container token $g$ compiles to **1 contiguous `[start, end)` run** ($O(1)$ range descriptor).
- For **multi-parent DAGs** (**Theorem 2**), secondary parent containers $g_{\text{sec}}$ that cross canonical subtrees maintain explicit `CRoaring` descendant posting bitmaps $B_{g_{\text{sec}}}$ across disjoint runs (`O(#runs)` intervals), remaining directly consumable by both `prism_ranges_set_bitset` and `prism_mode3_scan_ranges_{f32,sq8}` with zero false positives/negatives.
- **Dynamic Edge Additions & Multi-Parent Unlinks (`DynamicMultiParentAuthGraph` + `VersionedLineageCorpus`):** Never map single-edge structural unlink (`remove_hierarchy_edge(p, c)`) to global child blacklisting (which breaks surviving shared parents `B -> C`), and never apply blind $B_{p_1} \gets B_{p_1} \setminus B_c$ (which breaks same-parent alternate paths $P \to X \to C$ and upstream ancestors). Instead, mutate exact graph edges and atomically publish a frozen `CorpusRevisionSnapshot` recomputing reachability-exact transitive postings (`0` vector-index writes), pinned atomically alongside SpiceDB's opaque `ZedToken` with fail-closed `StaleOrMissingSnapshotError` / `safe_leaf_fallback` when expired (`R9a` `0` FP/FN across `1,000` independent DAGs/`5,000` mutations; `R9b` `13/13` live SpiceDB scenarios). Direct E2E timing (`R10`) also shows exact `FP32` beats in-timer `SQ8` quantization+scan at $S \le 0.1\%$ in mirror mode (`0.0384/0.0736 ms` vs `0.0537/0.0805 ms`), reversing at $S \ge 0.5\%$.

---

## 3. Graph Navigation (`ACORN-GLS v2`), Anti-Starvation & Stall Guard

Inside `prism_search_hhnsw_gls` (`bench/prism_ckernel.cpp:516-838`):
1. **O(N_cand / 64) Filter Setup & O(1) Epoch Visited Table:** Instead of memsetting a `523k` visited byte-array or rebuilding a `65 KB` bitset per query, `prism_ranges_set_bitset` / `prism_ranges_clear_bitset` mutate only `[s_r >> 6, e_r >> 6]` words; `visited_epoch[v] == current_epoch` resets via a single integer increment.
2. **Local Survival Routing ($\hat{S}_{\text{loc}}(v) = |\mathcal{N}_1(v) \cap B_\Phi| / |\mathcal{N}_1(v)|$):**
   - `mode == 0` ($\hat{S}_{\text{loc}} \ge \tau_{\text{high}} = 0.55$): dense 1-hop fast-path, skipping bridges and 2-hop expansions (saves `3.11x–3.82x` distance evaluations at $r \ge 2.0$).
   - `mode == 1` ($\tau_{\text{low}} \le \hat{S}_{\text{loc}} < \tau_{\text{high}}$): authorized 2-hop base expansion + 1/2-hop geometric bridges.
   - `mode == 2` ($\hat{S}_{\text{loc}} < \tau_{\text{low}} = 0.02$): depleted teleport + bridge base links + up to `4` unauthorized 1-hop hubs pushed onto `cand_queue` only (never to `results`, preventing frontier starvation).
3. **Three-Stage Local-Stall Mode-3 Escalation (`tau_stall = 0.04, n_guard = 25,000`):**
   - **(a) Hop-1 depleted entry:** `curr == ep` unauthorized, `s_loc_hat < tau_stall`, `< k` authorized 2-hop neighbors.
   - **(b) Hop-16 sustained depletion:** mean early `s_loc_hat < tau_stall` or `n_auth_found < k`.
   - **(c) Post-loop depletion:** final `n_auth_found < k` or `mean_s_loc_hat < tau_stall`.
   - When `stalled && N_cand <= N_guard`, escalates cleanly to Mode 3 (`FP32` or `SQ8`+`FP32` rerank).

---

## 4. Concurrency, Revocation Consistency & Dynamic Writes

### 4.1 `ZedToken` Snapshot Isolation on Revocation (`R4a`/`R4b` + Live `R11`)
- **Edge Revocation Path:**
  $$T_{\text{revoke}} = T_{\text{PG-commit}} + T_{\text{mirror-prop}} + T_{\text{UBP-compile}} + T_{\text{atomic-swap}}$$
  The vector index receives **`0` writes**. In `R4b` (`11,244` live concurrent C++ reader traversals across 4 threads using local integer snapshot versions), queries starting before $t_{\text{swap}}$ finish safely on immutable snapshot $\zeta=1$ (`4` crossed cutoff without torn reads), `0` post-swap queries read $\zeta=1$, and `0 / 6,039` post-$\zeta_{\text{rev}}$ queries leaked any revoked chunk. Extending this to live native SpiceDB v1.57.1 `R11` (`8` threads, `1,760` queries using opaque serialized `ZedToken`s: `423` pre-revocation `at_exact_snapshot`, `1,337` post-revocation `at_least_as_fresh`, `1.481 ms` SpiceDB median RPC, `0.116 ms` index median search) yielded `0` oracle mismatches, `0` post-revocation leaks, and `0` stale errors.
- **Scale Invariance:** Deleting a single container edge covering `128 → 490,419` chunks on persistent PG17 SpiceDB stays flat (`0.74–1.66 ms` median, `0` vector writes).

### 4.2 Dynamic Document Writes (`R5`)
- **Read Path Separation:** New chunks append in `5.3–23.9 µs/vec` (`+1k..+25k` vectors) to an online delta buffer scanned alongside the main Z-order array without blocking queries or triggering immediate full re-sorts.
- **Off-Critical-Path Compaction:** Background lexicographic re-sort (`1.30–2.36 s`) + C++ `prism_remap_hnsw_csr` (`116.3–121.6 ms` across `500k` CSR adjacency lists) atomically swaps the dense buffer back to contiguous Z-order intervals.
