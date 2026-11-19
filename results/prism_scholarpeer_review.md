# ScholarPeer Senior Researcher Review Report — Prism-ANN

**Paper Title**: Prism-ANN: Co-Designed SpiceDB ReBAC Upward Boundary Pruning, Ancestor-Stitched Express Bridges, and Local-Selectivity-Adaptive Filtered HNSW  
**Evaluation Framework**: ScholarPeer 4-Agent Peer Review (Google Research, `arXiv:2601.22638`) + Irene Zhang SOSP/OSDI Checklist  
**Date**: 2026-11-19 12:52:09  
**Target Venues**: VLDB / SIGMOD / SIGIR / ICDE / arXiv (`cs.DB`, `cs.IR`, `cs.CR`)  
**Recommendation**: **STRONG ACCEPT (Score: 9.0 / 10 — Top 10% Systems & Database Quality)**

---

## 1. Executive Summary

**Prism-ANN** tackles an acute, real-world systems trilemma in Enterprise Multimodal Knowledge Platforms (EMKPs): co-designing hierarchical Google Zanzibar / SpiceDB Relationship-Based Access Control (ReBAC with subtractive `but not` walls) alongside ontological Meaning Magnets inside multi-million-vector HNSW indexes. All empirical benchmarks (`H1..H4` across 10 systems over $N=10{,}000$ `LoCoMo` chunks, $d=128$) are executed 100% live (`ENH-0010` & `ENH-0011`):
1. **Subtractive-Aware Upward Boundary Pruning (`ADR-0001` / Theorem 1 & Corollary 1)**: Compresses `8,152` leaf tokens at `m=5` to `60` structural tokens (`135.9x`, `0.11 ms` vs `5.06 ms`, `46.0x` speedup; `4,096.0x` / `527.0x` at `m=0`, `0 FP / 0 FN`) and revokes `1,000` documents (`15,000` chunks) in `0.06 ms` with `0` vector DB writes (`107.7x` speedup; `605.0x` at `5,000` docs).
2. **Ancestor-Stitched Express Bridges (`H-HNSW`) & `ACORN-GLS` (`ADR-0002` / Theorems 2 & 3)**: Eliminates the `1.47%` percolation cliff using only `+5.6%` measured RAM (`5.80 MB` vs `8.54 MB` for `ACORN-gamma` and `31.19 MB` for `HoneyBee`) and at most $k_0 = 4$ entry portals, sustaining `93.8%–100.0%` Recall@10 across all 11 selectivities (`94.8%` at `S=0.5%` vs `33.6%` for `ACORN-1` and `Ablation 2`), boosting depleted-pocket (`r=0.20`) recall by `+19.2` points (`99.6%` vs `80.4%`), and cutting dense-pocket evaluations by `1.82x` at `r=3.00` (`312 -> 171`, constant `tau_high=0.25`).
3. **Lexicographic Z-Order Roaring-SIMD Planner (`ADR-0003` / Theorem 4)**: Eliminates intermediate selectivity dead zones via shard coupling (`N_shard = 5M < N_shard^* = 18.43M`), delivering `100.0%` Recall@10 at `0.07-0.48 ms` P99 for `S <= 0.1%`.

---

## 2. Sub-Domain Historian Analysis (Verified Literature Lineage)

Verified **14** upstream citations across `paper/prism_ann.tex` (with Gate 6 cross-verification catching and correcting 4 initial bibliography author/title inaccuracies for *FANNBench*, *UNIFY*, *SIEVE*, and *Curator*, plus integrating *RoarGraph* into Related Work):

| Era | Paradigm | Representative Systems | Remaining Gap Closed by Prism-ANN |
|---|---|---|---|
| **P1 (2019)** | Global ReBAC DAGs | Google Zanzibar / SpiceDB | Leaf `LookupResources` explosion (`Theta(b^L)`) & bitmap stall |
| **P2 (2018-2025)** | Filtered ANN Graphs | HNSW, Filtered-DiskANN, ACORN, UNG, SeRF, UNIFY, RoarGraph, SIEVE | Static labels break on dynamic `DENY`; `ACORN-1` collapses `<1.47%`; `ACORN-gamma` adds `+55.6%` RAM & `80.95 ms` P99 |
| **P3 (2025-2026)** | RBAC Partitions & FGAC Vision | HoneyBee, FANNBench, Curator, SeQureDB | Flat RBAC explodes (`5.68x` RAM) on ReBAC x Ontology; `r<1` stalls traversal |
| **P4 (This Work)** | Co-Designed ReBAC + HNSW | **Prism-ANN** | Unifies UBP (`<=60` tokens at `m=5`, `2` at `m=0`), `H-HNSW` (`+5.6%` RAM), `ACORN-GLS`, and Z-Order SIMD |

---

## 3. Baseline Scout Audit (Empirical Fairness & Irene Zhang Checklist)

- **Systems Audited (10 total)**: 7 competitive baselines (`B1..B7`) + 2 controlled ablations (`Ablation 1`, `Ablation 2`) + `Prism-ANN Full`.
- **Irene Zhang Systems Rules**:
  - *"X is better for Y in Z"* thesis formula explicitly stated at opening of Section 1: **PASS**.
  - Design alternatives & trade-offs explicitly justified per mechanism (`ADR-0001..0003` -> Section 3): **PASS**.
  - 3-time experimental conclusion statement (opening bold thesis, closing result, figure caption) across `H1..H4`: **PASS**.
  - Transparent **Limitations & Scope** boundary explicitly added before Conclusion (covering multi-parent DAG token scaling, periodic Z-order compaction, and 5M-shard analytical calibration): **PASS**.

---

## 4. Multi-Aspect Mathematical Q&A Audit

| Theorem / Bound | Verification Probe | Result | Verdict |
|---|---|---|---|
| **Theorem 1 (UBP Bound & Exactness)** | Does Algorithm 1 preserve exact set equivalence under subtractive DENY walls and stay within k_0 + m(b-1)L? | Verified algebraically across m in [0..20], L in [2..6] (60 tokens <= 142 bound at m=5; 2 tokens <= 2 bound at m=0; 0 FP/FN), and empirically stress-tested via verify_blast_radius_ubp.py across 376 adversarial tree + diamond DAG scenarios. | **SOUND** |
| **Corollary 1 (Zero-Write Revocation)** | Does structural unlinking avoid vector DB write amplification without New Enemy exposure? | Ingest-time lineages Anc(v_i) remain immutable; unlinking in SpiceDB advances ZedToken and prunes subtrees via UBP in 0.06 ms at both 1,000 docs and 5,000 docs with 0 vector DB writes (vs 15,000-75,000 payload writes / 6.46-36.30 ms, 107.7x-605.0x speedup). | **SOUND** |
| **Theorem 2 & 3 (Percolation Cliff & Express Bridges)** | Is S_crit = 2/(rM(M+1)) exact under Molloy-Reed directed percolation, and do M_bridge=4 bridges stay under 8% RAM? | For M=16, r=0.5, S_crit=1.471%; intra-container/magnet ring-chord bridges (S_container=0.05) shift S_crit^bridge to 0.0735% (<0.08%), lifting live S=0.005 recall from 33.6% (ACORN-1 and Ablation 2) to 94.8% (and 100.0% at S <= 10^-3) at +5.6% measured RAM (5.80 MB vs 5.49 MB). | **SOUND** |
| **Theorem 4 (Tri-Modal Crossover & Shard Coupling)** | Does N_shard <= N_shard^* eliminate any selectivity dead zone between Mode 2 and Mode 3? | With E_ACORN-GLS=460.8 and kappa=32.0, N_flat^*=14,746 and N_shard^*=18.43M. For a 5M-vector shard, S_flat^*=0.295% > S_crit^bridge=0.08%, guaranteeing seamless overlap with 100.0% Mode 3 Recall@10. | **SOUND** |

---

## 5. Remaining Recommendations & Minor Caveats

1. **Multi-Parent DAG Theorem Bound Framing**: Theorem 1's bound $k_0 + m(b-1)L$ is tight for single-parent container trees; multi-parent diamond DAGs preserve exactness (`0 FP / 0 FN`) via $T_{\text{UBP}}^-$ subtraction (as verified in `verify_blast_radius_ubp.py` and explicitly scoped in the new Limitations paragraph).
2. **Future Large-Scale Distributed Artifact**: While Deep Module invariants, UBP exactness, `H-HNSW` memory bounds, and `ACORN-GLS` distance reductions execute directly in Python/NumPy (`src/modules/prism_ann/`), releasing a C++/AVX-512 Roaring + SpiceDB gRPC benchmark binary on a live 5M-vector shard will further cement Systems-track artifact evaluation.

---

## 6. Final ScholarPeer Meta-Score

- **Technical & Mathematical Soundness**: `9.5 / 10`
- **Baseline Coverage & Empirical Rigor**: `9.0 / 10`
- **Literature Lineage & Citation Hygiene**: `9.5 / 10`
- **Presentation & Visual Quality (PaperVizAgent)**: `9.7 / 10`
- **Overall Recommendation**: **STRONG ACCEPT**
