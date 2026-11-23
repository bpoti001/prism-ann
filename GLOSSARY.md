# Ubiquitous Domain Language & Mathematical Symbol Table (`GLOSSARY.md`)

> **Rule (`domain-modeling` + `systems-paper-writing`):**
> Every domain concept, code identifier, and LaTeX symbol must adhere strictly to this glossary so that code implementations (`src/modules/prism_ann/`, `bench/prism_ckernel.cpp`, `bench/prism_audit_kernel.cpp`) and manuscript equations (`paper/prism_ann.tex`) maintain $1:1$ formal correspondence.

---

## 1. Domain Concepts (EMKP + SpiceDB + Filtered HNSW)

| Canonical Term | Definition | Code Identifier | Avoid (Ambiguous Synonyms) |
|---|---|---|---|
| **Capability Lineage Path** | Immutable set/sequence of structural container ancestors from organization root to leaf document stamped on chunk $v_i$ at ingest. | `ancestor_lineage` / `Anc(v_i)` | folder tags, flat role list |
| **Meaning Magnet** | High-gravity canonical Ontology concept node ($m_k \in \mathcal{T}_{\text{ont}}$) that gravitationally binds surface jargon chunks during ingestion. | `meaning_magnet_ids` / `tau(v_i)` | category, keyword tag |
| **Tainted Ancestor Set** | Set of structural containers lying on any directed path from a positively granted root $g \in G_0^+(u)$ to an explicit subtractive (`but not` / `DENY`) node $z \in V^-(u)$. | `tainted_containers` / `G_taint` | blocked folders, dirty nodes |
| **Subtractive-Aware Upward Boundary Pruning (UBP)** | Top-down Zanzibar graph cut algorithm that halts at untainted containers and recursively splits only tainted ancestors around denied subtrees under Deny-Dominates-Grant precedence. | `upward_boundary_prune()` / `P_UBP` | tree truncation, prefix filter |
| **Geometric Ancestor-Stitched Express Bridges** | $M_{\text{bridge}}=8$ supplementary Vamana/RNG-pruned long-range HNSW base-layer edges connecting semantic nearest neighbors that share a structural container or Meaning Magnet. | `express_bridges` / `M_bridge` | secondary index, payload links |
| **Instantaneous Local Selectivity** | Fraction of a visited node $v$'s 1-hop HNSW neighbors satisfying the composite Roaring Bitmap $B_\Phi$, computed via bitwise `AND` + `POPCNT`. | `local_selectivity_hat` / `S_loc_hat(v)` | node filter ratio |
| **Causal Revocation Consistency Token (`ZedToken`)** | Opaque causal snapshot watermark $\zeta_{\text{rev}}$ emitted by SpiceDB on relation-tuple mutation, gating atomic dual-version snapshot visibility in the query planner. | `zed_token` / `zeta_rev` | timestamp, lock epoch |

---

## 2. 1:1 Code-to-LaTeX Mathematical Symbol Table

| Symbol (LaTeX) | Meaning | Python / C++ Variable | Typical Range / Units |
|---|---|---|---|
| $\mathcal{C} = \{v_1, \dots, v_N\} \subset \mathbb{R}^d$ | Sharded vector corpus of $N$ document chunks | `corpus_vectors` (`N`, `d`) | $N \le 5 \times 10^6$ per shard, $d \in [96, 1536]$ (`384` in BEIR Quora/NQ) |
| $\mathcal{G}_{\text{auth}} = (U \cup G \cup R, E^+ \cup E^-)$ | SpiceDB / Zanzibar authorization DAG (tree when $p_{\text{multi}}=0$) | `auth_graph` | Depth $L \in [2, 6]$, branching $b \in [3, 12]$ |
| $\mathcal{T}_{\text{ont}} = (C, E_{\text{ont}})$ | Ontological Meaning Magnet DAG | `ontology_dag` | $|C| \in [64, 4096]$, Zipf $\alpha = 1.2$ |
| $k_0, m$ | Count of top-level positive grants ($k_0$) and explicit `DENY` walls ($m$) for principal $u$ | `k0_grants`, `m_denies` | $k_0 \in [1, 10], m \in [0, 25]$ |
| $(T_{\text{UBP}}^+(u), T_{\text{UBP}}^-(u))$ | Pruned positive and subtractive capability token sets | `tokens_pos`, `tokens_neg` | Tree (Theorem 1): $|T_{\text{UBP}}^+| \le k_0 + m(b-1)L$; DAG (Theorem 2): $\le k_0 + m\bar{p}_{\text{dag}}(b-1)L$ |
| $\bar{p}_{\text{dag}}$ | Mean ancestor-path multiplicity per `DENY` node in a multi-parent ReBAC DAG | `p_dag_multiplicity` | $\bar{p}_{\text{dag}} = 1$ (tree), $\bar{p}_{\text{dag}} \ge 1$ (multi-parent DAG) |
| $B_\Phi = (B_{\text{ont}} \cap B_{\text{acl}}^+) \setminus B_{\text{acl}}^-$ | Composite authorized candidate Roaring Bitmap | `bitmap_phi` | $N_{\text{cand}} = \operatorname{popcount}(B_\Phi)$ |
| $S = N_{\text{cand}} / N$ | Global predicate selectivity | `global_selectivity` (`S`) | $S \in [10^{-4}, 1.0]$ |
| $S_{\text{loc}}, r = S_{\text{loc}} / S$ | Local selectivity around query $q$ and Global-Local Selectivity correlation ratio | `local_selectivity`, `gls_ratio` (`r`) | $r < 1$ (depleted), $r = 1$ (uncorr), $r > 1$ (enriched) |
| $M, M_{\text{bridge}}$ | HNSW base out-degree ($M$) and Geometric Ancestor-Stitched Express Bridge count ($M_{\text{bridge}}$) | `m_degree`, `m_bridge` | $M = 16, M_{\text{bridge}} = 8$ (`+32 B/node`, `+1.91%` graph RAM) |
| $M_{\text{rerank}}$ | Exact FP32 reranking pool size following Mode-3 `SQ8` (`INT8`) ARM NEON scan | `m_rerank` | $M_{\text{rerank}} = \max(4k, 64)$ (exact guarantee whenever $N_{\text{cand}} \le M_{\text{rerank}}$) |
| $\zeta_{\text{rev}}$ | SpiceDB `ZedToken` causal snapshot watermark at permission revocation commit | `zeta_rev` | Monotonic uint64 / opaque token (`0` leaks for queries stamped $\zeta \ge \zeta_{\text{rev}}$) |
| $\kappa = c_{\text{rand}} / c_{\text{simd}}$ | Latency ratio of random DRAM graph hop to Z-ordered sequential SIMD distance evaluation | `hardware_kappa` | $\kappa \in [14, 24]$ (`23.62×` under `64 MB` cache eviction, `14.12×` warm cache) |
