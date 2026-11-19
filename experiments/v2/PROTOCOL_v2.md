# Prism-ANN v2 — Pre-Registered Confirmatory Protocol

- **Governing ADRs**: ADR-0001, ADR-0002, ADR-0003, ADR-0004
- **Registered by**: planner/orchestrator, 2026-11-19, before any v2 code or run
- **Frozen algorithm**: see `FREEZE.md` (SHA-256 of `src/modules/prism_ann/*`)
- **Status**: `PRE_REGISTERED` (commit this file before the builder starts)

## Shared setup
- **Corpus**: BEIR Quora corpus (~523k passages), all-MiniLM-L6-v2 (local cache), L2-normalized, 384-d, cosine/IP.
- **Queries**: BEIR Quora test queries. Sample 500 per condition per seed. Never inserted into the corpus.
- **Seeds**: 3 (graph build plus query sample). Report mean and 95% CI across seeds.
- **Hierarchy overlay**: Zanzibar tree org → L1 → L2 → folder → doc with L=4, b=8. Passages are grouped into docs of ~150 chunks.
  - **Random assignment** (r ≈ 1): docs are placed in folders uniformly at random.
  - **Cluster-aligned assignment** (controls r): docs go to folders by k-means cluster, so authorization correlates with embedding space.
- **Frozen Prism parameters**: M=16, M_bridge=4, τ_high=0.25, τ_low=0.02, ≤4 entry portals, efSearch=64. Base graph construction may be delegated to FAISS HNSW for scale. This is a recorded engineering deviation; the traversal algorithm is unchanged.
- **Ground truth**: exact brute-force top-10 within the filtered set.
- **Primary metrics**: Recall@10 and distance computations per query. **Secondary**: latency, with language noted.
- **Mandatory ablation**: "Prism graph-only" (Mode 3 flat scan disabled). This isolates the express bridges and GLS from the trivially exact flat-scan fallback.

## H1v2 — UBP correctness against real SpiceDB, and resolution cost
- **P1a (confirmatory)**: For ≥ 200 sampled principals with 0–20 DENY edges, the set of docs reachable via UBP tokens equals SpiceDB `LookupResources` output exactly. Prediction: 0 mismatches.
- **P1b**: |T⁺_UBP| ≤ k₀ + m(b−1)L in 100% of cases.
- **P1c**: For principals with ≥ 1,000 authorized docs, the median of UBP resolution plus bitmap build is ≥ 10× lower than the median of SpiceDB `LookupResources` streaming plus leaf bitmap build. Falsified if < 10×.

## H2v2 — Low-selectivity recall (random assignment)
- At S ∈ {0.1%, 0.5%, 1%, 5%}:
  - **P2a**: Prism graph-only Recall@10 ≥ FAISS HNSW + IDSelector (same efSearch) + 10 points at S ≤ 0.5%.
  - **P2b**: If FAISS ACORN is available, Prism graph-only recall is within −2 points of ACORN-1 or better, at ≤ 1.0× its distance computations. Otherwise this prediction is marked untestable.
  - **P2c**: Prism full (with the Mode 3 planner) Recall@10 ≥ 99% at S ≤ 0.5%. Expected to be near-trivial; reported for completeness, not as a contribution.

## H3v2 — Correlation (cluster-aligned assignment, S fixed at 2%)
- **P3a**: At measured r ≤ 0.5, Prism graph-only Recall@10 ≥ FAISS HNSW + IDSelector + 10 points.
- **P3b**: At measured r ≥ 2, Prism graph-only uses ≤ 0.8× the distance computations of the "static 2-hop" ablation (GLS disabled), with recall within −1 point.
- r is **measured** per query (local selectivity among the unfiltered top-100 ÷ S), not just set.

## H4v2 — Revocation cost on real engines
- **P4a**: Revoking one folder edge in SpiceDB covering ≥ 1,000 docs (~150k chunks) requires 0 vector-store writes. Measure SpiceDB `DeleteRelationships` plus next-query UBP latency.
- **P4b**: The same revocation as a pgvector `UPDATE` of an ACL column on ~150k rows (real PostgreSQL) is ≥ 100× slower than P4a's path. Falsified if < 100×.

## Reporting rules
- All four hypotheses are reported, including any that are falsified.
- Any deviation from this file (dataset, parameters, chunking, missing baselines) goes in a "Protocol Deviations" table in the paper.
- v1 numbers aren't reused anywhere in v2 claims.
