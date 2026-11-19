# Project Context & Architectural System of Record (`CONTEXT.md`)

> **Role of this Document (ADR-to-arXiv Research & Software Factory):**
> This file is the **single entry point** for all research and engineering agents (`@onboarding`, `@architect`, `@engineer`, `@pr-reviewer`, `@research-factory`).
> It unites the **System Map**, **Canonical ADR-to-Theorem Registry**, **Deep Module Ownership**, **Autoresearch Hypothesis Ledger**, and **Delete-Zone**.

---

## 1. Project Identity & Research Scope

- **Repository**: `/Users/tejap/memory_paper`
- **Published Foundation**: `EngramRAG` (`arXiv:2609.32049`) — Dynamic Usage-Weighted Topology and Synaptic Consolidation for Multi-Hop Agentic Memory
- **Active Research Track**: `Prism-ANN` — Upward-Pruned SpiceDB ReBAC Capability Tokens, Ancestor-Stitched Express Bridges, and Local-Selectivity-Adaptive Filtered HNSW for EMKP Pipelines
- **Target Venues**: VLDB, SIGMOD, SIGIR, ICDE, arXiv (`cs.DB`, `cs.IR`, `cs.CR`)

---

## 2. Canonical Architecture Map & Deep Module Ownership

All research and systems modules enforce **Deep Module boundaries** (small public entry points hiding internal algorithmic complexity).

| Module / Subsystem | Repository Path | Responsibility & Public Seam | Governing ADRs | Mapped Paper Theorems |
|---|---|---|---|---|
| **EngramRAG Graph Memory** | `src/graph_memory.py`, `src/epigraph_pipeline.py` | Usage-Modulated PPR (U-PPR), Hebbian Plasticity, CATD Decay, Quad-Leg RRF | `ADR-0000` | `EngramRAG` Eq. 1–7 |
| **SpiceDB UBP Auth Resolver** | `src/modules/prism_ann/ubp_resolver.py` | Subtractive-Aware Upward Boundary Pruning ($\mathcal{P}_{\text{UBP}}$) over Zanzibar DAGs with $O(1)$ zero-write revocation | `ADR-0001` | **Theorem 1** (UBP Token & Cut Bound) |
| **Ancestor-Stitched HNSW & ACORN-GLS** | `src/modules/prism_ann/hnsw_gls.py` | Hierarchy-Stitched Express Bridges ($M_{\text{bridge}}=4$) + `POPCNT` Local-Selectivity-Adaptive 1/2-hop & Teleport Traversal | `ADR-0002` | **Theorem 2** (Percolation Cliff) & **Theorem 3** (Express Bridge Restoration) |
| **Z-Ordered Roaring-SIMD Planner** | `src/modules/prism_ann/trimodal_planner.py` | Lexicographic `(Container, Magnet)` Z-Order Layout + Roaring `RunContainer` SIMD Flat Scan & Shard-Coupled Router | `ADR-0003` | **Theorem 4** (Hardware Crossover & Shard Coupling) |
| **3-Brake Academic & Governance Auditor** | `research_factory.py`, `verify_hallucinations.py`, `run_paperviz_audit.py`, `run_scholarpeer_review.py` | Enforces ADR parity, protocol pre-registration, 0-hallucination LaTeX metrics, PaperViz ($\ge 95/100$), and ScholarPeer review | `ADR-0000` | All Empirical Tables & Figures |

---

## 3. Canonical ADR-to-Theorem Registry

| ADR ID | Title | Status | Scope / Bounded Context | Local Mirror | Mapped Paper Section & Theorem |
|---|---|---|---|---|---|
| **ADR-0000** | ADR-to-arXiv Research & Software Factory Governance Gate | `accepted` | All Modules, Experiments & Manuscripts | [`docs/adr/0000-adr-to-arxiv-research-factory.md`](./docs/adr/0000-adr-to-arxiv-research-factory.md) | Methodology & Reproducibility Protocol |
| **ADR-0001** | Subtractive-Aware Upward Boundary Pruning (UBP) over SpiceDB / Zanzibar ReBAC DAGs | `accepted` | `src/modules/prism_ann/ubp_resolver.py` | [`docs/adr/0001-spicedb-subtractive-upward-boundary-pruning.md`](./docs/adr/0001-spicedb-subtractive-upward-boundary-pruning.md) | Section 3.1 — **Theorem 1** & **Corollary 1** |
| **ADR-0002** | Ancestor-Stitched Express Bridges (`H-HNSW`) and Bitmask-`POPCNT` Adaptive `ACORN-GLS` Traversal | `accepted` | `src/modules/prism_ann/hnsw_gls.py` | [`docs/adr/0002-ancestor-stitched-filtered-hnsw-and-acorn-gls.md`](./docs/adr/0002-ancestor-stitched-filtered-hnsw-and-acorn-gls.md) | Section 3.2 — **Theorem 2** & **Theorem 3** |
| **ADR-0003** | Lexicographic Ancestor-Magnet Z-Order Layout & Shard-Coupled Tri-Modal Query Planner | `accepted` | `src/modules/prism_ann/trimodal_planner.py` | [`docs/adr/0003-z-ordered-roaring-simd-tri-modal-planner.md`](./docs/adr/0003-z-ordered-roaring-simd-tri-modal-planner.md) | Section 3.3 — **Theorem 4** |

---

## 4. Intentional Removal & Delete-Zone (Anti-Anti-Pattern Ledger)

| Rejected / Deprecated Pattern | Why Rejected | Canonical Replacement | Governing ADR |
|---|---|---|---|
| Stamping mutable user/role ACL arrays onto vector chunk payloads | Causes $O(N_{\text{chunks}})$ write amplification on permission changes or document revocation | Stamp immutable structural lineage $\operatorname{Anc}(v_i)$ on chunks; store mutable grants/denies in SpiceDB | `ADR-0001` |
| Naive SpiceDB `LookupResources` leaf document ID expansion for broad principals | Produces $10^4\text{--}10^5$ leaf tokens, stalling Roaring Bitmap union for 50–180 ms | Subtractive-Aware Upward Boundary Pruning ($\mathcal{P}_{\text{UBP}}$, $\le 50$ tokens) | `ADR-0001` |
| Static `ACORN-gamma` ($\gamma \ge 10$) full-graph neighbor expansion | Causes $9\times\text{--}53\times$ index build slowdown and $4\times\text{--}8\times$ RAM bloat | Ancestor-Stitched Express Bridges ($M_{\text{bridge}}=4$, $<8\%$ RAM overhead) + `ACORN-GLS` | `ADR-0002` |
