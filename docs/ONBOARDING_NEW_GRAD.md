# Welcome to Prism-ANN: A New-Grad Engineer's Guide

*(Target audience: New graduates and associate engineers familiar with basic data structures, SQL, and REST/gRPC APIs — no prior background in HNSW graphs, Google Zanzibar / SpiceDB, or ARM SIMD required.)*

> **Looking for other perspectives in this repo?**
> - **Fresh grad / Associate engineer:** You are here! Pair this reading guide with [`prism_ann_onboarding_explainer.mp4`](../prism_ann_onboarding_explainer.mp4).
> - **Senior systems engineer / Architect:** See [`ARCHITECTURE_SENIOR_ENGINEER.md`](ARCHITECTURE_SENIOR_ENGINEER.md) for CSR memory layouts, C++/NEON kernels, `ZedToken` snapshot swaps, and memory/latency trade-offs.
> - **Researcher / Reviewer:** See [`RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md`](RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md) and [`../paper/prism_ann.tex`](../paper/prism_ann.tex) for formal theorems (`Theorem 1`, `Theorem 2`), raw benchmarks (`v3.0`–`v3.3`), and literature positioning (`Veda`, `RACORN`, `EMA`, `Curator`, `amanbayev2026gls`).

---

## 1. The Real-World Scenario: Enterprise AI Search (RAG) with Permissions

Imagine you just joined a software company with **500,000 internal documents** (architecture specs, engineering RFCs, HR policies, executive memos, payroll sheets).

We are building an internal AI assistant using **RAG (Retrieval-Augmented Generation)**. When an employee types a question such as *"What is our parental leave policy for engineers?"*, the backend does **not** feed all 500,000 documents into an LLM prompt (that would be far too slow and expensive). Instead, search happens in four simple steps:

1. **Chunking:** Long files are split into paragraph-sized pieces called **chunks**.
2. **Embedding:** An AI encoder turns every text chunk into a list of numbers (for example, 384 floats called a **vector embedding**) where similar meanings sit close together in space.
3. **Vector Search:** The user's question is embedded into the same 384-dimensional space, and a **vector index** finds the top $k$ (say, top 10) chunks whose vectors point in the closest direction to the question.
4. **Generation:** Only those top 10 chunks go to the LLM to synthesize the final answer.

### Where Security Enters the Picture
Now suppose **Alice** is an engineer. She is allowed to read:
- `/Company/Public_Handbook/*` (including `Parental_Leave.pdf`),
- `/Company/Engineering/*` (hundreds of folders containing 5,000 design docs),
- **EXCEPT** `/Company/Engineering/Acquisition_Project_Secret` (explicitly denied to her!).

Meanwhile, **Bob** in HR is allowed to read `/Company/HR/Salaries.pdf` — a document that is *very semantically close* to Alice's question about benefits, even though **Alice must never see a single line of it**.

In systems built on **Google Zanzibar / SpiceDB** (**ReBAC** — Relationship-Based Access Control), access flows down an **organizational hierarchy** (an **org chart** or **nested folder tree**: `Organization → Line of Business → Department → Folder → Document`), modified by explicit denials (`but not`, also called **ethical walls**).

Here is the core engineering challenge Prism-ANN solves:
> How do you return the **top 10 most relevant chunks** from a million-vector index quickly, while **never touching or returning a chunk Alice is not authorized to read** — even when she can see only **1% or 0.01%** of the company's documents?

---

## 2. Why Combining Search and Permissions Is Harder Than It Looks (The 3 Traps)

To see why you can't just bolt an authorization API onto an off-the-shelf vector database, let's look at how a vector index like **HNSW** works.

**Everyday Analogy — HNSW as a Highway Map:**
Think of **HNSW (Hierarchical Navigable Small World)** as a multi-layer road network connecting cities (chunks).
- The **top layer** has sparse expressways connecting distant landmarks so a traveler can cross the country in a few hops.
- The **ground layer (Layer 0)** connects each city to its ~16–32 closest semantic neighbors.
To find the closest match for a question, search drops onto a global highway entry city, greedily drives closer and closer to the target neighborhood, and stops after inspecting a fixed budget of street corners (`efSearch`, e.g., 64 stops).

Now watch the three failure modes when Alice asks a question:

### Trap 1: Authorize First, Search Second (**Leaf-Disjunction Explosion**)
*Idea:* Call SpiceDB's `LookupResources` API before vector search to get a list of every document ID Alice can read, build a bitmask over all 500,000 chunks, and hand that mask to the vector index.
- **Why it breaks:** Suppose Alice was granted access to an upper-level Engineering folder (`b = 8` sub-items per level, `L = 4` levels deep -> `4,096` documents, or `60,000+` chunks). Even if her folder tree only had **1 grant** (`Engineering`) and **1 denial**, `LookupResources` has to expand and stream **thousands of leaf document IDs** over gRPC and union their chunk bitmaps *before vector search even starts*.

### Trap 2: Search First, Or Filter During Graph Hops (**Filtered HNSW Graph Collapse**)
*Idea:* Keep permissions checked at each intersection inside the HNSW road map.
- **Why it breaks ("Getting Stranded"):** Imagine **99% or 99.99%** of the cities on the map are road-blocked because Alice lacks clearance for them! Standard filtered HNSW either:
  - **Refuses to cross blocked neighborhoods** (`FAISS IDSelector` / fixed `efSearch`) and gets stranded in a tiny disconnected pocket with terrible recall, OR
  - **Walks through thousands of blocked streets** (`hnswlib` / iterative scans) checking permission flags at every detour until it accidentally stumbles back onto an authorized city — making queries tens of milliseconds slow instead of sub-millisecond.
Worse still, suppose the closest semantic region to Alice's question happens to contain documents she is *not* allowed to read (**negative correlation** between query topic and authorized documents). Standard graph walkers land right in the forbidden neighborhood and immediately hit dead ends!

### Trap 3: Denormalizing ACLs Onto Every Vector Row (**Revocation Rewrite Storm**)
*Idea:* Why ask SpiceDB at query time at all? Just store an `acl_allowed` column or list of allowed users right alongside every vector in PostgreSQL (`pgvector`) or your vector store!
- **Why it breaks:** Suppose **one manager revokes one folder** containing 1,024 documents (say, ~150,000 text chunks). Now the database has to find and `UPDATE` all **150,000 vector rows**, rewrite heap pages, update HNSW indexes, and flush transaction logs — blocking or stalling for minutes over a single folder permission change!

---

## 3. How Prism-ANN Solves All Three Traps

Instead of treating **SpiceDB permissions**, **HNSW graph navigation**, and **CPU memory layout** as three isolated black boxes, Prism-ANN co-designs them together:

### Solution 1: **Subtractive-Aware Upward Boundary Pruning (`P_UBP`)** — Fix Traps 1 & 3
- **Core Intuition (Stop at the Folder Signpost!):** Instead of expanding `/Engineering` into 4,096 individual documents, **stamp every vector chunk at ingest time with its permanent structural lineage** (`org / engineering / dept_a / folder_3 / doc_9`). Keep *all mutable permissions* (`VIEW` grants and `DENY` walls) strictly inside SpiceDB!
- When Alice queries, `P_UBP` walks top-down from her top grants (`Engineering`):
  - If a container subtree has **no `DENY` walls inside it**, we **stop immediately** and emit that single folder ID (`Engineering`) instead of 4,096 leaf files!
  - If a subtree *does* have a `DENY` wall nested underneath (we call that branch **tainted**), we only split down the path toward the `DENY` wall, emitting untainted sibling folders whole and subtracting the denied branch.
- **Why revocations touch zero vectors:** When Alice loses access to `folder_3`, we only delete **one edge** in SpiceDB — we never modify the vector chunks' structural lineage on disk (`0` vector writes!). A causal timestamp (`ZedToken`) swaps the immutable snapshot atomically so concurrent searches never see partial revocations or stale "New Enemy" state. *(Scope note: legacy `PrismANNIndex`/`PrismANNIndexV3` prototypes stamp lineages once at ingest for static folder trees/DAGs; when folder edges themselves are added or unlinked post-index in a multi-parent DAG, `DynamicMultiParentAuthGraph` + `VersionedLineageCorpus` in `src/modules/prism_ann_v3/dynamic_dag_ubp.py` update affected postings atomically per `ZedToken` revision without re-writing vectors.)*

### Solution 2: **Geometric Express Bridges (`H-HNSW v2`) + Adaptive Routing (`ACORN-GLS`)** — Fix Trap 2
- **Core Intuition (Private Employee Shuttle Lanes):** Inside each folder container and each shared topic cluster (**Meaning Magnet**), Prism-ANN adds just **8 carefully chosen long/diverse semantic edges** per vector (`4` inside the same L3 folder, `2` across sibling folders under the same L2 container, and `2` connecting the same Meaning Magnet topic across folders).
- Because these shortcuts connect vectors using **angular diversity** (pointing in varied directions inside the *same authorized folder*), Alice never gets stranded in an isolated island even when 99.9% of the rest of the map is forbidden!
- Meanwhile, during search, Prism-ANN measures local neighborhood survival ($\hat{S}_{\text{loc}}$ — how many of a node's neighbors Alice can read):
  - **Dense neighborhood?** Stay in fast **1-hop** mode (no wasted detour checks!).
  - **Medium sparsity?** Use 2-hop + express bridges.
  - **Depleted pocket (getting stranded)?** Follow bridge teleports — or trigger the **Local-Stall Guard** to switch strategies instantly!

### Solution 3: **Z-Ordered Contiguous Layout + Roaring Bitmaps + Hardware SIMD Scan** — Ultra-Fast Fallback
- **Core Intuition (Sort Books by Shelf Before Scanning):** At index build/compaction time, Prism-ANN sorts vector IDs in memory in **Z-order (lexicographical `(Folder Path, Meaning Magnet)` order)**.
- Because vectors in the same folder now sit **physically side by side in contiguous RAM**, a folder permission token turns into **one `[start, end)` integer interval** inside a compressed **Roaring Bitmap (`CRoaring` `RunContainer`)**!
- When the authorized set is small (e.g., `S <= 1%` — a few dozen to a few thousand vectors) OR when the Local-Stall Guard detects Alice landed in a forbidden semantic pocket, Prism-ANN skips pointer-chasing through scattered graph nodes altogether. Instead, it **streams straight across those contiguous `[start, end)` RAM blocks sequentially** (using 8-bit quantized dot products + exact 32-bit reranking, or exact 32-bit mode directly) with zero random memory jumps!
- New documents arriving live go into a lightweight **online delta buffer** (so writes don't block reads), while background compaction periodically re-sorts the Z-order array and remaps the HNSW neighbor table off the critical path.

---

## 4. End-to-End Query Walkthrough (Tracing One Query Step by Step)

```text
User Alice asks: "What is our Q4 architecture roadmap?" (ZedToken zeta = 42)
   │
   ▼  [1] Authorization Cut (P_UBP over SpiceDB Mirror / PG17)
   │  Root Grant: /Engineering  |  Deny Wall: /Engineering/M&A_Secret
   │  Untainted subtree emitted whole: [/Engineering/Core, /Engineering/ML, ...]
   │  Denied branch excised:           [/Engineering/M&A_Secret]
   ▼
   │  [2] Contiguous Filter Compilation (Z-Order + CRoaring)
   │  Each folder token maps to a contiguous [start, end) slice in RAM!
   │  Union(T_UBP+) \ Union(T_UBP-)  ──►  CRoaring RunContainers R_Phi, count N_cand
   ▼
   │  [3] Tri-Modal Execution Planner (Decision in microseconds)
   ├── If N_cand is tiny (e.g., <= 1.5% of corpus):
   │     └─► Mode 3 Direct Contiguous Scan:
   │         Stream contiguous [start, end) slices in L1/L2 cache
   │         Compute exact or SQ8+FP32-rerank inner products ──► Top-10 Chunks!
   │
   └── If N_cand is larger (> 1.5% of corpus):
         └─► Mode 2 H-HNSW v2 + ACORN-GLS:
             Enter via upper HNSW layers (with bounded portals from R_Phi)
             At each hop check local authorized fraction S_loc:
               - Dense? 1-hop fast-path
               - Sparse? Follow Geometric Folder/Magnet Bridges
               - Stalled in hostile neighborhood & N_cand <= 25k?
                 └─► Escalate cleanly to Mode 3 Contiguous Scan!
   ▼
   [4] Return Top-10 Authorized Chunks to LLM (0 unauthorized chunks ever returned)
```

---

## 5. Beginner Glossary

| Term | Plain-English Meaning |
| :--- | :--- |
| **Chunk & Embedding** | A short passage split out of a document, represented as an array of numbers (here `384` floats) capturing its semantic meaning. |
| **HNSW** | A multi-layer nearest-neighbor graph ("highway layers" + "local street layer") used to search millions of vectors in sub-millisecond time. |
| **ReBAC / SpiceDB** | Relationship-Based Access Control (open-source implementation of Google Zanzibar). Permissions depend on graph paths (`viewer`, `parent`, `but not` denials). |
| **Leaf-Disjunction Explosion** | Asking SpiceDB for every single readable document ID under a large folder, causing thousands of leaf IDs to stream over the network before search starts. |
| **Tainted Ancestor & UBP** | Any upper folder that contains a nested `DENY` inside it is *tainted*. Upward Boundary Pruning (`P_UBP`) stops expanding untainted folders at the folder level instead of walking to every file. |
| **Filtered HNSW Collapse** | When strict filters block most neighbors in an HNSW graph, causing fixed-budget greedy search to miss relevant results (`< 1%` recall). |
| **Revocation Rewrite Storm** | Having to `UPDATE` tens or hundreds of thousands of rows inside a vector database whenever one folder permission changes. |
| **Z-Ordering** | Sorting chunk IDs physically in RAM by their `(Folder Lineage, Topic Magnet)` path so entire folders sit next to each other sequentially. |
| **Roaring Bitmap (`CRoaring`)** | A high-speed compressed integer set format whose `RunContainer` stores a contiguous slice `[start, end)` in just 4 bytes! |
| **SIMD / ARM NEON / SQ8** | Single Instruction Multiple Data CPU vector math (`vdotq_s32` on Apple Silicon) multiplying 64 8-bit quantized (`SQ8`) numbers at once over contiguous RAM before exact 32-bit float (`FP32`) reranking. |

---

## 6. 4-Part Accessible Video Series Storyboard (`12`-Document Walkthrough)

When explaining Prism-ANN visually across engineering & stakeholder audiences, use this 4-video structure built around a concrete **12-document diagram (`D1..D12`)**:

1. **Video 1 — The Problem (`60–90s`):** Why authorized vector search is hard when permissions live in a hierarchy (`SpiceDB`) and similarity lives in an embedding graph (`HNSW`). Shows how top nearest neighbors (`D9`, `D10`, `D8`) can all be forbidden to Alice while permitted docs (`D1..D7`) hide behind disjoint folders.
2. **Video 2 — How Existing Methods Work (`90–120s`):** Side-by-side 12-document trace comparing leaf list enumeration (`LookupResources`), fixed-`ef` post-filtering (`FAISS IDSelector`), rejected-neighbor graph walks (`ACORN` / `RACORN` / `hnswlib`), and inline/partitioned ACL indexes (`pgvector UPDATE`, `HoneyBee`, `Curator`, `Veda`).
3. **Video 3 — What Prism Proposes (`90–120s`):** Trace `P_UBP` halting at untainted folders (`Core`), subtracting `D8`, scanning Z-ordered contiguous intervals (exact `FP32` at $S \le 0.1\%$ or `SQ8` NEON at $S \ge 0.5\%$), traversing `H-HNSW v2` geometric bridges, and handling dynamic shared-parent (`Eng -> D6 <- ML`) mutations via `VersionedLineageCorpus` (`dynamic_dag_ubp.py`).
4. **Video 4 — What Remains to Be Verified (`60–90s`):** Honest summary of falsified strict predictions (`PR7`, `PR8`, ultra-low `S=0.01%` live-RPC `PR10`), static vs. versioned hierarchy assumptions, empirical vs. mathematical `SQ8` recall bounds, and unrun upstream C++ baselines (`RACORN`, `EMA`, `Curator`, `Veda`) + billion-scale validation.
