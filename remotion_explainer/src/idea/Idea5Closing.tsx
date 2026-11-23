import React from "react";
import { COLORS, FONT_MONO } from "../theme";
import { IdeaShell, useIdeaPop } from "./IdeaShell";

export const Idea5Closing: React.FC = () => {
  const c1 = useIdeaPop(18);
  const c2 = useIdeaPop(65);
  const c3 = useIdeaPop(112);
  const seal = useIdeaPop(175);

  return (
    <IdeaShell
      step="05 · THE UNIFYING IDEA"
      title="Co-Designed From Authorization Graph Down to Silicon"
      subtitle="Turning three conflicting enterprise retrieval constraints into one unified architecture"
      sceneIdx={5}
      totalScenes={5}
    >
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", height: "100%" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 32, marginTop: 24 }}>
          {[
            {
              pop: c1,
              tag: "AUTHORIZATION",
              title: "Exact by Construction",
              body: "Subtractive Upward Boundary Pruning bounds tokens linearly in tree depth and revokes subtrees in O(1) with zero vector writes.",
              col: COLORS.emerald,
            },
            {
              pop: c2,
              tag: "GRAPH TOPOLOGY",
              title: "Navigable Under Sparsity",
              body: "Container- and concept-scoped Vamana/RNG semantic bridges preserve HNSW connectivity without predicate-agnostic degree bloat.",
              col: COLORS.cyan,
            },
            {
              pop: c3,
              tag: "MEMORY & HARDWARE",
              title: "Aligned to Contiguous SIMD",
              body: "Lexicographic Z-ordering turns permission tokens into contiguous intervals, letting a stall-guarded planner seamlessly switch to linear SIMD scans.",
              col: COLORS.violet,
            },
          ].map((item) => (
            <div
              key={item.tag}
              style={{
                background: COLORS.card,
                border: `2px solid ${item.col}77`,
                borderRadius: 24,
                padding: 36,
                opacity: item.pop,
                transform: `translateY(${(1 - item.pop) * 34}px)`,
              }}
            >
              <div style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 800, color: item.col, letterSpacing: 2 }}>
                {item.tag}
              </div>
              <div style={{ fontSize: 32, fontWeight: 800, marginTop: 12 }}>{item.title}</div>
              <div style={{ fontSize: 21, color: COLORS.muted, marginTop: 16, lineHeight: 1.45 }}>{item.body}</div>
            </div>
          ))}
        </div>

        <div
          style={{
            background: "linear-gradient(90deg, rgba(139,92,246,0.2), rgba(59,130,246,0.2), rgba(16,185,129,0.2))",
            border: `2.5px solid ${COLORS.cyan}`,
            borderRadius: 24,
            padding: "32px 44px",
            textAlign: "center",
            opacity: seal,
            transform: `scale(${0.94 + seal * 0.06})`,
          }}
        >
          <div style={{ fontSize: 36, fontWeight: 900, letterSpacing: -0.5 }}>
            Prism-ANN: Co-Designing ReBAC Graph Cuts, Semantic Bridges &amp; Contiguous Vector Memory
          </div>
          <div style={{ fontSize: 22, color: COLORS.cyan, marginTop: 10, fontFamily: FONT_MONO }}>
            Exact · Connected · Zero-Write by Construction
          </div>
        </div>
      </div>
    </IdeaShell>
  );
};
