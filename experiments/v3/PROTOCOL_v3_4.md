# Pre-Registered Protocol: Prism-ANN v3.4 Concurrency & Unsynced-Mirror Audit (`R12`)

- **Registered:** 2026-11-23 (before executing `bench/run_reviewer_audit_v3_4.py`)
- **Governing ADRs:** `ADR-0001`, `ADR-0005`, `ADR-0006`
- **Freeze Requirement:** `FREEZE.md` (`5/5`), `FREEZE_v3.md` (`7/7`), `FREEZE_v3_1.md` (`8/8`), `FREEZE_v3_3.md` (`9/9`, preserving `src/modules/prism_ann_v3/dynamic_dag_ubp.py` untouched), and `FREEZE_v3_4.md` (`10/10`, adding `src/modules/prism_ann_v3/consistent_snapshot_index.py`) must ALL match `100%` on a clean git tree (`git_dirty=False`) prior to execution.
- **Additive Rule:** Strictly additive. Zero prior frozen datasets (`v2`, `v3`, `v3.1`, `v3.2`, `v3.3`) are modified or overwritten.

## Targeted Verification Scope (`R12`)

Directly verifies the reviewer-recommended final concurrency and unsynced-mirror experiment (`R12` from the November 23, 2026 review of commit `378d290`):

1. **`R12a` — Deterministic Race Injection & Snapshot Atomicity (`v3.3` Control vs. `v3.4` Fix):**
   - Across `200` randomized multi-parent DAG race-injection trials (`100` structural+deny double-injection trials + `100` out-of-order concurrent multi-publisher ordering trials):
     - **Injection Point 1**: Mutate the live graph immediately after revision capture and before posting computation.
     - **Injection Point 2**: Mutate the live graph immediately after posting computation and before copying/publishing authorization state.
   - Run the same injection schedule against:
     - **Control (Frozen `v3.3` `VersionedLineageCorpus`)**: Confirm whether torn snapshots occur (disagreement among `snap.zed_token`, `snap.hierarchy_version`, `snap.token_bitmaps`, and `snap.auth_snapshot`).
     - **Treatment (`v3.4` `AtomicVersionedLineageCorpus`)**: Verify `100%` of published snapshots satisfy `snap.zed_token == snap.auth_snapshot.zed_token`, `snap.hierarchy_version == snap.auth_snapshot.hierarchy_version`, and exact bit-for-bit equality `snap.token_bitmaps == recompute(snap.auth_snapshot)`, with `0` monotonic `_latest_snapshot` ordering regressions and `0` search leaks through `ConsistentDynamicPrismANNIndex.search()`.
2. **`R12b` — Live Native SpiceDB v1.57.1 Unsynced-Mirror & Opaque-`ZedToken` Compatibility Matrix (`13` Scenario Checkpoints `C1`–`C10c`):**
   - Execute `13` end-to-end checkpoints (`C1`–`C10c`) against a real native SpiceDB v1.57.1 daemon (`memory` datastore) where external writes mutate SpiceDB directly (deny wall, structural edge addition to denied container, grant/un-deny) WITHOUT advancing the local mirror:
     - Verify `on_unavailable="fail_closed"` raises `StaleOrMissingSnapshotError` (`0` stale leaks) whenever an external `ZedToken` is un-ingested or an `at_exact_snapshot` has been evicted.
     - Verify `on_unavailable="spicedb_leaf_fallback"` queries live SpiceDB `LookupResources` directly (returning exact newly authorized / newly revoked sets with `0` mismatches against live SpiceDB `CheckPermission`), and refuses (`StaleOrMissingSnapshotError`) when no authoritative external SpiceDB lookup provider is configured.
     - Verify SpiceDB's semantic distinction between `at_least_as_fresh(zt_old)` (validly serving newer ingested snapshot `zt_new`) and `at_exact_snapshot(zt_old)` (pinned to `zt_old` before GC eviction, refusing or falling back after GC eviction).
     - Verify mirror catch-up (`sync(external_zed_token=zt_ext)`) restores fast UBP snapshot serving (`fallback_used=None`, `0` mismatches).
3. **`R12c` — Multi-Threaded Concurrent DAG Mutation, Atomic Publication, & Public `search()` Stress:**
   - `4` concurrent writer/publisher threads performing randomized structural edge additions, diamond unlinks, grants, denies, and `sync_to_revision` calls alongside `4` concurrent reader threads issuing `>= 1,000` public `ConsistentDynamicPrismANNIndex.search_with_metadata()` queries (`at_exact_snapshot` and `at_least_as_fresh`).
   - Every published snapshot is checked by `verify_snapshot_internal_consistency()`, and every read is checked against the exhaustive leaf oracle of its selected snapshot.

## Pre-Registered Falsifiable Predictions (`PR12a`–`PR12c`)

- **`PR12a` (Snapshot Atomicity & Ordering Under Race Injection):**
  - Across `>= 200` injected-race + out-of-order publication trials on `v3.4` `AtomicVersionedLineageCorpus`: `0` torn snapshots, `0` bitmap/state disagreements, `0` `_latest_snapshot` regressions, and `0` search leaks (while confirming the `v3.3` control exhibits `>= 1` torn snapshot under the exact same injection schedule).
- **`PR12b` (External SpiceDB Lag Fail-Closed & Authoritative Fallback):**
  - Across all `10/10` live SpiceDB v1.57.1 scenarios: `0` mask/search/`CheckPermission` mismatches, `>= 5` verified fail-closed `StaleOrMissingSnapshotError` refusals on un-ingested or expired external tokens (including unconfigured fallback guard), and `>= 4` verified live `spicedb_leaf_fallback` executions matching SpiceDB `CheckPermission` `100%`.
- **`PR12c` (Multi-Threaded Concurrent Public `search()` Consistency):**
  - Across `>= 1,000` concurrent multi-threaded reads and all concurrently published snapshots: `0` torn snapshots, `0` oracle mismatches, and `0` unauthorized search leaks.

## Raw Output & Deterministic Recomputer

- Raw JSONL: `results/v3_4_audit/raw/v3_4_reviewer_audit.jsonl`
- Recomputed Summary: `results/v3/reviewer_audit_v3_4.json`
- Checker: `python -m bench.recompute_v3_4 --check results/v3/reviewer_audit_v3_4.json`
