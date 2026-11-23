# Project Context & Architectural System of Record (`CONTEXT.md`)

> **Role of this Document (ADR-to-arXiv Research & Software Factory):**
> This file is the **single entry point** for all research and engineering agents (`@onboarding`, `@architect`, `@engineer`, `@pr-reviewer`, `@research-factory`).
> It unites the **System Map**, **Canonical ADR-to-Theorem Registry**, **Deep Module Ownership**, **Three-Tier Audience Documentation Map**, and **Delete-Zone**.

---

## 1. Project Identity & Research Scope

- **Repository**: `/Users/tejap/memory_paper` (`https://github.com/bpoti001/prism-ann`)
- **Published Foundation**: `EngramRAG` (`arXiv:2609.32049`) — Dynamic Usage-Weighted Topology and Synaptic Consolidation for Multi-Hop Agentic Memory
- **Active Research Track**: `Prism-ANN` — Upward-Pruned SpiceDB ReBAC Capability Tokens, Geometric Ancestor-Stitched Express Bridges, and Native SIMD Tri-Modal Filtered HNSW
- **Target Venues**: VLDB, SIGMOD, SIGIR, ICDE, arXiv (`cs.DB`, `cs.IR`, `cs.CR`)

---

## 2. Canonical Architecture Map & Deep Module Ownership

All research and systems modules enforce **Deep Module boundaries** (small public entry points hiding internal algorithmic complexity).

| Module / Subsystem | Repository Path | Responsibility & Public Seam | Governing ADRs | Mapped Paper Theorems |
|---|---|---|---|---|
| **EngramRAG Graph Memory** | `src/graph_memory.py`, `src/epigraph_pipeline.py` | Usage-Modulated PPR (U-PPR), Hebbian Plasticity, CATD Decay, Quad-Leg RRF | `ADR-0000` | `EngramRAG` Eq. 1–7 |
| **SpiceDB UBP Auth Resolver** | `src/modules/prism_ann/ubp_resolver.py` | Subtractive-Aware Upward Boundary Pruning ($\mathcal{P}_{\text{UBP}}$) over single-parent trees & multi-parent Zanzibar DAGs with $O(1)$ zero-vector-write revocation | `ADR-0001`, `ADR-0006` | **Theorem 1** (Single-Parent Tree Cardinality Bound), **Theorem 2** (Multi-Parent DAG Exact Set Equivalence) & **Corollary 1** (Revocation Boundary) |
| **Ancestor-Stitched HNSW & ACORN-GLS** | `src/modules/prism_ann/hnsw_gls.py` | Vamana/RNG Geometric Intra-Container & Intra-Magnet Express Bridges ($M_{\text{bridge}}=8$) + `POPCNT` Local-Selectivity-Adaptive 1/2-hop & Local-Stall Guard | `ADR-0002`, `ADR-0005` | **Proposition 2** (Percolation Cliff) & **Proposition 3** (Express Bridge Restoration) |
| **Z-Ordered Roaring-SIMD Planner** | `src/modules/prism_ann/trimodal_planner.py` | Lexicographic `(Container, Magnet)` Z-Order Layout + Roaring `RunContainer` SIMD Flat Scan (`FP32` & `SQ8 + M_rerank=64`) & Shard-Coupled Router | `ADR-0003`, `ADR-0005` | **Proposition 4** (Hardware Crossover & Shard Coupling) |
| **Native C++17 / ARM NEON Kernels** | `bench/prism_ckernel.cpp`, `bench/prism_audit_kernel.cpp` | Native ARM NEON (`vdotq_s32`) + `CRoaring` Mode-3 interval scan, C++ `H-HNSW`/`ACORN-GLS` traversal, 2×2×2 cache-eviction attribution, 16-thread `ZedToken` race & CSR compaction | `ADR-0005`, `ADR-0006` | §3.2 (`H-HNSW v2`), §4 (C++ NEON Kernel), §5 (`H1v3`–`H5v3` & `R1`–`R8`) |
| **Deterministic Recomputers & 3-Brake Auditor** | `bench/recompute_v3.py`, `bench/recompute_v3_1.py`, `bench/recompute_v3_2.py`, `research_factory.py`, `verify_prism_hallucinations.py`, `run_prism_paperviz_audit.py`, `run_prism_scholarpeer_review.py` | Enforces ADR parity, `FREEZE_v3.md`/`FREEZE_v3_1.md` SHA-256 integrity, bit-for-bit raw JSONL recomputation (`199,164` records), 0-hallucination LaTeX metrics (`310+` checks), and artifact-hash review verification | `ADR-0000`, `ADR-0004`, `ADR-0005`, `ADR-0006` | All Empirical Tables (`Tables I–V`) & Figures (`Fig. 1–6`) |
| **Three-Tier Audience Documentation Suite** | `docs/ONBOARDING_NEW_GRAD.md`, `docs/ARCHITECTURE_SENIOR_ENGINEER.md`, `docs/RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md`, `REVIEWER_AUDIT_REPORT.md` | Separates fresh-graduate educational onboarding, senior-systems failure/latency/memory architecture, and independent research evaluation & novelty matrix | `ADR-0006` | Pedagogical & Reviewer Audit Traceability |

---

## 3. Canonical ADR-to-Theorem Registry

| ADR ID | Title | Status | Scope / Bounded Context | Local Mirror | Mapped Paper Section & Theorem |
|---|---|---|---|---|---|
| **ADR-0000** | ADR-to-arXiv Research & Software Factory Governance Gate | `accepted` | All Modules, Experiments & Manuscripts | [`docs/adr/0000-adr-to-arxiv-research-factory.md`](./docs/adr/0000-adr-to-arxiv-research-factory.md) | Methodology & Reproducibility Protocol |
| **ADR-0001** | Subtractive-Aware Upward Boundary Pruning (UBP) over SpiceDB / Zanzibar ReBAC DAGs | `accepted` | `src/modules/prism_ann/ubp_resolver.py` | [`docs/adr/0001-spicedb-subtractive-upward-boundary-pruning.md`](./docs/adr/0001-spicedb-subtractive-upward-boundary-pruning.md) | Section III-A — **Theorem 1**, **Theorem 2** & **Corollary 1** |
| **ADR-0002** | Ancestor-Stitched Express Bridges (`H-HNSW`) and Bitmask-`POPCNT` Adaptive `ACORN-GLS` Traversal | `accepted` | `src/modules/prism_ann/hnsw_gls.py` | [`docs/adr/0002-ancestor-stitched-filtered-hnsw-and-acorn-gls.md`](./docs/adr/0002-ancestor-stitched-filtered-hnsw-and-acorn-gls.md) | Section III-B — **Proposition 2** & **Proposition 3** |
| **ADR-0003** | Lexicographic Ancestor-Magnet Z-Order Layout & Shard-Coupled Tri-Modal Query Planner | `accepted` | `src/modules/prism_ann/trimodal_planner.py` | [`docs/adr/0003-z-ordered-roaring-simd-tri-modal-planner.md`](./docs/adr/0003-z-ordered-roaring-simd-tri-modal-planner.md) | Section III-C — **Proposition 4** |
| **ADR-0004** | Provenance-Verified, Real-Baseline Evaluation Protocol (Prism-ANN v2) | `accepted` | `bench/`, `results/v2/`, Milestone 4 provenance rules | [`docs/adr/0004-provenance-verified-real-baseline-evaluation.md`](./docs/adr/0004-provenance-verified-real-baseline-evaluation.md) | Section V — Evaluation Methodology |
| **ADR-0005** | Geometric Intra-Container Express Bridges (`H-HNSW v2`), Native C++ SIMD/CRoaring Kernel & Multi-Corpus Persistent-SpiceDB Evaluation | `accepted` | `src/modules/prism_ann/`, `bench/prism_ckernel.cpp`, `results/v3/` | [`docs/adr/0005-geometric-hhnsw-cpp-simd-and-multi-corpus-eval.md`](./docs/adr/0005-geometric-hhnsw-cpp-simd-and-multi-corpus-eval.md) | Sections III-B, IV & V — Milestone 5 (`v3.0`) |
| **ADR-0006** | External Reviewer Audit Protocol (`v3.1 R1–R5` & `v3.2 R6–R8`), Multi-Parent DAG Exactness (`Theorem 2`), Two-Track Fair Attribution, and Three-Tier Audience Architecture | `accepted` | `bench/prism_audit_kernel.cpp`, `bench/run_reviewer_audit_v3_*.py`, `docs/*.md`, `paper/prism_ann.tex` | [`docs/adr/0006-external-reviewer-audit-multiparent-dag-and-two-track-fairness.md`](./docs/adr/0006-external-reviewer-audit-multiparent-dag-and-two-track-fairness.md) | Sections III-A (`Theorem 1` vs. `Theorem 2`), V-G (`R1`–`R8`), VI-B (`RACORN` & `EMA`) |

---

## 4. Intentional Removal & Delete-Zone (Anti-Anti-Pattern Ledger)

| Rejected / Deprecated Pattern | Why Rejected | Canonical Replacement | Governing ADR |
|---|---|---|---|
| Stamping mutable user/role ACL arrays onto vector chunk payloads | Causes $O(N_{\text{chunks}})$ write amplification (`179.4 s` in PostgreSQL/`pgvector`) on permission changes or document revocation | Stamp immutable structural lineage $\operatorname{Anc}(v_i)$ on chunks; store mutable grants/denies in SpiceDB (`0` vector writes) | `ADR-0001` |
| Naive SpiceDB `LookupResources` leaf document ID expansion for broad principals | Produces $10^4\text{--}10^5$ leaf tokens, stalling RPC + Roaring Bitmap union for `79–98 ms` | Subtractive-Aware Upward Boundary Pruning ($\mathcal{P}_{\text{UBP}}$, `0.35 ms` cached / `3.49 ms` live RPC) | `ADR-0001` |
| Claiming single-parent tree bound $k_0+m(b-1)L$ holds unchanged on multi-parent DAGs | Secondary parent edges allow one `DENY` node to taint multiple ancestor paths ($\bar{p}_{\text{dag}} \ge 1$, exceeded in `4.86%` of multi-parent DAGs) | Split **Theorem 1** (Single-Parent Tree Cardinality Bound) from **Theorem 2** (Multi-Parent DAG Exact Set Equivalence, `0/5,000` mismatches) | `ADR-0006` |
| Static `ACORN-gamma` ($\gamma \ge 4$) full-graph neighbor expansion | Inflates level-0 edge RAM by `7×` (`+224 B/node`) while still collapsing at $S \le 0.1\%$ | Geometric Ancestor-Stitched Express Bridges ($M_{\text{bridge}}=8$, `+32 B/node`, `+1.91%` graph RAM) + Local-Stall Mode-3 Guard | `ADR-0002`, `ADR-0005` |
