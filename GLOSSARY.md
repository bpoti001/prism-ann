# Ubiquitous Domain Language & Mathematical Symbol Table (`GLOSSARY.md`)

> **Rule (`domain-modeling` + `systems-paper-writing`):**
> Every domain concept, code identifier, and LaTeX symbol must adhere strictly to this glossary so that code implementations (`src/modules/prism_ann/`) and manuscript equations (`paper/`) maintain $1:1$ formal correspondence.

---

## 1. Domain Concepts (EMKP + SpiceDB + Filtered HNSW)

| Canonical Term | Definition | Code Identifier | Avoid (Ambiguous Synonyms) |
|---|---|---|---|
| **Capability Lineage Path** | Immutable sequence of structural container ancestors from organization root to leaf document stamped on chunk $v_i$ at ingest. | `ancestor_lineage` / `Anc(v_i)` | folder tags, flat role list |
| **Meaning Magnet** | High-gravity canonical Ontology concept node ($m_k \in \mathcal{T}_{\text{ont}}$) that gravitationally binds surface jargon chunks during Silver-to-Gold ingestion. | `meaning_magnet_ids` / `tau(v_i)` | category, keyword tag |
| **Tainted Ancestor Set** | Set of structural containers lying on a directed path from a positively granted root $g \in G_0^+(u)$ to an explicit subtractive (`but not` / `DENY`) node $z \in V^-(u)$. | `tainted_containers` / `G_taint` | blocked folders, dirty nodes |
| **Subtractive-Aware Upward Boundary Pruning (UBP)** | Top-down Zanzibar graph cut algorithm that halts at untainted containers and recursively splits only tainted ancestors around denied subtrees. | `upward_boundary_prune()` / `P_UBP` | tree truncation, prefix filter |
| **Ancestor-Stitched Express Bridges** | $M_{\text{bridge}}$ supplementary long-range HNSW base-layer edges connecting nodes that share a structural container or Meaning Magnet. | `express_bridges` / `M_bridge` | secondary index, payload links |
| **Instantaneous Local Selectivity** | Fraction of a visited node $v$'s 1-hop HNSW neighbors satisfying the composite Roaring Bitmap $B_\Phi$, computed via bitwise `AND` + `POPCNT`. | `local_selectivity_hat` / `S_loc_hat(v)` | node filter ratio |

---

## 2. 1:1 Code-to-LaTeX Mathematical Symbol Table

| Symbol (LaTeX) | Meaning | Python Variable | Typical Range / Units |
|---|---|---|---|
| $\mathcal{C} = \{v_1, \dots, v_N\} \subset \mathbb{R}^d$ | Sharded vector corpus of $N$ document chunks | `corpus_vectors` (`N`, `d`) | $N \le 5 \times 10^6$ per shard, $d \in [96, 1536]$ |
| $\mathcal{G}_{\text{auth}} = (U \cup G \cup R, E^+ \cup E^-)$ | SpiceDB / Zanzibar authorization graph | `auth_graph` | Depth $L \in [2, 6]$, branching $b \in [4, 16]$ |
| $\mathcal{T}_{\text{ont}} = (C, E_{\text{ont}})$ | Ontological Meaning Magnet DAG | `ontology_dag` | $|C| \in [256, 4096]$, Zipf $\alpha = 1.2$ |
| $k_0, m$ | Count of top-level positive grants ($k_0$) and explicit `DENY` walls ($m$) for principal $u$ | `k0_grants`, `m_denies` | $k_0 \in [1, 10], m \in [0, 25]$ |
| $(T_{\text{UBP}}^+(u), T_{\text{UBP}}^-(u))$ | Pruned positive and subtractive capability token sets | `tokens_pos`, `tokens_neg` | $|T_{\text{UBP}}^+| \le k_0 + m(b-1)L \le 50$ |
| $B_\Phi = (B_{\text{ont}} \cap B_{\text{acl}}^+) \setminus B_{\text{acl}}^-$ | Composite authorized candidate Roaring Bitmap | `bitmap_phi` | $N_{\text{cand}} = \operatorname{popcount}(B_\Phi)$ |
| $S = N_{\text{cand}} / N$ | Global predicate selectivity | `global_selectivity` (`S`) | $S \in [10^{-4}, 1.0]$ |
| $S_{\text{loc}}, r = S_{\text{loc}} / S$ | Local selectivity around query $q$ and Global-Local Selectivity correlation ratio | `local_selectivity`, `gls_ratio` (`r`) | $r < 1$ (depleted), $r = 1$ (uncorr), $r > 1$ (enriched) |
| $M, M_{\text{bridge}}$ | HNSW base out-degree ($M$) and Ancestor-Stitched Express Bridge count ($M_{\text{bridge}}$) | `m_degree`, `m_bridge` | $M = 16, M_{\text{bridge}} = 4$ |
| $\kappa = c_{\text{rand}} / c_{\text{simd}}$ | Latency ratio of random DRAM graph hop to Z-ordered sequential SIMD distance evaluation | `hardware_kappa` | $\kappa \in [20, 35]$ |
