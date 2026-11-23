export const FPS = 30;
export const TOTAL_FRAMES = 8795;
export const METRICS = {
  "nRecords": 169810,
  "h1MemSpicedbMs": 79.14,
  "h1PgSpicedbMs": 98.3,
  "h1UbpMs": 0.35,
  "h1PgRpcMs": 3.49,
  "h1MemSpeedup": 225.9,
  "h1PgSpeedup": 278.2,
  "h1PgRpcSpeedup": 28.2,
  "h2QuoraS001Faiss": 5.75,
  "h2QuoraS001AcornG": 0.25,
  "h2QuoraS001V3Geom": 66.6,
  "h2QuoraS001V3Full": 100.0,
  "h2QuoraS001V3FullMs": 0.09,
  "h2NqS001V3Geom": 75.57,
  "h2NqS001V3FullMs": 0.05,
  "h2QuoraSweep": [
    {
      "s": "0.1%",
      "faiss": 5.75,
      "acorn1": 0.95,
      "acorng": 0.25,
      "v3geom": 66.6,
      "v3full": 100.0
    },
    {
      "s": "0.5%",
      "faiss": 22.07,
      "acorn1": 19.95,
      "acorng": 15.55,
      "v3geom": 78.29,
      "v3full": 100.0
    },
    {
      "s": "1.0%",
      "faiss": 36.85,
      "acorn1": 28.55,
      "acorng": 53.64,
      "v3geom": 85.99,
      "v3full": 100.0
    },
    {
      "s": "5.0%",
      "faiss": 77.51,
      "acorn1": 31.66,
      "acorng": 87.69,
      "v3geom": 95.25,
      "v3full": 95.25
    }
  ],
  "h5Bars": [
    {
      "s": "0.1%",
      "faiss": 5.75,
      "faiss4p": 6.37,
      "v3geom": 66.6,
      "v3noportal": 67.18,
      "retained": 101.0
    },
    {
      "s": "0.5%",
      "faiss": 22.07,
      "faiss4p": 21.71,
      "v3geom": 78.29,
      "v3noportal": 79.59,
      "retained": 102.3
    },
    {
      "s": "1.0%",
      "faiss": 36.85,
      "faiss4p": 36.29,
      "v3geom": 85.99,
      "v3noportal": 86.51,
      "retained": 101.0
    }
  ],
  "h3QuoraFarFaiss": 5.56,
  "h3QuoraFarGeom": 54.56,
  "h3QuoraFarGuard": 97.17,
  "h3QuoraFarGuardMs": 0.35,
  "h3NqFarGuard": 96.42,
  "h3NqFarGuardMs": 0.17,
  "h3QuoraFarHnswMs": 45.37,
  "h3QuoraNearEvalRatio": 3.82,
  "h4P4aMs": 67.28,
  "h4PgvSec": 179.4,
  "h4Speedup": 2666.2
} as const;
export const TIMELINE = [
  {
    "index": 1,
    "id": "scene1_trilemma",
    "label": "01 \u00b7 The Enterprise Trilemma",
    "audioFile": "audio/scene1_trilemma.mp3",
    "durationSec": 34.146,
    "startFrame": 0,
    "durationInFrames": 1025,
    "narration": "Suppose an AI agent searches half a million enterprise documents, but the user is only allowed to see one in a thousand. Today, every database hits a wall. Asking PostgreSQL SpiceDB for every allowed leaf document stalls for ninety eight milliseconds before search even begins. Standard filtered H-N-S-W collapses to five point seven percent recall. And revoking a single folder in pgvector locks one hundred fifty three thousand rows for nearly three minutes. Prism-A-N-N breaks all three walls by co-designing the permission graph, the vector index, and ARM NEON hardware."
  },
  {
    "index": 2,
    "id": "scene2_ubp",
    "label": "02 \u00b7 Upward Boundary Pruning (P_UBP)",
    "audioFile": "audio/scene2_ubp.mp3",
    "durationSec": 38.045,
    "startFrame": 1025,
    "durationInFrames": 1142,
    "narration": "First, how do we stop SpiceDB from exploding down to every leaf? At ingest, Prism-A-N-N stamps each chunk with its immutable folder path. At query time, instead of expanding all four thousand leaves, Upward Boundary Pruning stops at the highest untainted folder. When an ethical-wall DENY appears deep in the tree, taint propagates upward along only that branch, splitting just its ancestors. Theorem One proves the token count stays tiny with zero false positives or negatives \u2014 cutting persistent PostgreSQL SpiceDB pre-filtering by two hundred seventy eight times, with zero mismatches across twelve hundred principals."
  },
  {
    "index": 3,
    "id": "scene3_bridges",
    "label": "03 \u00b7 Geometric Express Bridges (H-HNSW v2)",
    "audioFile": "audio/scene3_bridges.mp3",
    "durationSec": 39.662,
    "startFrame": 2167,
    "durationInFrames": 1190,
    "narration": "Now we have exact permission tokens, but a second trap waits inside the vector graph. At zero point one percent selectivity, ninety nine point nine percent of H-N-S-W neighbors are forbidden, so standard FAISS gets stranded at five point seven five percent recall. So Prism-A-N-N adds just eight Vamana-diverse semantic shortcuts per node: four inside the folder, two across sibling folders, and two inside the same Meaning Magnet \u2014 for only one point nine percent extra graph memory. Search glides right across forbidden regions, beating FAISS by up to sixty one points and beating compiled upstream ACORN-1 and ACORN-gamma at every selectivity on both Quora and Wikipedia."
  },
  {
    "index": 4,
    "id": "scene4_ablation",
    "label": "04 \u00b7 Causal Ablation Proof (H5v3)",
    "audioFile": "audio/scene4_ablation.mp3",
    "durationSec": 28.212,
    "startFrame": 3357,
    "durationInFrames": 847,
    "narration": "Wait \u2014 could lucky authorized entry portals be faking that recall lift? We tested that head-to-head on the exact same half-million-node FAISS graph. Adding four authorized portals to plain FAISS moves recall by less than one point, because one-hop search immediately steps back into forbidden space. Conversely, turning off portals completely on our geometric bridge graph retains over one hundred one percent of the recall gain. The semantic bridges \u2014 not entry portals \u2014 do the real work."
  },
  {
    "index": 5,
    "id": "scene5_neon",
    "label": "05 \u00b7 Z-Order CRoaring & ARM NEON Mode 3",
    "audioFile": "audio/scene5_neon.mp3",
    "durationSec": 39.636,
    "startFrame": 4204,
    "durationInFrames": 1190,
    "narration": "For ultra-strict filters at one percent visibility and below, traversing any graph still wastes random memory jumps. So Prism-A-N-N sorts internal vector IDs lexicographically by folder lineage and Meaning Magnet. Every permission token collapses into contiguous Roaring RunContainers. Our native C-plus-plus ARM NEON kernel streams straight across those intervals using sixty-four-MAC int-eight dot products followed by exact FP32 reranking \u2014 hitting one hundred percent recall in zero point zero five to zero point eleven milliseconds, and staying five to forty one times faster than hnswlib and pgvector even with live PostgreSQL SpiceDB RPCs included."
  },
  {
    "index": 6,
    "id": "scene6_stall_guard",
    "label": "06 \u00b7 Negative-Correlation Local-Stall Guard",
    "audioFile": "audio/scene6_stall_guard.mp3",
    "durationSec": 38.199,
    "startFrame": 5394,
    "durationInFrames": 1146,
    "narration": "But what if selectivity is two percent, yet the user's allowed folders sit semantically far from the query? In that negative-correlation pocket, FAISS drops to five percent recall and hnswlib stalls for forty five milliseconds. Inside our C-plus-plus kernel, a three-stage Local-Stall Guard monitors local survival at hop one, hop sixteen, and post-loop. The instant it spots a depleted pocket, it trips a circuit breaker straight into NEON Mode Three \u2014 recovering ninety seven point two percent recall on Quora in zero point three five milliseconds, while easy enriched queries stay on the fast one-hop path with three point eight times fewer distance evaluations."
  },
  {
    "index": 7,
    "id": "scene7_revocation",
    "label": "07 \u00b7 O(1) Zero-Write Revocation Race",
    "audioFile": "audio/scene7_revocation.mp3",
    "durationSec": 33.854,
    "startFrame": 6540,
    "durationInFrames": 1016,
    "narration": "Finally, watch what happens when compliance revokes access to a department covering one hundred fifty three thousand chunks. In PostgreSQL pgvector with an inline permission column, updating every row triggers massive heap rewrites and H-N-S-W index locks, stalling for one hundred seventy nine seconds. In Prism-A-N-N, because vectors only store immutable folder lineage, revoking access deletes a single edge in persistent PostgreSQL SpiceDB in sixty seven milliseconds with zero vector writes \u2014 two thousand six hundred sixty six times faster."
  },
  {
    "index": 8,
    "id": "scene8_provenance",
    "label": "08 \u00b7 Provenance, Tradeoffs & Sign-Off",
    "audioFile": "audio/scene8_provenance.mp3",
    "durationSec": 41.268,
    "startFrame": 7556,
    "durationInFrames": 1239,
    "narration": "Every number in this video comes directly from one frozen confirmatory run of one hundred sixty nine thousand eight hundred ten raw per-query logs, verified bit-for-bit across two real corpora with zero leaks. We also report tradeoffs plainly: keeping an auxiliary int-eight buffer alongside FP32 raises full Mode-Three memory to plus twenty four point eight percent, while graph-only bridges cost just one point nine percent. After an independent adversarial review with zero prior context, Prism-A-N-N earned seven point five out of ten, accept, with zero blockers. Zero leaks, instant revocation, and sub-millisecond enterprise retrieval \u2014 co-designed from SpiceDB down to silicon."
  }
] as const;
