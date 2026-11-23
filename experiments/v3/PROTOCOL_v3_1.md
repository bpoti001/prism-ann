# Prism-ANN v3.1 — Pre-Registered Reviewer Audit Protocol

- **Governing ADRs**: `ADR-0001`, `ADR-0002`, `ADR-0003`, `ADR-0004`, `ADR-0005`
- **Registered**: 2026-11-22 (Reviewer Audit Hardening Extension to `PROTOCOL_v3.md`)
- **Frozen algorithm & audit kernels**: see `FREEZE_v3_1.md` (`8/8` SHA-256 hashes covering `FREEZE_v3.md` plus `bench/prism_audit_kernel.cpp`)
- **Status**: `PRE_REGISTERED`

## Shared Setup
- **Corpora**: Identical to `PROTOCOL_v3.md` (`BEIR Quora`, `N = 522,931` with reserved queries; `BEIR NQ Wikipedia`, `N = 250,000` with strictly disjoint queries).
- **Raw Provenance**: Every trial, query, batch, and condition emits its record to `results/v3_1_audit/raw/v3_1_reviewer_audit.jsonl`. The summary `results/v3/reviewer_audit_v3_1.json` is derived exclusively via `bench/recompute_v3_1.py` and verified bit-for-bit with `--check`.

## Pre-Registered Audit Predictions (`PR1`–`PR5`)

### `PR1` (`R1`: 10,000-Hierarchy Property-Based & Alternating Override Fuzzing)
- Evaluate `5,000` standard ReBAC trees (`but not` exclusions + revoked subtrees) and `5,000` generalized depth-5 alternating-precedence trees (`Root GRANT -> L1 DENY -> L2 Re-GRANT -> L3 Sub-DENY -> L4 Leaf override`) across `(b, L) in {(8,4), (4,5), (6,4)}`.
- **Criterion**: `0 / 5,000` standard leaf mismatches, `0 / 5,000` alternating leaf mismatches, and `100.0%` satisfaction of the Theorem 1 token bound (`|T_UBP+| <= k_0 + m(b - 1)L` and generalized rule bound).

### `PR2` (`R2`: Ultra-Low Selectivity `S = 0.01%` Multi-Corpus Benchmark)
- On depth-5 hierarchy overlays (`b = 8, L = 5`, `32,768` docs, `S_actual ~= 0.0091%`, `3` seeds x `50` queries = `150` queries/corpus) on full BEIR Quora (`522,931`) and BEIR NQ (`250,000`):
- **Criterion**: Graph-only `v3-geom-M8` achieves `>= 80.0%` Recall@10 (beating `faiss-hnsw-M16` and `acorn-1` by `>= +75.0` pts), AND complete `v3-full-guard-sq8` achieves `100.0%` Recall@10 at `<= 0.10 ms` median latency on both corpora with `0` authorization leaks.

### `PR3` (`R3`: 6-Way Cold-LLC Mode-3 Component Isolation)
- Using `bench/prism_audit_kernel.cpp` (scalar loops guarded via `#pragma clang loop vectorize(disable)`) on BEIR Quora (`522,931 x 384-d`) across `S in {0.01%, 0.1%, 0.5%, 1.0%}` with a 64 MB volatile stride-64 L1/L2/SLC flush before every query:
- **Criterion**: Under cold LLC at `S = 1.0%`, Z-order + `CRoaring` contiguity contributes `>= 4.0x` speedup (on `FP32 NEON`), `SQ8` quantization contributes `>= 2.0x` speedup (on scalar Z-order), ARM NEON contributes `>= 4.0x` speedup over portable scalar C++ `SQ8`, and portable cold scalar `SQ8` (`5_zorder_sq8_scalar`) runs in `<= 1.0 ms` median with `100.0%` Recall@10.

### `PR4` (`R4`: Subtree Revocation Scaling & Concurrent In-Flight `ZedToken` Race)
- **Part A (`R4a`)**: Persistent PostgreSQL 17 SpiceDB `DeleteRelationships` + mirror + UBP + `CRoaring` across `7` subtree sizes (`1` to `3,840` docs = `128` to `490,419` chunks, `5` trials each):
- **Criterion**: `0` vector writes across all `35` trials and `<= 25.0 ms` median latency at every subtree size.
- **Part B (`R4b`)**: `4` concurrent C++ H-HNSW reader threads executing `>= 10,000` queries while a writer commits a live PostgreSQL 17 SpiceDB `131,072`-chunk revocation at `zeta_rev` and atomically swaps the `CRoaring` snapshot:
- **Criterion**: `0` post-`zeta_rev` queries leak any chunk from the revoked subtree, and `0` queries started after the atomic swap execute against the stale `zeta_1` snapshot.

### `PR5` (`R5`: Dynamic Document Ingestion & Background Z-Order Compaction)
- Inserting batches of `{1,000, 5,000, 10,000, 25,000}` new 384-d vectors onto `500,000` Quora base vectors:
- **Criterion**: Online delta-buffer append + incremental `CRoaring` delta bitmap takes `<= 50.0 us/vector` across all batch sizes, and background full lexicographic compaction + `SQ8` quantization + C++ HNSW CSR ID remapping (`prism_remap_hnsw_csr`) completes in `<= 5.0 s` (`<= 250.0 ms` for the 500k CSR ID remap).
