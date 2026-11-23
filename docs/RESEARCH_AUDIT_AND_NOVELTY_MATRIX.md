# Prism-ANN Research Audit, Theoretical Review, & Literature Novelty Matrix (`v3.2`)

> **Three-Audience Documentation Set:**
> - **New-Grad / Associate Engineer:** [`ONBOARDING_NEW_GRAD.md`](ONBOARDING_NEW_GRAD.md) (RAG & HNSW basics, analogies, end-to-end query trace).
> - **Senior Engineer / Architect:** [`ARCHITECTURE_SENIOR_ENGINEER.md`](ARCHITECTURE_SENIOR_ENGINEER.md) (CSR/Z-order layout, C++17 & NEON kernels, `ZedToken` snapshots, delta ingestion/compaction).
> - **Researcher / Reviewer (this document):** Formal theorem-by-theorem audit (Findings A–F), full FANNS/ReBAC novelty matrix (`RACORN`, `EMA`, `Curator`, etc.), additive `v3.2` empirical tables (`R6`–`R8`), and manuscript change map.

**Primary Evidence Sources:**
- **Formal Paper:** [`paper/prism_ann.tex`](../paper/prism_ann.tex) → [`prism_ann_paper.pdf`](../prism_ann_paper.pdf) (`12` pages)
- **Frozen Confirmatory (`v3-confirmatory-001`, commit `41868bb`, `169,810` records):** [`results/v3/summary.json`](../results/v3/summary.json) (`11/11` `SUPPORTED`)
- **First-Round Audit (`v3.1`, commit `e39260a`, `22,533` records):** [`results/v3/reviewer_audit_v3_1.json`](../results/v3/reviewer_audit_v3_1.json) (`5/5` `PR1`–`PR5` `SUPPORTED`)
- **Second-Round Audit (`v3.2`, commit `a435bab`, `6,821` records):** [`results/v3/reviewer_audit_v3_2.json`](../results/v3/reviewer_audit_v3_2.json) (`PR6: SUPPORTED`; `PR7` & `PR8`: honestly `FALSIFIED` on strict fragmented-depth-5 latency cutoffs, while confirming `0` leaks and exact/empirical recall behavior)

---

## Part I — Theorem-by-Theorem Mathematical Audit (Findings A–E)

### 1. Finding A — Splitting Theorem 1 into Theorem 1A (Tree Bound) and Theorem 1B (Multi-Parent DAG Exactness)

In the earlier draft (`v3.1`), Theorem 1 combined the cardinality compression bound $|T_{\mathrm{UBP}}^+(u)| \le k_0 + m(b-1)L$ and exact set equivalence on multi-parent DAGs inside one theorem block, with only a prose scope note explaining DAG generalizations. To eliminate any ambiguity between tree assumptions and multi-parent DAG guarantees, the revised manuscript splits Theorem 1 cleanly into:

#### **Theorem 1A (Single-Parent Tree Token Compression Bound)**
- **Assumptions:** $\mathcal{G}_{\mathrm{auth}} = (U \cup G \cup R, E^+ \cup E^-)$ has a **single-parent rooted tree** hierarchy over $G \cup R$ of maximum depth $L$ and maximum branching factor $b$; principal $u$ holds $k_0 = |G_0^+(u)|$ minimal positive root grants and $m = |V^-(u)|$ explicit `DENY` / revoked-subtree exclusions.
- **Claim:** Algorithm 1 ($\mathcal{P}_{\mathrm{UBP}}$) emits positive tokens $T_{\mathrm{UBP}}^+(u)$ satisfying
  $$|T_{\mathrm{UBP}}^+(u)| \le k_0 + m \cdot (b - 1) \cdot L.$$
- **Proof Summary & Tightness:**
  - Base case ($m=0$): $G_{\mathrm{taint}}(u) = \emptyset$, so Algorithm 1 halts on $G_0^+(u)$ with $|T_{\mathrm{UBP}}^+(u)| = k_0$.
  - Inductive step ($m \ge 1$): In a single-parent tree, each denied/unlinked node $z \in V^-(u)$ at depth $\le L$ has a unique path to the root, contributing at most $L$ strict ancestors intersecting $\operatorname{Desc}(G_0^+(u))$, so $|G_{\mathrm{taint}}(u)| \le mL$. Expanding one tainted container $x \in G_{\mathrm{taint}}(u)$ pops $1$ node and considers at most $b$ children, at least one of which lies on the path to $z$ (either tainted or in $D^-(u)$) and is therefore **not** emitted into $T_{\mathrm{UBP}}^+(u)$, adding at most $(b-1)$ net tokens. Summing over $\le mL$ expansions gives $k_0 + m(b-1)L$.
  - **Tightness:** Achieved when $k_0 = 1$ root grant is split along $m$ disjoint root-to-leaf paths sharing only the root, yielding $1 + m(b-1)L - (m-1) = \Theta(m b L)$ while still collapsing $\Theta(b^L)$ leaf documents exponentially.
  - **Scope Limitation:** On an arbitrary **multi-parent DAG** with shared diamond parents, a denied node $z$ has $\ge 1$ parent path, so $|G_{\mathrm{taint}}(u)|$ can exceed $mL$; thus Theorem 1A's cardinality formula strictly requires the single-parent tree assumption, whereas exactness (Theorem 1B) holds unconditionally on multi-parent DAGs.

#### **Theorem 1B (Multi-Parent DAG Exact Set Equivalence under Deny-Dominates-Grant Precedence)**
- **Assumptions:** Let $\mathcal{G}_{\mathrm{auth}} = (U \cup G \cup R, E^+ \cup E^-)$ be **any finite acyclic graph (multi-parent DAG)** under Zanzibar *deny-dominates-grant* precedence:
  $$r \in D_{\mathrm{auth}}(u, \zeta) \iff \big(\exists g \in G^+(u): g \in \operatorname{Anc}(r)\big) \;\land\; \big(\neg \exists d \in V^-(u): d \in \operatorname{Anc}(r)\big),$$
  where $\operatorname{Anc}(r)$ is the transitive ancestor set of leaf $r$ in $\mathcal{G}_{\mathrm{auth}}$, and every node $v \in G \cup R$ maintains its inverted descendant chunk posting bitmap $B_v = \{i \in \{1,\dots,N\} : v \in \operatorname{Anc}(r(v_i))\}$ (where `v ∈ Anc(r)` is invariant on static edges and dynamically masked by $\operatorname{RevokedSubtrees}$ in `V^-(u)`).
- **Claim:**
  $$B_{\mathrm{acl}}(u) := \Big(\bigcup_{t \in T_{\mathrm{UBP}}^+(u)} B_t\Big) \setminus \Big(\bigcup_{z \in T_{\mathrm{UBP}}^-(u)} B_z\Big) = \bigcup_{r \in D_{\mathrm{auth}}(u, \zeta)} B_r \qquad (0\text{ FP},\; 0\text{ FN}).$$
- **Formal Proof (Why Multi-Parent DAGs Work Without Leakage):**
  1. **Zero False Negatives ($r \in D_{\mathrm{auth}}(u, \zeta) \implies \forall i \in B_r,\; i \in B_{\mathrm{acl}}(u)$):**
     - Since $r \in D_{\mathrm{auth}}(u,\zeta)$, no node in $V^-(u)$ belongs to $\operatorname{Anc}(r)$; hence for all $z \in T_{\mathrm{UBP}}^-(u) = V^-(u) \cup (D^-(u) \cap \text{visited})$, we have $z \notin \operatorname{Anc}(r)$, so $B_r \cap B_z = \emptyset$ and subtraction removes **no** chunk of $r$.
     - Moreover, since $\exists g \in G^+(u)$ with $g \in \operatorname{Anc}(r)$, there exists a directed path $x_0 \to x_1 \to \dots \to x_p = r$ starting from some minimal positive root $x_0 \in G_0^+(u)$. Every vertex $x_s$ on this path lies in $\operatorname{Anc}(r)$ and therefore cannot be in $D^-(u)$ (otherwise some $d \in V^-(u)$ would be an ancestor of $x_s$ and by transitivity an ancestor of $r$, contradicting $r \in D_{\mathrm{auth}}$). Because $r$ is a leaf ($\operatorname{StrictDesc}(r) = \emptyset$), $r \notin G_{\mathrm{taint}}(u)$. Thus there exists a smallest index $j \in \{0,\dots,p\}$ such that $x_j \notin G_{\mathrm{taint}}(u)$ while $x_0, \dots, x_{j-1} \in G_{\mathrm{taint}}(u)$. By induction on $0 \le s < j$, Algorithm 1 reaches and expands $x_s$ and emits $x_j \in T_{\mathrm{UBP}}^+(u)$. Since $x_j \in \operatorname{Anc}(r)$, $B_r \subseteq B_{x_j}$, hence $B_r \subseteq B_{\mathrm{acl}}(u)$.
  2. **Zero False Positives ($i \in B_{\mathrm{acl}}(u) \implies r(v_i) \in D_{\mathrm{auth}}(u, \zeta)$):**
     - Let $i \in B_t$ for some $t \in T_{\mathrm{UBP}}^+(u)$ and $r = r(v_i)$. Since $t$ is emitted by BFS seeded at $G_0^+(u)$, $\exists g \in G_0^+(u)$ with $g \in \operatorname{Anc}(t) \subseteq \operatorname{Anc}(r)$, establishing positive reachability.
     - Suppose toward contradiction that $r \notin D_{\mathrm{auth}}(u,\zeta)$, i.e., $\exists d \in V^-(u)$ such that $d \in \operatorname{Anc}(r)$. Since both $t, d \in \operatorname{Anc}(r)$, three acyclic topological cases exist in the sub-DAG $\operatorname{Anc}(r)$:
       - *Case (i) $t = d$ or $t \in \operatorname{Desc}(d)$:* Then $t \in D^-(u)$, contradicting Algorithm 1 Line 10 (which excises $D^-(u)$ rather than emitting to $T_{\mathrm{UBP}}^+$).
       - *Case (ii) $d \in \operatorname{StrictDesc}(t)$:* Since $t$ is reachable from $G_0^+(u)$, $d \in \operatorname{Desc}(G_0^+(u)) \cap \operatorname{StrictDesc}(t)$, so $t \in G_{\mathrm{taint}}(u)$ by Definition 2—contradicting $t \notin G_{\mathrm{taint}}(u)$ when Algorithm 1 emitted $t$.
       - *Case (iii) $t$ and $d$ lie on incomparable multi-parent branches joining above or at $r$:* Because $d \in \operatorname{Anc}(r)$, the invariant $B_d = \{j : d \in \operatorname{Anc}(r(v_j))\}$ guarantees $i \in B_d$. Since $V^-(u) \subseteq T_{\mathrm{UBP}}^-(u)$, $B_d$ is explicitly subtracted in $B_{\mathrm{acl}}(u)$, yielding $i \notin B_{\mathrm{acl}}(u)$—contradiction. (This Case (iii) diamond-parent cancellation is why posting bitmaps *must* index all transitive DAG ancestors $\operatorname{Anc}(r)$ rather than a single tree prefix!)
- **Empirical Verification (`R1` + `R6`):**
  - `R1` (`10,000` trees + alternating `GRANT ↔ DENY`): `0 / 10,000` mismatches (`100.0%` Theorem 1A bound satisfaction).
  - `R6` (`5,000` randomized multi-parent DAGs with `min_secondary_parents = 672`, `mean_secondary_edges = 1,170.0`, median `20` / max `387` `T_UBP+` tokens): **`0 / 5,000` mismatches (`0` false positives, `0` false negatives)**.

---

### 2. Scoped Corollary 1 ($O(1)$ Edge Mutation vs. $T_{\mathrm{revoke}}$ Lifecycle & Causal Security Boundary)

To satisfy reviewer scrutiny on what is strictly $O(1)$ versus end-to-end propagation latency:
- **Graph & Vector Write Complexity:** Deleting an authorization edge $(p, g)$ covering $D_{\mathrm{rev}}$ documents ($N_{\mathrm{chunks}}$ chunks) performs **$0$ vector-store writes** and **$O(1)$ graph-edge deletion** in SpiceDB relative to $N_{\mathrm{chunks}}$ (as opposed to $\Theta(N_{\mathrm{chunks}})$ heap/HNSW/WAL updates in inline-ACL relational tables like `pgvector` `UPDATE`, measured at `179.4 s` for `153,600` rows in `H4v3`).
- **End-to-End Revocation Latency Decomposition:**
  $$T_{\mathrm{revoke}} = T_{\mathrm{PG\text{-}commit}} + T_{\mathrm{mirror\text{-}prop}} + T_{\mathrm{UBP\text{-}compile}} + T_{\mathrm{atomic\text{-}swap}}.$$
  In `R4a` (persistent PostgreSQL 17 SpiceDB single-edge subtree deletions from `128` to `490,419` chunks), total end-to-end median latency remains flat at **`0.74–1.66 ms`** with `0` vector writes. In `R4b` (`131,072`-chunk live PG17 revocation under 4 concurrent C++ reader threads executing `11,244` queries), Postgres SpiceDB `DeleteRelationships` commits in **`6.82 ms`** (`T_PG-commit`) and the in-memory `UBP + CRoaring` atomic snapshot swap completes in **`0.091 ms` (`91 µs`)**.
- **Pre-$\zeta_{\mathrm{rev}}$ vs. Post-$\zeta_{\mathrm{rev}}$ Security Boundary:**
  - *Before swap ($t < t_{\mathrm{swap}}$, requests carrying $\zeta < \zeta_{\mathrm{rev}}$ or already in-flight at cutoff):* `4` in-flight queries crossed `t_swap` on an immutable `zeta=1` `CRoaring`/epoch snapshot without torn reads or crashes (bounded staleness equal to the causal propagation window).
  - *After swap ($\zeta \ge \zeta_{\mathrm{rev}}$):* Every newly issued query binds to the post-revocation `ZedToken`; across `6,039` post-swap queries in `R4b`, **`0 / 6,039` leaked any revoked chunk** (`0` started after `t_swap` on `zeta=1`).

---

### 3. Finding B — Five-Level Exact vs. Empirical Recall Taxonomy (`Propositions 2–4` & `R8`)

The paper now distinguishes mathematically guaranteed exactness from empirically observed `100.00%` recall across all five operating regimes:

| Level | Regime / Kernel | Guarantee Type | Exact Condition | Empirical Evidence (`v3`, `v3.1`, `v3.2`) |
| :---: | :--- | :--- | :--- | :--- |
| **L1** | Auth Set Compilation $B_{\mathrm{acl}}(u)$ | **Mathematical Exactness** (Thm 1B) | Always ($0$ FP, $0$ FN vs.\ `LookupResources`) | `0/1,200` (`H1`), `0/10,000` (`R1`), `0/5,000` (`R6`), `0/1,500` (`R7`) |
| **L2** | Mode 3 Exact `FP32` (`prism_mode3_scan_ranges_f32`) | **Mathematical Top-$k$ Exactness** | Exact IP over all $N_{\mathrm{cand}}$ authorized IDs (`0` extra vector RAM) | `100.00%` R@10 across $S \in \{0.01\%, 0.1\%, 0.5\%, 1.0\%\}$ (`R7`/`R8`, `0.0035–0.453 ms`) |
| **L3** | Mode 3 `SQ8` + Top-$M_{\mathrm{rerank}}$ `FP32` when $N_{\mathrm{cand}} \le M_{\mathrm{rerank}}$ | **Mathematical Top-$k$ Exactness** | All $N_{\mathrm{cand}}$ candidates pass into exact `FP32` reranker | `100.0%` of queries at $S=0.01\%$ (`n_cand_max = 48 <= 64`, `R8`) |
| **L4** | Mode 3 `SQ8` + Top-$64$ `FP32` when $N_{\mathrm{cand}} > 64$ ($0.1\% \le S \le 1\%$) | **Empirical High-Probability** | Top-10 true neighbors remain inside top-64 `SQ8` shortlist | `100.00%` R@10 across Quora, NQ (`H2`), `R8` (`M_rerank >= 32` hits `100.0%`; `M=10` drops to `97.0%–98.0%`) |
| **L5** | Graph-only `v3-geom-M8` & Hybrid at $S > \tau_{\mathrm{guard}}$ (`5%`) | **Approximate ANN** | `efSearch`-bounded HNSW + RNG bridge navigation | `66.6%–86.0%` (`H2`), `85.7%–92.3%` (`R2`), `71.4%–87.4%` (`R7` frag. L5), `93.0%–95.3%` (`S=5%`) |

---

## Part II — Comprehensive Literature & Novelty Matrix + `v3.2` Empirical Tables

### 1. Novelty Comparison vs. 2024–Nov 2026 FANNS & Authorization Literature

| System / Paper | Venue / Date | Access / Filter Model | Subtractive `DENY` (`but not`) | Pre-Filter Cost vs. Leaves $b^L$ | Low-$S$ Strategy | Graph Extra RAM (excl. Vectors) | Total Extra RAM (w/ Aux Copy) | Dynamic Revocation Cost |
| :--- | :--- | :--- | :---: | :---: | :--- | :---: | :---: | :--- |
| **Zanzibar / SpiceDB** | USENIX ATC '19 | Hierarchical ReBAC DAG | **Yes** | $\Theta(b^L)$ `LookupResources` (`79–98 ms`) | External to ANN | Auth graph only | Auth graph only | $O(1)$ graph delete (`0` vec writes) |
| **Filtered-DiskANN** | WWW '23 | Flat label equality | No | $O(1)$ flat label | Label-stitched Vamana | $+25\%$--$40\%$ | $+25\%$--$40\%$ | $O(N_{\text{chunks}})$ graph edits |
| **SeRF / UNIFY** | SIGMOD / VLDB '24 | 1D numeric range $[a,b]$ | No | $O(1)$ range interval | Compressed segment HNSW | $+80\%$--$140\%$ | $+80\%$--$140\%$ | N/A (1D immutable attribute) |
| **ACORN-1 / ACORN-$\gamma$** | SIGMOD '24 | Arbitrary predicate map | External only | $O(N)$ bitset/byte map | 2-hop / $\gamma$-expanded L0 (`M_beta`) | `0` (`ACORN-1`) / $+224\text{ B/n}$ (`γ=4`) | $+224\text{ B/n}$ (`γ=4`) | External map or index rebuild |
| **UNG / SIEVE** | SIGMOD '24 / VLDB '25 | Static label set / Hasse DAG | No | Static label lattice | Label-navigable / workload sub-indexes | Moderate--$2\times$ | Moderate--$2\times$ | Offline rebuild |
| **FANNBench** | VLDB '25 (`arXiv:2507.21989`) | Evaluation framework ($r=S_{\text{loc}}/S$) | No (taxonomy) | Benchmark framework | Benchmarks correlation $r$ | N/A | N/A | N/A |
| **HoneyBee** | arXiv '25 (`2505.01538`) | Flat Role-Based (RBAC) | No (monotonic) | $O(|\text{Roles}|)$ | Role-partitioned sub-indexes | Replicated sub-indexes | Replicated sub-indexes | Partition updates |
| **Policy-Aware Vector Search** | SeQureDB '26 (`2606.19803`) | Fine-Grained AC Vision | Conceptual | Position paper | Identifies FGAC trilemma | N/A | N/A | N/A |
| **Curator** | SIGMOD '26 (`2601.01291`) | Low-selectivity tenant/tag | No | Per-tenant prefix/bitset | Shared-graph tenant routing trees | Per-tenant tree metadata | Per-tenant tree metadata | Per-document tenant bit update |
| **EMA** | Nov '26 (`arXiv:2606.00734v2`) | General attributes + dynamic updates | External predicate | Dynamic attribute map | Dynamic multi-granularity maintenance | Attribute-index metadata | Attribute-index metadata | Incremental node/attribute update |
| **RACORN** | Nov '26 (`arXiv:2607.00768v2`) | Predicate-agnostic ($S \ll 1\%$) | External predicate | $O(N)$ byte/bitmap | Fallback to rejected 1-hop neighbors | `0` (`RACORN-1`) | `0` (`RACORN-1`) | External bitmap only |
| **Prism-ANN v3 (`v3-geom-M8` / `-f32`)** | **This Work** | **Hierarchical ReBAC $\times$ Ontology** | **Yes ($\mathcal{P}_{\text{UBP}}$ Cut)** | **$\le k_0 + m(b-1)L$ (Thm 1A)** | **Container+Magnet Bridges + GLS / FP32 Scan** | **`+32 B/n` (`+1.91%`)** | **`+32 B/n` (`+1.91%`, `0` vec copy)** | **$0$ vec writes ($O(1)$ edge)** |
| **Prism-ANN v3 (`v3-full-guard-sq8`)** | **This Work** | **Hierarchical ReBAC $\times$ Ontology** | **Yes ($\mathcal{P}_{\text{UBP}}$ Cut)** | **$\le k_0 + m(b-1)L$ (Thm 1A)** | **Bridges + GLS + NEON SQ8 Guard** | **`+32 B/n` (`+1.91%`)** | **`+416 B/n` (`+24.8%` w/ SQ8)** | **$0$ vec writes ($O(1)$ edge)** |

**Concrete Novelty Differentiation:**
1. **Vs. `RACORN` (`arXiv:2607.00768v2`):** `RACORN` fixes `ACORN-1`'s zero-degree frontier collapse when $S \ll 1\%$ by allowing traversal through rejected neighbors without expanding memory overhead, **assuming predicates live in an already-materialized bitset**. On hierarchical ReBAC, `RACORN` neither compresses $\Theta(b^L)$ SpiceDB `LookupResources` enumeration (`79–98 ms` in `Track 2`) nor injects semantic container/magnet express shortcuts (`v3-geom-M8` beats `racorn-1-fallback` by `+28.0` to `+81.4` Recall@10 pts across $S \in [0.01\%, 1.0\%]$ in `R7`).
2. **Vs. `EMA` (`arXiv:2606.00734v2`):** `EMA` targets general attribute filtering with dynamic vector/attribute mutations, updating inline attribute structures per mutated document. `Prism-ANN` targets hierarchical ReBAC with subtractive `DENY`s where container-level revocations would otherwise rewrite $\Theta(N_{\text{chunks}})$ attribute indexes, achieving $0$ index writes via $\mathcal{P}_{\text{UBP}}$ and dynamic Z-order delta compaction (`R4`, `R5`).
3. **Vs. `Curator` (`SIGMOD 2026`):** `Curator` embeds per-tenant prefix routing trees inside a shared index for low-selectivity tenants, whereas `Prism-ANN` handles arbitrary multi-level Zanzibar DAG hierarchies with subtractive exclusions (`Theorem 1B`), Meaning Magnet cross-cuts, and Z-order `CRoaring` NEON range scanning.

---

### 2. Second-Round Additive Benchmark Results (`v3.2`, `6,821` Records, Commit `a435bab`)

#### `R6` — Multi-Parent DAG Fuzzing (`PR6: SUPPORTED`)
| Topology | DAG Trials | Min / Mean Secondary Edges | Mismatches vs.\ Oracle | Median / Max `\|T_UBP+\|` | Verdict |
| :---: | :---: | :---: | :---: | :---: | :---: |
| `(b=4, L=5)` | `1,667` | — | **`0`** | — | Verified |
| `(b=6, L=4)` | `1,666` | — | **`0`** | — | Verified |
| `(b=8, L=4)` | `1,667` | — | **`0`** | — | Verified |
| **Total Combined** | **`5,000`** | **`672` / `1,170.0`** | **`0 / 5,000` (`0` FP, `0` FN)** | **`20.0` / `387`** | **`PR6: SUPPORTED`** |

#### `R7` — Two-Track Fair Benchmark + `RACORN-1` & Zero-RAM `FP32` (`PR7: FALSIFIED` on strict `<=0.35 ms` / `>=100x` fragmented-L5 thresholds)
*Full BEIR Quora (`N=522,931`, `L=5, b=8`, `50` queries/cell, `0 / 1,500` total authorization leaks). Track 1 excludes all filter/permission materialization from all systems; Track 2 adds `filter_compile_med_ms` (`~0.74–0.95 ms` FAISS/ACORN, `~2.32–2.39 ms` RACORN byte map, `~0.13–0.54 ms` UBP ranges) + live PG17 `H1v3` SpiceDB `T_auth` (`98.30 ms` `LookupResources` vs.\ `3.49 ms` PG `ReadRelationships+UBP` or `0.35 ms` local mirror `UBP`).*

| Selectivity ($S_{\text{act}}$) | System | R@10 (%) | Evals | Track 1 C++ Med / P95 (ms) | Filter Compile (ms) | Track 2 PG17 Total (ms) | Track 2 Mirror Total (ms) | T2 PG / Mir Speedup vs.\ FAISS |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`0.01%`** (`0.00918%`) | `faiss-hnsw-M16` | `0.8%` | `818.8` | `2.886` / `6.165` | `0.835` | `102.45` | `83.30` | `1.00×` / `1.00×` |
| | `acorn-1` | `0.2%` | `1.7` | `0.774` / `4.433` | `0.759` | `99.88` | `80.73` | `1.03×` / `1.03×` |
| | `racorn-1-fallback` | `6.0%` | `166.1` | `1.429` / `4.380` | `2.320` | `102.07` | `82.92` | `1.00×` / `1.00×` |
| | `v3-geom-M8` (graph) | **`87.4%`** | `161.7` | `0.527` / `3.345` | `0.129` | `4.21` | `1.07` | `24.33×` / `77.51×` |
| | `v3-full-guard-f32` (`0 B/n` vec) | **`100.0%`** | `48.0` | **`0.0206`** / `0.074` | `0.129` | **`3.65`** | **`0.509`** | **`28.07×`** / **`163.75×`** |
| | `v3-full-guard-sq8` | **`100.0%`** | `48.0` | **`0.0380`** / `0.094` | `0.129` | **`3.65`** | **`0.518`** | **`28.07×`** / **`160.68×`** |
| **`0.1%`** (`0.10063%`) | `faiss-hnsw-M16` | `5.4%` | `794.8` | `1.530` / `5.608` | `0.913` | `100.82` | `81.66` | `1.00×` / `1.00×` |
| | `acorn-1` | `0.8%` | `13.6` | `1.461` / `12.179` | `0.752` | `100.70` | `81.55` | `1.00×` / `1.00×` |
| | `racorn-1-fallback` | `15.0%` | `173.6` | `1.110` / `3.875` | `2.346` | `101.80` | `82.64` | `0.99×` / `0.99×` |
| | `v3-geom-M8` (graph) | **`79.2%`** | `351.2` | `0.453` / `2.099` | `0.130` | `4.07` | `0.93` | `24.77×` / `87.48×` |
| | `v3-full-guard-f32` (`0 B/n` vec) | **`100.0%`** | `526.2` | **`0.0440`** / `0.142` | `0.130` | **`3.66`** | **`0.526`** | **`27.55×`** / **`155.31×`** |
| | `v3-full-guard-sq8` | **`100.0%`** | `526.2` | **`0.1026`** / `0.214` | `0.130` | **`3.72`** | **`0.579`** | **`27.10×`** / **`140.99×`** |
| **`0.5%`** (`0.50038%`) | `faiss` / `acorn-1` / `racorn-1` | `24.2` / `23.8` / `35.8%` | — | `0.6938` / `2.2102` / `1.2360` | — | `~100–102` | `~81–83` | `~1.0×` |
| | `v3-geom-M8` / `-f32` / `-sq8` | `71.4%` / **`100%`** / **`100%`** | `587` / `2617` | `0.7421` / `0.2335` / `0.3035` | `0.1793` | `4.42` / `3.89` / `3.96` | `1.2799` / `0.7559` / `0.8269` | `25.70×` (`-f32`) / `106.90×` (`-f32`) |
| **`1.0%`** (`1.00120%`) | `faiss` / `acorn-1` / `racorn-1` | `33.6` / `30.4` / `45.6%` | — | `0.4559` / `2.4896` / `1.2857` | — | `99.62`–`102.09` | `80.46`–`82.93` | `~1.0×` |
| | `v3-geom-M8` / `-f32` / `-sq8` | `73.6%` / **`100%`** / **`100%`** | `777` / `5236` | `0.8751` / `0.4527` / `0.4344` | `0.2060` | `4.57` / `4.13` / `4.12` | `1.4362` / `0.9982` / `0.9790` | `24.18×` (`-sq8`) / `82.19×` (`-sq8`) |
| **`5.0%`** (`4.99832%`) | `faiss` / `acorn-1` / `racorn-1` | `76.6` / `31.2` / `89.0%` | — | `0.4437` / `3.3586` / `1.4544` | — | `99.68`–`102.55` | `80.53`–`83.40` | `~1.0×` |
| | `v3-geom-M8` / `-f32` / `-sq8` | **`93.0%`** (all 3 modes) | `1522.6` | `1.0378` / `0.3118` / `0.2581` | `0.5381` | `5.02` / `4.34` / `4.29` | `1.8805` / `1.2055` / `1.1509` | `23.24×` (`-sq8`) / `69.97×` (`-sq8`) |

- **Why `PR7` Registered as `FALSIFIED` (Important Scientific Finding):** Under fragmented depth-5 `L=5, b=8` overlays (`32,768` leaf docs), `S = 1.0%` fragments into `~328` disjoint folders across multiple L4 branches rather than 5 large L4 folders. Consequently, `v3-full-guard-f32` (`0.4527 ms`) and `v3-full-guard-sq8` (`0.4344 ms`) exceeded the pre-registered `<= 0.35 ms` Track-1 threshold and `Track-2 Mirror` speedup (`82.19x`) came slightly below `100x`, while still achieving **`100.0%` R@10**, **`0` leaks**, **`24.18x` PG17 speedup**, and **`+28.0` to `+81.4` pt higher R@10** for `v3-geom-M8` vs.\ `RACORN-1`. Zero-RAM `v3-full-guard-f32` matches `SQ8` at `100.0%` R@10 and is actually *faster* (`0.0206 ms`, `0.0440 ms`, `0.2335 ms`) than `SQ8` (`0.0380 ms`, `0.1026 ms`, `0.3035 ms`) up through $S = 0.5\%$!

#### `R8` — Exact vs.\ Empirical Recall Shortlist & Zero-RAM `FP32` Parity Audit (`PR8: FALSIFIED` on strict `<=0.25 ms` exact-FP32 cutoff at fragmented `S=1.0%`)
| Selectivity | $N_{\text{cand}}$ Mean / Max | `M=64` Math Guarantee Cov. | `SQ8 M=10` R@10 | `SQ8 M=32` R@10 | `SQ8 M=64` R@10 (Med ms) | `SQ8 M=128` R@10 | `Exact FP32` R@10 (Med ms, `0 B/n` vec) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`0.01%`** | `47.9` / `48` | **`100.0%`** ($N_{\text{cand}} \le 64$) | `97.00%` | `100.00%` | `100.00%` (`0.0057 ms`) | `100.00%` | `100.00%` (**`0.0035 ms`**) |
| **`0.1%`** | `526.7` / `528` | `0.0%` (empirical) | `98.00%` | `100.00%` | `100.00%` (`0.0292 ms`) | `100.00%` | `100.00%` (**`0.0235 ms`**) |
| **`0.5%`** | `2,616.2` / `2,624` | `0.0%` (empirical) | `97.13%` | `100.00%` | `100.00%` (`0.0569 ms`) | `100.00%` | `100.00%` (`0.1964 ms`) |
| **`1.0%`** | `5,234.6` / `5,248` | `0.0%` (empirical) | `97.38%` | `100.00%` | `100.00%` (`0.0780 ms`) | `100.00%` | `100.00%` (`0.3289 ms`) |

- **Design Takeaway (`R8`):** At $S \le 0.1\%$, exact `FP32` Mode 3 (`0.0035–0.0235 ms`) is both **mathematically exact** and faster than `SQ8` while requiring **`0` extra vector RAM**. For $S \in [0.5\%, 1.0\%]$ (`5,235` scattered runs at `L=5`), `SQ8 + M_rerank >= 32` holds `100.00%` empirical R@10 (`4.22×` faster than `FP32` at `S=1%`), whereas `M=10` loses `2.0%–3.0%` recall due to `SQ8` quantization boundary flips.

---

## Part III — Manuscript Change Map (`v3.1` $\to$ `v3.2`)

1. **Abstract & §III-C (`paper/prism_ann.tex`):** Clarified that `100.00%` Recall@10 at $S \le 1\%$ for `v3-full-guard-sq8` is *empirically observed* (mathematically guaranteed whenever $N_{\text{cand}} \le 64$ or via zero-extra-vector-RAM `prism_mode3_scan_ranges_f32`).
2. **Theorem 1 $\to$ Theorem 1 & Theorem 2 (`paper/prism_ann.tex` §III-A):** Separated Single-Parent Tree Token Compression Bound (`Theorem 1`) from Multi-Parent DAG Exact Set Equivalence under Deny-Dominates-Grant Precedence (`Theorem 2`), each with an explicit standalone proof.
3. **Scoped Corollary 1 (`paper/prism_ann.tex` §III-A):** Scoped $0$ vector writes and $O(1)$ authorization-edge mutation relative to $N_{\text{chunks}}$, decomposing end-to-end $T_{\mathrm{revoke}}$ (`6.82 ms` PG17 commit + `0.091 ms` atomic snapshot swap in `R4b`) and separating pre-$\zeta_{\mathrm{rev}}$ vs.\ post-$\zeta_{\mathrm{rev}}$ guarantees.
4. **Section V-G (`sec:eval_audit`):** Adopted explicit `64 MB cache-thrashing sweep` wording in `R3`, and added the `v3.2` (`R6`–`R8`) audit findings (including transparent reporting of fragmented depth-5 `R7` Track 1/Track 2 latencies against `RACORN-1` and `FP32` Mode 3).
5. **Table I, Section VI-B & Bibliography:** Added **`RACORN`** (`arXiv:2607.00768v2`, Nov.\ 2026) and **`EMA`** (`arXiv:2606.00734v2`, Nov.\ 2026) alongside `Curator`, `ACORN`, `HoneyBee`, `FANNBench`, and `SeQureDB '26`.
