# Prism-ANN v2 Evaluation Environment (ADR-0004)

Recorded prior to running the smoke and confirmatory v2 evaluations (Phase 14-01).

## Hardware & OS
- **Machine**: Apple M2 Pro (10 logical CPUs, 16.0 GB unified RAM)
- **OS**: macOS-26.6.2-arm64-arm-64bit (arm64)
- **Compiler**: Apple clang version 21.0.0 (clang-2100.1.1.101) (macOS SDK: `MacOSX26.5.sdk`)
- **TeX Engine**: Tectonic 0.17.0

## Python Runtime
- **Interpreter**: `/Users/tejap/memory_paper/.venv-bench/bin/python` (`Python 3.11.5`)

| Package | Version |
|---|---|
| `numpy` | `1.26.4` |
| `scipy` | `1.17.1` |
| `torch` | `2.15.0` |
| `sentence-transformers` | `6.3.0` |
| `faiss-cpu` | `1.16.0` |
| `hnswlib` | `0.8.0` |
| `psycopg` | `3.3.9` |
| `pgvector` | `0.5.1` |
| `authzed` | `1.25.0` |
| `pyroaring` | `1.2.0` |
| `pyarrow` | `17.0.0` |
| `scikit-learn` | `1.9.1` |
| `matplotlib` | `3.11.2` |
| `requests` | `2.34.2` |

## Native Real Engines & Availability

| Engine | Status | Version / Source | Notes |
|---|---|---|---|
| **SpiceDB** | Available | `spicedb v1.57.1` (`/opt/homebrew/bin/spicedb`) | Native macOS arm64 binary; in-memory datastore over local gRPC (`authzed` v1 API) |
| **PostgreSQL + pgvector** | Available | `postgres (PostgreSQL) 17.12 (Homebrew)` + `pgvector 0.8.7` | Native Homebrew; HNSW index with `SET hnsw.iterative_scan = relaxed_order` |
| **FAISS HNSW + IDSelector** | Available | `faiss-cpu 1.16.0` | `IndexHNSWFlat` + `IDSelectorBitmap`, exact C++ `hnsw_stats.ndis` |
| **stanford-futuredata/ACORN (`ACORN-1`)** | Available | Built from upstream `https://github.com/stanford-futuredata/ACORN` commit `c259f11cdbec` | `faiss-cpu` wheel lacks `IndexACORNFlat`; compiled upstream C++ `libfaiss.dylib` + minimal `ctypes` C ABI wrapper `bench/acorn_cwrap.cpp` (exact `acorn_stats.n3 + 1` distance count) |
| **hnswlib** | Available | `hnswlib` (`pip` wheel in `.venv-bench`) | Native C++ HNSW with Python filter callback |
| **CRoaring (`pyroaring`)** | Available | `pyroaring 1.2.0` | C++ CRoaring bitmaps with `.run_optimize()` used symmetrically for UBP and SpiceDB leaf bitmap build |
| **HoneyBee** | Unavailable (not plotted) | No public implementation | Discussed in Related Work / Taxonomy only (per ADR-0004) |

## Local Encoder & Corpus Cache
- **Embedding model**: `sentence-transformers/all-MiniLM-L6-v2` (384-d, L2-normalized, Apple Silicon MPS `device="mps"`, loaded from local HuggingFace cache)
- **Corpus**: Official BEIR Quora (`BeIR/quora` + `BeIR/quora-qrels` from HuggingFace mirror; `public.ukp.informatik.tu-darmstadt.de` failed DNS resolution at download time — logged in `results/v2/DEVIATIONS.md`)
