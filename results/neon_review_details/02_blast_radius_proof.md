# Detail Report 02: Blast Radius Safety Proof — Live `ENH-0010` Build

**Reviewer**: `@neon-reviewer` (`blast-radius` skill)  
**Proof Script**: `verify_blast_radius_ubp.py`  
**Verification Level Achieved**: **Step 4 ("You ran it")** + **Three-Hops-Downstream End-to-End Execution**

---

## 1. The Single Safety Fact `Prism-ANN` Depends On

> **Safety Invariant (`ADR-0001` / Theorem 1 & Corollary 1):**  
> Even after `@hydrogen-builder`'s upgrade of `upward_boundary_prune()` (`src/modules/prism_ann/ubp_resolver.py:257-281`) from $\Theta(b^L)$ downward descendant materialization to an $O(m \cdot L^2)$ upward ancestor taint walk, compiling the Roaring Bitmap via:
> $$B_{\text{acl}}(u) = \Big(\bigcup_{t \in T_{\text{UBP}}^+(u)} B_t\Big) \setminus \Big(\bigcup_{z \in T_{\text{UBP}}^-(u)} B_z\Big)$$
> remains **100% set-identical** to exhaustive leaf `LookupResources` ($\bigcup_{r \in D_{\text{auth}}(u)} B_r$) across both balanced trees and multi-parent diamond DAGs (**0 false positives / 0 data leaks** and **0 false negatives**), and downstream `PrismANNIndex.search()` never leaks any denied document.

---

## 2. Blast Radius Inspection of the Upgraded $O(m \cdot L^2)$ Resolver

1. **Tainted Set Equivalence (`ubp_resolver.py:257-264`)**:
   - Checked whether `(z_anc | {z}) & g0_pos` and `(self.get_strict_ancestors(anc) | {anc}) & g0_pos` are mathematically equivalent to the prior `z in pos_descendants` / `anc in pos_descendants` checks across arbitrary acyclic DAGs.
   - Because $y \in \operatorname{Desc}(S) \iff (\operatorname{StrictAnc}(y) \cup \{y\}) \cap S \neq \emptyset$ in any DAG, the upward check produces the exact same `g_taint` set without touching $\Theta(b^L)$ nodes.
2. **Denied Branch Termination (`ubp_resolver.py:278-280`)**:
   - `if curr in v_neg or (self.get_strict_ancestors(curr) & v_neg):` checks $\operatorname{Desc}(V^-(u))$ strictly by upward ancestors, preventing any subtree rooted under `v_neg` from entering `tokens_pos`.
3. **Downstream `hnsw_gls.py` Search Safety (`hnsw_gls.py:233-257, 326-405`)**:
   - Checked the new `entry_seeds` (`50` portals), `_select_upper_layer_entry`, `TELEPORT` fallback, and new `search_pgvector_iterative` (`hnsw_gls.py:518-578`):
     - `_evaluate_candidates` inserts into `results_map` strictly when `if mask[nid]:`.
     - `search_pgvector_iterative` inserts into `results_map` strictly when `if mask[nb_int]:` (both `entry_0` and loop neighbors).
     - `entry_seeds` (`entry_0` from upper layer) passes `authorized_only=False` for graph traversal queuing while gating `results_map` on `if mask[nid]:`, so unauthorized entry nodes are never returned in `top_k_ids`.

---

## 3. Executed Proof Transcript (`python3 verify_blast_radius_ubp.py`)

```text
==================================================================
  Blast Radius Live Proof: UBP Zero-Leakage & Set Equivalence     
==================================================================
  [PASS] Adversarial Edge-Case Suite: 9 cases -> 0 FP, 0 FN
  [PASS] Balanced Hierarchy Trees: 150 randomized trials -> 0 FP, 0 FN, 100% Theorem 1 bound satisfied
  [PASS] Multi-Parent Diamond DAGs: 100 randomized trials -> 0 FP, 0 FN
  [PASS] Dynamic Post-Revocation Checks: 100 mutations -> 0 FP, 0 FN
  [PASS] Downstream PrismANNIndex.search() E2E (Modes 1/2/3 + Post-Revoke): 17 queries -> 0 leaks
------------------------------------------------------------------
  TOTAL ADVERSARIAL SCENARIOS PROVEN: 376 | FALSE POSITIVES: 0 | FALSE NEGATIVES: 0
==================================================================
```
