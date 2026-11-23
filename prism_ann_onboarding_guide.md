# Welcome to Prism-ANN: A New-Grad Engineer's Guide

*(Mirror of [`docs/ONBOARDING_NEW_GRAD.md`](docs/ONBOARDING_NEW_GRAD.md) — start here if you are new to vector databases, HNSW graphs, Google Zanzibar / SpiceDB permissions, or SIMD optimization.)*

1. **The Problem:** An employee searches 500,000+ company docs with an internal AI assistant (RAG). Documents live inside nested org folders (`Org -> Dept -> Folder -> Doc`) governed by SpiceDB, including explicit `DENY` walls (`but not`). Search must return the top 10 most relevant chunks quickly without **ever** leaking an unauthorized chunk.
2. **The Three Traps of Naive Designs:**
   - **Authorize First (`LookupResources` Leaf Explosion):** Streaming thousands of allowed file IDs out of SpiceDB and unioning their bitmasks stalls every query before vector math begins.
   - **Filter During HNSW Hops (`Filtered HNSW Collapse`):** When 99%–99.99% of vectors are blocked to a user, standard HNSW graph search gets stranded in disconnected neighborhoods (low recall) or wanders tens of thousands of blocked hops (high latency).
   - **Store ACLs Inline on Vector Rows (`Revocation Rewrite Storm`):** Revoking one folder means running `UPDATE` across hundreds of thousands of rows inside your vector database (`pgvector` heap/HNSW maintenance stalls).
3. **How Prism-ANN Solves All Three:**
   - **Upward Boundary Pruning (`P_UBP`):** Stamp each vector once at ingest with its folder path (`Anc(v_i)`), keep mutable `GRANT`/`DENY` rules inside SpiceDB, halt tree expansion above untainted folders, and revoke entire subtrees in SpiceDB with **zero vector writes**.
   - **Geometric Express Bridges (`H-HNSW v2`) + `ACORN-GLS`:** Add `8` semantically diverse shortcut links inside each folder/parent/topic cluster (`+32 B/node`) so graph search stays connected even inside sparse permitted islands.
   - **Z-Ordered Contiguous Scans (`CRoaring` + SIMD):** Sort vectors in RAM by folder path so each allowed folder becomes one contiguous `[start, end)` range; for ultra-sparse queries or stalled searches, stream straight across contiguous memory slices sequentially.

Read the full walkthrough with diagrams, end-to-end query trace, and glossary in [`docs/ONBOARDING_NEW_GRAD.md`](docs/ONBOARDING_NEW_GRAD.md), and see [`docs/ARCHITECTURE_SENIOR_ENGINEER.md`](docs/ARCHITECTURE_SENIOR_ENGINEER.md) when you are ready to dive into the C++/Python implementation.
