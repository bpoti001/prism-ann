import React from "react";
import { COLORS, FONT_MONO } from "../theme";
import { IdeaShell, useIdeaPop } from "./IdeaShell";

export const Idea2Sota: React.FC = () => {
  const c1 = useIdeaPop(20);
  const c2 = useIdeaPop(95);
  const c3 = useIdeaPop(170);
  const foot = useIdeaPop(245);

  const paradigms = [
    {
      pop: c1,
      tag: "APPROACH 1",
      title: "External Pre-Filter + Standard HNSW",
      examples: "SpiceDB LookupResources + FAISS / hnswlib",
      works: "Exact ReBAC semantics and O(1) graph revocation.",
      breaks: "Streams Θ(b^L) leaf IDs at query time; fixed-ef HNSW disconnects at low selectivity, while unbounded walks scan tens of thousands of forbidden nodes.",
      col: COLORS.blue,
    },
    {
      pop: c2,
      tag: "APPROACH 2",
      title: "Inline ACL Columns on Vector Rows",
      examples: "Payload metadata filters / pgvector SQL ACLs",
      works: "Eliminates external authorization graph walks on the read path.",
      breaks: "Couples mutable permissions to vector storage — revoking a shared folder forces Θ(N_chunks) row mutations, heap rewrites, and HNSW maintenance locks.",
      col: COLORS.amber,
    },
    {
      pop: c3,
      tag: "APPROACH 3",
      title: "Filtered-ANN & RBAC Graph Indexes",
      examples: "ACORN-1 / ACORN-γ, Filtered-DiskANN, UNG, HoneyBee",
      works: "Improves low-selectivity graph connectivity via 2-hop expansion, label stitching, or role partitions.",
      breaks: "Either assumes flat static labels / monotonic RBAC (no subtractive DENYs), or pays large predicate-agnostic degree bloat (M_β) that still stalls under extreme sparsity.",
      col: COLORS.violet,
    },
  ];

  return (
    <IdeaShell
      step="02 · STATE OF THE ART (PRIOR PARADIGMS)"
      title="How Earlier Systems Tried to Solve This — and Where Each Breaks"
      subtitle="Every existing family solves one dimension of the trilemma while exposing another"
      sceneIdx={2}
      totalScenes={5}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 32, marginTop: 12 }}>
        {paradigms.map((p) => (
          <div
            key={p.tag}
            style={{
              background: COLORS.card,
              border: `2px solid ${p.col}66`,
              borderRadius: 24,
              padding: 32,
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              height: 560,
              opacity: p.pop,
              transform: `translateY(${(1 - p.pop) * 40}px)`,
            }}
          >
            <div>
              <div style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 800, color: p.col, letterSpacing: 2 }}>
                {p.tag}
              </div>
              <div style={{ fontSize: 28, fontWeight: 800, marginTop: 10, lineHeight: 1.2 }}>{p.title}</div>
              <div
                style={{
                  fontFamily: FONT_MONO,
                  fontSize: 15,
                  color: COLORS.cyan,
                  marginTop: 10,
                  padding: "8px 12px",
                  background: "#081226",
                  borderRadius: 10,
                }}
              >
                {p.examples}
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              <div
                style={{
                  background: "rgba(16,185,129,0.1)",
                  border: "1px solid rgba(16,185,129,0.35)",
                  borderRadius: 14,
                  padding: 16,
                }}
              >
                <div style={{ fontFamily: FONT_MONO, fontSize: 15, fontWeight: 800, color: COLORS.emerald }}>✓ WHAT WORKS</div>
                <div style={{ fontSize: 18, color: COLORS.white, marginTop: 6, lineHeight: 1.35 }}>{p.works}</div>
              </div>

              <div
                style={{
                  background: "rgba(239,68,68,0.1)",
                  border: "1px solid rgba(239,68,68,0.35)",
                  borderRadius: 14,
                  padding: 16,
                }}
              >
                <div style={{ fontFamily: FONT_MONO, fontSize: 15, fontWeight: 800, color: COLORS.coral }}>✕ FUNDAMENTAL GAP</div>
                <div style={{ fontSize: 18, color: COLORS.muted, marginTop: 6, lineHeight: 1.35 }}>{p.breaks}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div
        style={{
          marginTop: 28,
          background: "rgba(59,130,246,0.14)",
          border: `2px solid ${COLORS.blue}`,
          borderRadius: 18,
          padding: "20px 32px",
          fontSize: 23,
          fontWeight: 700,
          textAlign: "center",
          opacity: foot,
        }}
      >
        The Missing Link: <span style={{ color: COLORS.cyan }}>Authorization graph cuts, HNSW topology, and memory layout have never been co-designed together.</span>
      </div>
    </IdeaShell>
  );
};
