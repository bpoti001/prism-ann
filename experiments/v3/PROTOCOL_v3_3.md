# Pre-Registered Protocol v3.3 — Dynamic Multi-Parent Mutations, Live SpiceDB `ZedToken` Concurrency & Directly Timed E2E Benchmark (`R9`–`R11`)

- **Date Created:** 2026-11-23
- **Parent Confirmatory Protocols & Freeze Manifests:** [`PROTOCOL_v3.md`](PROTOCOL_v3.md) (`FREEZE_v3.md` `7/7`), [`PROTOCOL_v3_1.md`](PROTOCOL_v3_1.md) (`FREEZE_v3_1.md` `8/8`), [`PROTOCOL_v3_2.md`](PROTOCOL_v3_2.md), & [`FREEZE_v3_3.md`](../../FREEZE_v3_3.md) (`9/9` including `src/modules/prism_ann_v3/dynamic_dag_ubp.py`)
- **Rule:** None of the 8 frozen files in `FREEZE_v3_1.md`, nor `results/v3/summary.json`, nor `results/v3/reviewer_audit_v3_1.json`, nor `results/v3/reviewer_audit_v3_2.json` are altered. All `v3.3` experiments are strictly additive and logged per-record to `results/v3_3_audit/raw/v3_3_reviewer_audit.jsonl`, recomputed deterministically via `bench/recompute_v3_3.py --check results/v3/reviewer_audit_v3_3.json`.

---

## Pre-Registered Audit Predictions (`PR9a`, `PR9b`, `PR10`, `PR11`)

### `PR9a` (`R9a`: `1,000` Genuinely Independent Multi-Parent DAGs + Dynamic Structural Mutations)
- **Workload:** Construct `1,000` freshly generated multi-parent DAGs (`1` independent random DAG per trial, zero graph reuse) spanning `(b, L) ∈ {(4, 4), (4, 5), (6, 4)}` with `30%` secondary multi-parent edge probability at levels `2..L` and indexed chunks in `DynamicPrismANNIndex`.
- **Five Dynamic Mutations Checked Per Fresh DAG (`5,000` checkpoints total):**
  1. `add_hierarchy_edge(denied_parent, allowed_doc)` post-index addition + atomic snapshot sync,
  2. `remove_hierarchy_edge(p_a, multi_parent_node)` structural unlink preserving active alternate parent path `p_b -> multi_parent_node`,
  3. `remove_hierarchy_edge(p_b, multi_parent_node)` unlinking final granted path,
  4. `remove_deny_exclusion(u, denied_node)` explicit deny removal, and
  5. `revoke_access(u, g)` followed by `grant_access(u, g)` re-grant.
- **Oracle:** Exhaustive DAG reachability under Zanzibar deny-dominates-grant precedence (`_dag_oracle_authorized_leaves`).
- **Success Criterion (`PR9a`):** `0 / 5,000` false positives and `0 / 5,000` false negatives across all `1,000` independent DAGs (`5` mutation states each) for both `VersionedLineageCorpus` candidate masks and returned `DynamicPrismANNIndex.search()` document hits.

### `PR9b` & `PR11` (`R9b` & `R11`: Live Native SpiceDB `v1.57.1` Multi-Parent Schema Matrix & Real Opaque `ZedToken` Concurrency)
- **Live Schema & Engine:** Native Homebrew SpiceDB `v1.57.1` (`ZANZIBAR_SCHEMA` with `relation parent: container`, `viewer: user`, `ethical_wall_deny: user`, `permission denied = ethical_wall_deny + parent->denied`, `permission view = (viewer + parent->view) - denied`).
- **9-Scenario Mutation Matrix (`R9b`):**
  1. Multi-parent `A -> C <- B`, grant `u` on `A` & `B`, unlink `A -> C` (one surviving path keeps `C` authorized),
  2. Unlink remaining path `B -> C` (final path removed),
  3. Direct child grant on `C` + parent edge from denied container (deny dominates) + unlink denied parent,
  4. Explicit deny on secondary parent + removal of uninvolved sibling path,
  5. Post-index `add_hierarchy_edge(B, D)` where `u` is granted `A` and denied `B` (`D` hidden across Modes 1/2/3),
  6. Deny removal (`DeleteRelationships` removing `ethical_wall_deny`),
  7. Grant revocation + re-grant,
  8. Real opaque SpiceDB `Consistency(at_exact_snapshot=zt_pre)` verification after mutation, and
  9. Combined `R11` 8-thread concurrent Stress test issuing `CheckPermission` / `LookupResources` against live SpiceDB + `DynamicPrismANNIndex.search()` bound to real opaque SpiceDB `at_exact_snapshot(zt_pre)` vs `at_least_as_fresh(zt_post)` across a live edge deletion (`>= 1,600` concurrent reads).
- **Success Criterion (`PR9b` / `PR11`):** `0` false positives and `0` false negatives against live SpiceDB `LookupResources` & `CheckPermission` at every scenario and across all concurrent reader queries (`0` post-revision leaks).

### `PR10` (`R10`: Directly Timed Same-Query E2E Requests + Matched-Recall `efSearch` Sweep)
- **Corpus & Workload:** Full BEIR Quora (`N = 522,931`, `384-d`, reserved held-out test queries `[500..9,984]`, `seed=0`) with live SpiceDB `v1.57.1`.
- **Track A (Single-Timer Directly Measured End-to-End Request):** A single `perf_counter_ns()` timer wraps the complete request on the same query/principal:
  1. Live SpiceDB authorization (`LookupResources` for external bitset baselines vs. live `ReadRelationships+UBP` or synced UBP+mirror),
  2. Native filter compilation (`IDSelectorBitmap` / `uint8` perm / `CRoaring` ranges, zero component overlap),
  3. Query conversion including in-timer `SQ8` quantization (`np.clip(np.round(q*127), -127, 127).astype(np.int8)` for `v3-full-guard-sq8`), and
  4. C++ index traversal + `FP32` reranking across `S ∈ {0.01%, 0.1%, 0.5%, 1.0%, 5.0%}` (`25` queries/cell).
- **Track B (Matched-Recall `efSearch` Sweep):** `efSearch ∈ {32, 64, 128, 256, 512}` at `S = 0.5%` and `S = 5.0%` (`25` queries each) across `faiss-hnsw-M16`, `acorn-1`, `racorn-1-fallback`, and `v3-geom-M8`.
- **Success Criterion (`PR10`):** `0` total authorization leaks across all directly timed E2E queries and matched-recall sweeps; directly timed `v3-full-guard-f32` and `v3-full-guard-sq8` (live `ReadRelationships+UBP`) beat live `LookupResources + faiss-hnsw-M16` E2E median latency by `>= 10.0x` across `S <= 1.0%` while attaining `100.0%` Recall@10, and `v3-geom-M8` dominates `faiss-hnsw-M16`, `acorn-1`, and `racorn-1-fallback` along the `S = 0.5%` Recall@10 vs. latency Pareto frontier.
