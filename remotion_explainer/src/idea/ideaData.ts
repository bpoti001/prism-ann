export const IDEA_FPS = 24;
export const IDEA_TOTAL_FRAMES = 2481;
export const IDEA_TIMELINE = [
  {
    "index": 1,
    "id": "idea1_problem",
    "label": "01 \u00b7 The Problem",
    "audioFile": "audio_idea/idea1_problem.mp3",
    "durationSec": 20.719,
    "startFrame": 0,
    "durationInFrames": 498,
    "narration": "In enterprise AI retrieval, every vector must pass two graphs simultaneously: a hierarchical permission tree with subtractive DENY walls, and an ontology filter. Combining hierarchical permissions with H-N-S-W search triggers three tensions: leaf-set explosion, disconnected vector graphs under strict filters, and costly rewrite storms on revocation."
  },
  {
    "index": 2,
    "id": "idea2_sota",
    "label": "02 \u00b7 State of the Art",
    "audioFile": "audio_idea/idea2_sota.mp3",
    "durationSec": 21.952,
    "startFrame": 498,
    "durationInFrames": 527,
    "narration": "Prior approaches fix one tension while exposing another. External pre-filtering via SpiceDB walks exponential leaves and disconnects fixed-budget H-N-S-W. Inline ACL stamping skips tree walks, but folder revocations rewrite massive vector rows. Filtered graphs like ACORN or Filtered-DiskANN target flat labels, missing hierarchical DENYs and paying heavy degree bloat."
  },
  {
    "index": 3,
    "id": "idea3_theory",
    "label": "03 \u00b7 Theoretical Foundation",
    "audioFile": "audio_idea/idea3_theory.mp3",
    "durationSec": 25.245,
    "startFrame": 1025,
    "durationInFrames": 606,
    "narration": "Our idea co-designs all three layers mathematically first. Theorem 1, Upward Boundary Pruning, halts at untainted folders and splits only DENY-tainted ancestors, bounding tokens linearly in depth with exact equivalence. Conditional percolation shows sparse angular semantic bridges inside each container restore navigability. Finally, lexicographic Z-ordering turns tokens into contiguous intervals with a clean SIMD crossover."
  },
  {
    "index": 4,
    "id": "idea4_system",
    "label": "04 \u00b7 System-Level Architecture",
    "audioFile": "audio_idea/idea4_system.mp3",
    "durationSec": 19.974,
    "startFrame": 1631,
    "durationInFrames": 480,
    "narration": "At the system level, ingest stamps each chunk once with immutable ancestor lineage and sorts IDs in Z-order \u2014 so revoking a department deletes one graph edge with zero vector writes. At query time, pruned tokens compile into Roaring RunContainers, and a stall-guarded planner routes between bridged H-N-S-W and a zero-copy SIMD interval scan."
  },
  {
    "index": 5,
    "id": "idea5_closing",
    "label": "05 \u00b7 The Unifying Idea",
    "audioFile": "audio_idea/idea5_closing.mp3",
    "durationSec": 15.392,
    "startFrame": 2111,
    "durationInFrames": 370,
    "narration": "That is the core idea of Prism-A-N-N: co-design the authorization graph cut, semantic bridge topology, and contiguous memory layout as one system \u2014 making hierarchical, subtractive vector retrieval exact, navigable, and zero-write by construction."
  }
] as const;
