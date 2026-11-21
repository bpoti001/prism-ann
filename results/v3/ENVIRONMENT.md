# Prism-ANN v3 Evaluation Environment (ADR-0004 & ADR-0005)

Recorded prior to executing the single frozen confirmatory v3 evaluation (`v3-confirmatory-001`, Phase 19).

## Hardware & OS
- **Machine**: Apple M2 Pro (10 logical CPUs, 16.0 GB unified RAM)
- **OS**: macOS-26.6.2-arm64 (arm64, Apple Silicon NEON + ARMv8.2-A `vdotq_s32` dotprod)
- **Compiler**: Apple clang version 21.0.0 (`clang-2100.1.1.101`, SDK `MacOSX26.5.sdk`), flags `-O3 -mcpu=native -std=c++17 -shared -fPIC`
- **TeX Engine**: Tectonic 0.17.0

## Python Runtime
- **Interpreter**: `/Users/tejap/memory_paper/.venv-bench/bin/python` (`Python 3.11.5`)
- **Packages**: `numpy 1.26.4`, `scipy 1.17.1`, `torch 2.15.0`, `sentence-transformers 6.3.0`, `faiss-cpu 1.16.0`, `hnswlib 0.8.0`, `psycopg 3.3.9`, `pgvector 0.5.1`, `authzed 1.25.0`, `pyroaring 1.2.0`, `pyarrow 17.0.0`, `matplotlib 3.11.2`.

## Native Real Engines & Availability

| Engine | Status | Version / Source | Notes |
|---|---|---|---|
| **Prism-ANN v3 C++ Kernel** | Available | `bench/prism_ckernel.cpp` -> `bench/_build/libprism_ckernel.dylib` | Native C++17 + ARM NEON (`has_neon=1`, `has_dotprod=1` `vdotq_s32`), frozen in `FREEZE_v3.md` |
| **SpiceDB (Memory & Persistent PostgreSQL 17)** | Available | `spicedb v1.57.1` (`/opt/homebrew/bin/spicedb`) | Native macOS arm64 binary; evaluated on BOTH `--datastore-engine memory` AND persistent `--datastore-engine postgres` backed by PostgreSQL 17.12 (`spicedb migrate head`) |
| **PostgreSQL + pgvector** | Available | `PostgreSQL 17.12` + `pgvector 0.8.7` | Native Homebrew; HNSW index with `SET hnsw.iterative_scan = relaxed_order` (`EXPLAIN`-verified) |
| **FAISS HNSW + IDSelector** | Available | `faiss-cpu 1.16.0` | `IndexHNSWFlat(384, 16, METRIC_INNER_PRODUCT)` + `IDSelectorBitmap`, exact C++ `hnsw_stats.ndis` |
| **stanford-futuredata/ACORN (`ACORN-1` & `ACORN-gamma`)** | Available | Upstream `c259f11cdbec` compiled natively + `bench/acorn_cwrap.cpp` | Evaluates BOTH `ACORN-1` ($\gamma=1, M_\beta=32$) AND `ACORN-gamma` ($\gamma=4, M_\beta=64$, level-0 degree `M_beta + 1.5*M = 88`, `+224 B/node` extra level-0 RAM over base `M=16`) |
| **hnswlib** | Available | `hnswlib 0.8.0` | Native C++ HNSW (`M=16, efConstruction=64, efSearch=64`) with Python filter callback (`C++/Py-cb`) |
| **CRoaring (`pyroaring`)** | Available | `pyroaring 1.2.0` | C++ CRoaring bitmaps with `.run_optimize()` used symmetrically for UBP and SpiceDB leaf bitmap build |
| **Qdrant** | Unavailable | No native Homebrew bottle / Docker daemon unavailable | Excluded as measured baseline (no mock substituted); logged in `results/v3/DEVIATIONS.md` |
| **HoneyBee** | Unavailable | No public implementation | Discussed in Related Work / Taxonomy only |

## Real Public Corpora & Encoder
- **Embedding Model**: Locally cached `sentence-transformers/all-MiniLM-L6-v2` (384-d, L2-normalized, Apple Silicon MPS `device="mps"`).
- **Corpus 1 (Primary)**: Official BEIR Quora (`BeIR/quora`, `N = 522,931` passages). Confirmatory test queries strictly sampled from indices **`[500..9,984]`** (`9,485` queries; `0` ID overlap, `0` exact text overlap, 100% disjoint from Phase 17 dev queries `[0..499]`).
- **Corpus 2 (Cross-Domain Wikipedia)**: Official BEIR Natural Questions (`BeIR/nq` from HuggingFace mirror, first `N = 250,000` Wikipedia passages) + strictly disjoint BEIR NQ test queries (`3,452` queries; `0` ID overlap, `0` exact text overlap).
  - `corpus_minilm_250000.npy` SHA-256: `570eb0bf0797651b612a63b2efdcf446c3ba6e4f3fb144ff15ff8cad83fcfd42`
  - `queries_minilm.npy` SHA-256: `6757766de8dfc120e075a579f93180a4e0d4afa58ef94c426ec858ef6ab27599`
