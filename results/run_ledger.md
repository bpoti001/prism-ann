# Run Ledger (ADR-0004)

Every benchmark run gets one row, including failed and exploratory runs. Rows are append-only.

| run_id | date | git SHA | freeze match? | type (confirmatory/exploratory/smoke) | command | raw dir | notes |
|---|---|---|---|---|---|---|---|
| v1-* | 2026-11-19 | various | n/a | exploratory (superseded) | `run_prism_ann_benchmarks.py` | `results/prism_ann_benchmark_results.json` | Milestone 3. Synthetic vectors, self-built baselines; the first pass contained hardcoded curves. Not used for v2 claims. |
