# Prism-ANN v3 — Technical Explainer Narration & 4-Part Accessible Storyboard

## Part A: Revised Executive Briefing Script (Qualified Claims & Reviewer-Audit Sync)

## Slide 01 (00:00:00,000 – 00:00:35,865) — Prism-ANN: Co-Designed SpiceDB ReBAC & Filtered Vector Search

Welcome to the technical briefing on Prism-A-N-N version three: a co-designed enterprise retrieval prototype combining hierarchical SpiceDB permissions with filtered H-N-S-W search. Across one hundred sixty nine thousand eight hundred ten confirmatory queries on two public corpora plus three reviewer audits, Prism-A-N-N cuts broad-principal pre-filtering by up to two hundred seventy eight times, accelerates PostgreSQL folder revocation with zero vector writes, and observes zero leaks across the tested workloads.

## Slide 02 (00:00:35,865 – 00:01:22,330) — Why Enterprise AI Search Fails Compliance or Latency SLAs Today

Why do enterprise retrieval systems struggle today? When hierarchical Zanzibar permissions meet H-N-S-W vector indexes, three severe bottlenecks emerge. First, streaming thousands of leaf document IDs from PostgreSQL-backed SpiceDB stalls broad queries for ninety eight milliseconds median before vector search even starts. Second, when a user can only view zero point one percent of a corpus, standard FAISS H-N-S-W collapses to five point seven five percent recall, while unbounded graph walks spike up to one hundred forty seven milliseconds. Third, storing permissions inline on vector rows causes massive write amplification: revoking one folder across one hundred fifty three thousand chunks stalls pgvector for nearly three full minutes.

## Slide 03 (00:01:22,330 – 00:02:02,649) — Prism-ANN v3: Unifying Three Co-Designed Layers

Prism-A-N-N addresses all three bottlenecks by co-designing the authorization graph, the vector index, and the hardware scanner. In Layer One, Upward Boundary Pruning stamps structural lineages at ingest and halts SpiceDB traversal above leaf documents, splitting only around explicit deny walls—extended with atomic revisioned lineage graphs (`DynamicMultiParentAuthGraph` + `VersionedLineageCorpus`) when hierarchy edges change post-index. In Layer Two, Geometric Express Bridges add eight diverse semantic shortcuts per node across folders, parent containers, and Meaning Magnets for one point nine one percent extra graph memory. In Layer Three, Z-ordered Roaring bitmaps feed contiguous memory spans straight into a native C-plus-plus ARM NEON kernel with a multi-stage Local-Stall Guard.

## Slide 04 (00:02:02,649 – 00:02:39,205) — Zero Mismatches on Static Hierarchies & Atomic Dynamic DAG Revisions

Our first confirmatory experiment tests live SpiceDB version one point fifty seven in both memory and durable PostgreSQL seventeen modes across twelve hundred principals with up to twenty deny walls. Upward Boundary Pruning matches SpiceDB with zero mismatches on static-hierarchy workloads and obeys Theorem One across all twelve hundred principals. For broad principals accessing over one thousand documents, pre-filter compilation drops from ninety eight milliseconds on PostgreSQL SpiceDB down to zero point three five milliseconds on a local mirror, and three point four nine milliseconds when calling live PostgreSQL SpiceDB gRPC.

## Slide 05 (00:02:39,205 – 00:03:21,832) — Sub-Millisecond Kernel Speed & End-to-End Attribution Across Two Real Corpora

Next, we benchmarked live native engines across five hundred twenty two thousand BEIR Quora passages and two hundred fifty thousand Wikipedia passages. Graph-only geometric bridges beat FAISS M equals sixteen by up to sixty one recall points, and beat compiled upstream C-plus-plus ACORN-1 and ACORN-gamma across tested selectivities on both corpora. When the ARM NEON Mode Three scanner engages at one percent selectivity and below, Prism-A-N-N empirically reaches one hundred percent recall—mathematically exact under FP32 mode or small candidate counts ($N_{\text{cand}} \le M_{\text{rerank}}$)—in zero point zero five to zero point eleven milliseconds kernel time, or one point six to two point zero milliseconds directly timed end-to-end (`R10`) with live PostgreSQL SpiceDB RPC.

## Slide 06 (00:03:21,832 – 00:03:58,191) — Eliminating Negative-Correlation Collapse with Local-Stall Escalation

In real enterprise deployments, the hardest failure mode occurs when a user's permitted documents sit far from the query in embedding space. Under negative Global-Local Selectivity correlation ($r = S_{\text{loc}}/S \le 0.5$), FAISS collapses to five percent recall, and hnswlib takes up to forty five milliseconds. Prism-A-N-N's multi-stage Local-Stall Guard detects stalled queries automatically and escalates them to Mode Three, restoring ninety seven point two percent recall on Quora and ninety six point four percent on Wikipedia in zero point one seven to zero point three five milliseconds kernel latency.

## Slide 07 (00:03:58,191 – 00:04:33,705) — 67 ms Ethical-Wall Revocation & Opaque ZedToken Concurrency

Compliance teams care deeply about revocation speed: when an employee leaves a project or an ethical wall goes up, access must vanish cleanly. Updating an inline permission column across one hundred fifty three thousand chunks in PostgreSQL pgvector triggers heavy heap rewrites and index maintenance, taking one hundred seventy nine seconds median. With Prism-A-N-N, revoking the exact same folder deletes a single edge in persistent PostgreSQL SpiceDB in sixty seven milliseconds with zero vector-store writes, bounded causally by atomic opaque-ZedToken and lineage-revision snapshots (`0` leaks across `1,760` 8-thread live SpiceDB reads in `R11`).

## Slide 08 (00:04:33,705 – 00:05:03,879) — Why It Works: Geometric Bridges — Not Entry Portals — Drive the Gain

To verify our gains are not an artifact of lucky entry points, we ran a strict four-way ablation on the exact same five hundred twenty two thousand node FAISS base graph. Adding four authorized entry portals to plain FAISS moves recall by less than one point. Conversely, removing portals completely from our geometric bridge graph retains over one hundred one percent of the recall lift across all sub-one-percent selectivities, showing that Vamana-diverse intra-container bridges drive the connectivity win.

## Slide 09 (00:05:03,879 – 00:05:39,681) — Scientific Transparency: Falsified Cutoffs, Memory Cost, & Scope Boundaries

Scientific credibility requires reporting every limitation and falsified prediction transparently. Across our reviewer audits covering `207,685` total records, three strict pre-registered latency cutoffs—`PR7` (`0.434 ms` / `82.19×` mirror at fragmented `L5`), `PR8` (`0.329 ms` exact `FP32`), and ultra-low `S=0.01%` live-RPC `PR10` (`6.20–6.47× < 10×`)—were falsified and reported honestly alongside positive results. We separate our `+1.91%` graph-only memory cost from the `+24.8%` footprint when retaining an auxiliary `SQ8` buffer, and measure exact `FP32` Mode Three beating in-timer `SQ8` quantization+scan at $S \le 0.1\%$.

## Slide 10 (00:05:39,681 – 00:06:10,110) — Open Work Before External Submission & Enterprise Pilots

To summarize what remains before conference submission and pilot deployment: while zero leaks were observed across `1,000` independent dynamic multi-parent DAGs (`5,000` mutations) and live SpiceDB opaque-`ZedToken` concurrency, Prism-A-N-N has not yet been benchmarked against upstream binaries of `RACORN`, `EMA`, `Curator`, or `Veda`, or validated on billion-vector clusters. All reproducible proofs, pre-registered protocols, raw logs, and falsified checks are open in the repository for independent reproduction.

---

## Part B: Accessible 4-Part Video Explainer Series Roadmap (`12`-Document Walkthrough)

Designed for mixed technical & non-specialist audiences so every core mechanism is traceable by hand on a **12-document toy corpus** (`D1..D12` under folders `Root -> {Eng (Core D1-D4, ML D5-D8), HR (Payroll D9-D10, Policy D11-D12)}`, with shared project edge `Eng -> SharedSpec D6 <- ML` and deny wall on `ML/Secret D8` for Alice).

### Video 1 — The Problem (`60–90s`)
- **Hook:** Searching company knowledge when permissions live in a nested org/folder graph (SpiceDB) while meaning lives in a high-dimensional geometry map (HNSW).
- **12-Document Visual Trace:** Alice types *"benefits & model weights."* Nearest neighbors in embedding space are `D9 (Payroll)`, `D10 (HR)`, and `D8 (ML/Secret)`. All three sit closest semantically, yet **all three are forbidden** to Alice! Meanwhile her allowed documents (`D1..D7`) live inside subtrees of `Eng`.
- **Takeaway:** You cannot rank first and filter second without leaking or missing answers, and you cannot stream `100,000` individual leaf file IDs before every query.

### Video 2 — How Existing Methods Work (`90–120s`)
- **Side-by-Side Trace on `D1..D12`:**
  1. **Pre-Filter Leaf Expansion (`LookupResources`):** SpiceDB walks every leaf folder for Alice and hands the vector DB `[D1, D2, D3, D4, D5, D6, D7]`. Fast for 7 files, stalls at `79–98 ms` when a broad folder holds thousands of documents.
  2. **Post-Filter / Fixed-`ef` Graph (`FAISS IDSelector`):** Enters near `D9/D10`, sees neighbors blocked, hits `efSearch` budget while stranded in forbidden space (`0.87%`–`5.75%` recall at $S \le 0.1\%$).
  3. **In-Graph Fallback Walks (`ACORN` / `RACORN` / `hnswlib`):** Steps across rejected neighbors (`D9 -> D10 -> ...`) or keeps expanding (`hnswlib`), paying `20–147 ms` under extreme hostility or relying on an already-materialized external bitset (`RACORN`).
  4. **Inline ACL / Partitioned Indexes (`pgvector UPDATE`, `HoneyBee`, `Curator`, `Veda`):** Replicates/partitions indexes or stores permission bits directly on rows; revoking `Eng` rewrites every affected vector row (`179.4 s` in `pgvector UPDATE`).

### Video 3 — What Prism Proposes (`90–120s`)
- **Co-Design in 3 Steps on `D1..D12`:**
  1. **Positive Boundaries + Subtractive Exclusions ($\mathcal{P}_{\text{UBP}}$):** Stop at untainted folder containers (`Core` -> `1` token for `D1..D4`!), split `ML` only because `D8` is denied (`+ML_public, -D8`). Zero vector rows store permissions.
  2. **Z-Order Contiguous Intervals + Geometric Bridges:** Sort `D1..D12` by folder lineage so `Core` becomes one slice `[0, 4)` scanned straight sequentially by SIMD/exact-FP32 (`Mode 3`), while adding `8` angularly diverse intra-container edges (`H-HNSW v2`) for larger slices.
  3. **What Changed for Dynamic Multi-Parent Graphs (`dynamic_dag_ubp.py`):** Show `Eng -> D6 <- ML`. If static stamping isn't updated when a new parent `BadFolder -> D6` (with deny on `BadFolder`) is added—or if deleting `Eng -> D6` globally blacklists `D6`—the static prototype breaks! `VersionedLineageCorpus` solves this via single-edge unlinks and atomic `CorpusRevisionSnapshot` swaps bound to SpiceDB `ZedToken`s (`0` vector writes).

### Video 4 — What Remains to Be Verified (`60–90s`)
- **Honest Scientific Scorecard:**
  - **Falsified Strict Cutoffs:** `PR7` (`0.434 ms > 0.35 ms` at fragmented L5), `PR8` (`0.329 ms > 0.25 ms` exact FP32 at `S=1%`), and `PR10` (`6.20–6.47× < 10×` live SpiceDB speedup when only 3 leaf docs match at `S=0.01%`).
  - **Key Architectural Distinctions:** Static-hierarchy legacy facades (`PrismANNIndex`, `PrismANNIndexV3`) vs. versioned dynamic DAGs (`DynamicPrismANNIndex`); exact `FP32` beating in-timer `SQ8` at $S \le 0.1\%$.
  - **Open Work:** Independent clean-machine reproduction, direct benchmarking of upstream C++ `RACORN`, `EMA`, `Curator`, and `Veda` binaries, non-clustered multi-tenant workloads, and billion-scale Zanzibar clusters.
