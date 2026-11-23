export const ONB_FPS = 24;
export const ONB_TOTAL_FRAMES = 6392;
export const ONB_TIMELINE = [
  {
    "index": 1,
    "id": "onb1_scenario",
    "label": "01 \u00b7 Real-World Scenario",
    "audioFile": "audio_onb/onb1_scenario.mp3",
    "durationSec": 36.099,
    "startFrame": 0,
    "durationInFrames": 867,
    "narration": "Hey, welcome to the team! Before you dive into our codebase, let's build intuition for why Prism-A-N-N exists. Imagine Maya, an engineer, asks our internal AI assistant a question across half a million company document chunks stored as embeddings \u2014 lists of numbers representing meaning. Here's the catch: Maya is only allowed to read one in a thousand documents, and her Engineering folder contains a secret subfolder marked DENY. Leaking even one forbidden snippet into the prompt is a Sev-zero security bug. So every search must enforce strict folder permissions and find the closest matches in just a few milliseconds."
  },
  {
    "index": 2,
    "id": "onb2_problems",
    "label": "02 \u00b7 The 3 Naive Traps",
    "audioFile": "audio_onb/onb2_problems.mp3",
    "durationSec": 47.034,
    "startFrame": 867,
    "durationInFrames": 1129,
    "narration": "Why not bolt an existing permission service onto an existing vector database? Three traps hit immediately. First, leaf-set explosion: SpiceDB is an authorization graph \u2014 like a company org chart for folder access. Asking it for every allowed leaf file walks the whole tree and stalls for ninety-eight milliseconds before search even begins. Second, getting stranded in filtered H-N-S-W: vector indexes connect similar docs like a highway map, so when ninety-nine point nine percent of nodes are blocked, search gets trapped on an island and standard FAISS drops to five point seven five percent recall. Third, revocation rewrite storms: copying user lists straight onto Postgres pgvector rows avoids the tree walk, until revoking one folder locks one hundred fifty-three thousand rows for nearly three minutes."
  },
  {
    "index": 3,
    "id": "onb3_ubp_bridges",
    "label": "03 \u00b7 Pruning & Express Bridges",
    "audioFile": "audio_onb/onb3_ubp_bridges.mp3",
    "durationSec": 53.276,
    "startFrame": 1996,
    "durationInFrames": 1279,
    "narration": "Prism-A-N-N solves these by co-designing permissions, graph links, and memory together. First: Upward Boundary Pruning. Think of mailing a letter to Building B instead of listing every desk inside it. At ingest, each chunk stores only its immutable folder path \u2014 never mutable user lists. At query time, we stop at the highest allowed folder and split only branches sitting above a DENY wall. That cuts SpiceDB pre-filtering from ninety-eight milliseconds down to zero point three five milliseconds \u2014 two hundred seventy-eight times faster \u2014 and makes folder revocation an instant sixty-seven millisecond edge delete with zero vector writes. Second: Semantic Shortcut Bridges. We add just eight diverse shortcut links per node \u2014 like highway overpasses jumping straight over forbidden zones \u2014 lifting graph-only recall from five point seven five to sixty-six point six percent for only one point nine percent extra memory."
  },
  {
    "index": 4,
    "id": "onb4_zorder_simd",
    "label": "04 \u00b7 Z-Order, Roaring & SIMD",
    "audioFile": "audio_onb/onb4_zorder_simd.mp3",
    "durationSec": 45.004,
    "startFrame": 3275,
    "durationInFrames": 1081,
    "narration": "Third: Contiguous Memory and SIMD Scans. When a user can see less than one percent of documents, jumping randomly across any graph is slower than scanning allowed vectors straight through RAM. So we sort vector IDs by folder path and topic \u2014 called Z-ordering \u2014 grouping allowed chunks side-by-side like books on one library shelf. We compress those ID ranges into Roaring Bitmaps \u2014 storing a whole span as one start-to-end interval \u2014 and sweep straight across them using SIMD, CPU instructions that run dozens of multiplications per clock cycle. And if a normal graph search ever hits a dead-end pocket, our runtime Local-Stall Guard flips a circuit breaker straight into this SIMD scan, recovering ninety-seven to one hundred percent recall in under a third of a millisecond."
  },
  {
    "index": 5,
    "id": "onb5_query_flow",
    "label": "05 \u00b7 End-to-End Query Flow",
    "audioFile": "audio_onb/onb5_query_flow.mp3",
    "durationSec": 39.907,
    "startFrame": 4356,
    "durationInFrames": 958,
    "narration": "Let's trace one live query from API call to response so you can recognize every module in our repo. First, the control plane asks SpiceDB with Upward Boundary Pruning for Maya's compact folder tokens \u2014 never post-filtering after search, which returns empty results under strict policies. Next, those tokens intersect with her topic filter into contiguous Roaring ranges, giving the exact candidate count. Finally, our Tri-Modal Cost Router picks the fastest engine: dense queries cruise through bridged H-N-S-W with the Stall Guard watching, while ultra-strict or stalled queries stream through our zero-copy SIMD interval scan and rerank the top matches in full precision."
  },
  {
    "index": 6,
    "id": "onb6_takeaways",
    "label": "06 \u00b7 Production Trade-offs",
    "audioFile": "audio_onb/onb6_takeaways.mp3",
    "durationSec": 44.903,
    "startFrame": 5314,
    "durationInFrames": 1078,
    "narration": "As you start shipping code here, keep four production realities in mind. One: zero permission leaks is non-negotiable \u2014 exact boundary pruning guarantees zero leaks across all one hundred sixty-nine thousand logged queries. Two: revocation is instant and zero-write \u2014 sixty-seven milliseconds versus three minutes in pgvector. Three: sub-millisecond recall stays at ninety-seven to one hundred percent even at zero point one percent visibility. And four: know the memory trade-off \u2014 shortcut bridges cost just one point nine percent extra RAM, while keeping an auxiliary int-eight copy for ultra-fast SIMD scans adds twenty-four point eight percent RAM. That's the whole mental model: co-design permissions, graphs, and memory together. Welcome aboard!"
  }
] as const;
