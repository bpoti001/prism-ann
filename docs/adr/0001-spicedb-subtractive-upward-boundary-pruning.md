# ADR-0001: Subtractive-Aware Upward Boundary Pruning (UBP) over SpiceDB / Zanzibar ReBAC DAGs

- **Status**: `accepted`
- **Date**: 2026-11-19
- **Scope**: `src/modules/prism_ann/ubp_resolver.py`
- **Mapped Paper Section**: Section 3.1 — Theorem 1 (Token Cardinality Bound) & Corollary 1 (Zero-Write Revocation)

## Context
In an Enterprise Multimodal Knowledge Platform (EMKP), access control is governed by a Google Zanzibar / SpiceDB Relationship-Based Access Control (ReBAC) graph $\mathcal{G}_{\text{auth}} = (U \cup G \cup R, E^+ \cup E^-)$ supporting multi-hop hierarchical inheritance (`org -> lob -> dept -> folder -> doc`) and non-monotonic exclusions (`but not` / `ethical_wall_deny`).
Calling SpiceDB's `LookupResources` API to pre-filter a vector search expands permissions down to leaf documents, generating $\Theta(b^L) \approx 10^4\text{--}10^5$ document IDs and stalling Roaring Bitmap union operations for 50–180 ms. Conversely, stamping resolved user/role ACLs onto vector chunks causes $O(N_{\text{chunks}})$ write amplification on revocation.

## Decision
1. **Ingest-Time Immutable Lineage Stamping**: Stamp every chunk $v_i$ with its immutable structural container lineage $\operatorname{Anc}(v_i) = \{g_0, g_1, \dots, r(v_i)\}$ ($L+1$ tokens). Store all mutable user/group grants ($E^+$) and subtractive exclusions ($E^-$) exclusively in SpiceDB.
2. **Query-Time Subtractive-Aware Upward Boundary Pruning ($\mathcal{P}_{\text{UBP}}$)**: Compute the tainted ancestor set $G_{\text{taint}}(u) = \bigcup_{z \in V^-(u)} (\operatorname{Anc}(z) \cap \operatorname{Desc}(G_0^+(u)))$. Perform top-down traversal from $G_0^+(u)$, halting immediately at any untainted container $x \notin G_{\text{taint}}(u)$ and splitting only tainted containers around denied branches.

## Alternatives Considered (Design-It-Twice)
1. **Alternative A — Naive SpiceDB `LookupResources` Leaf Expansion (Baseline B2)**: Streams all accessible leaf document IDs. Rejected due to $\Theta(b^L)$ disjunction explosion and 50–180 ms bitmap union latency.
2. **Alternative B — `HoneyBee` Static RBAC Overlapping Vector Partitioning (`arXiv:2505.01538`, Baseline B5)**: Replicates vectors across role partitions. Rejected because ReBAC container hierarchies + dynamic `but not` exclusions + orthogonal Ontology filters explode partition combinations ($>6\times$ RAM) and require re-indexing on ACL mutations.
3. **Alternative C — Post-Filter via SpiceDB `CheckBulkPermissions` (Baseline B1)**: Rejected due to catastrophic recall collapse ($<5\%$ Recall@10) when user selectivity $S < 0.05$.

## Mapped Paper Theorem & Bound
**Theorem 1 (UBP Token Compression Bound):** For $k_0$ top-level grants and $m = |V^-(u)|$ explicit `DENY` rules in a hierarchy of branching factor $b$ and depth $L$:
$$|T_{\text{UBP}}^+(u)| \le k_0 + m \cdot (b - 1) \cdot L$$
with exact set equivalence $\bigcup_{t \in T_{\text{UBP}}^+(u)} B_t = \bigcup_{r \in D_{\text{auth}}(u)} B_r$ and $O(1)$ zero-write document revocation.

## Deep Module Seam
`src/modules/prism_ann/ubp_resolver.py` -> `resolve_ubp_tokens(auth_graph, principal_id) -> Tuple[Set[str], Set[str]]`.

## Consequences
- **Positive**: Compresses $10^4+$ leaf tokens to $\le 50$ structural tokens ($18\times$ faster pre-filter compilation) and enables $O(1)$ zero-write document revocation.
- **Negative**: Adds $L+1$ (typically 4–6) immutable ancestor token postings per chunk in the inverted bitmap index.
- **Reversibility**: `Two-Way Door`.
