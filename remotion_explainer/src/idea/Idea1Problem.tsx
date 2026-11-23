import React from "react";
import { COLORS, FONT_MONO } from "../theme";
import { IdeaShell, useIdeaPop } from "./IdeaShell";

export const Idea1Problem: React.FC = () => {
  const g1 = useIdeaPop(18);
  const g2 = useIdeaPop(48);
  const w1 = useIdeaPop(115);
  const w2 = useIdeaPop(170);
  const w3 = useIdeaPop(225);

  return (
    <IdeaShell
      step="01 · THE PROBLEM"
      title="When Hierarchical Permissions Meet Vector Search"
      subtitle="Enterprise retrieval must jointly satisfy a ReBAC authorization graph and an ontology graph inside HNSW"
      sceneIdx={1}
      totalScenes={5}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1.05fr 1.25fr", gap: 36, height: "100%" }}>
        {/* Left: Dual-Graph Predicate Diagram */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${COLORS.cardBorder}`,
            borderRadius: 24,
            padding: 28,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div style={{ fontFamily: FONT_MONO, fontSize: 17, fontWeight: 700, color: COLORS.cyan }}>
            DUAL-GRAPH CONJUNCTIVE RETRIEVAL
          </div>

          <svg viewBox="0 0 720 460" width="100%" height="580" style={{ margin: "auto 0" }}>
            {/* ReBAC Tree Box */}
            <g opacity={g1}>
              <rect x="20" y="24" width="315" height="250" rx="18" fill="#0A1429" stroke={COLORS.blue} strokeWidth="2.5" />
              <text x="177" y="58" textAnchor="middle" fill={COLORS.blue} fontSize="20" fontWeight="800">
                ReBAC Graph G_auth
              </text>
              <circle cx="177" cy="104" r="17" fill="#1E3A8A" stroke={COLORS.blue} strokeWidth="2.5" />
              <line x1="177" y1="121" x2="105" y2="164" stroke="#60A5FA" strokeWidth="2.5" />
              <line x1="177" y1="121" x2="248" y2="164" stroke="#60A5FA" strokeWidth="2.5" />
              <circle cx="105" cy="176" r="16" fill="#065F46" stroke={COLORS.emerald} strokeWidth="2.5" />
              <circle cx="248" cy="176" r="16" fill="#7F1D1D" stroke={COLORS.coral} strokeWidth="2.5" />
              <text x="248" y="216" textAnchor="middle" fill={COLORS.coral} fontSize="15" fontWeight="800">
                but not (DENY)
              </text>
              <text x="105" y="216" textAnchor="middle" fill={COLORS.emerald} fontSize="15" fontWeight="700">
                Nested Grants
              </text>
              <text x="177" y="252" textAnchor="middle" fill={COLORS.muted} fontSize="15">
                Org → Dept → Folder → Doc
              </text>
            </g>

            {/* Ontology DAG Box */}
            <g opacity={g2}>
              <rect x="385" y="24" width="315" height="250" rx="18" fill="#0A1429" stroke={COLORS.violet} strokeWidth="2.5" />
              <text x="542" y="58" textAnchor="middle" fill={COLORS.violet} fontSize="20" fontWeight="800">
                Ontology Graph T_ont
              </text>
              <circle cx="542" cy="108" r="18" fill="#4C1D95" stroke={COLORS.violet} strokeWidth="2.5" />
              <line x1="542" y1="126" x2="465" y2="178" stroke="#A78BFA" strokeWidth="2.5" />
              <line x1="542" y1="126" x2="620" y2="178" stroke="#A78BFA" strokeWidth="2.5" />
              <circle cx="465" cy="186" r="16" fill="#2E1065" stroke="#A78BFA" strokeWidth="2" />
              <circle cx="620" cy="186" r="16" fill="#2E1065" stroke="#A78BFA" strokeWidth="2" />
              <text x="542" y="252" textAnchor="middle" fill={COLORS.muted} fontSize="15">
                Concept / Meaning Magnet Filter
              </text>
            </g>

            {/* Intersection symbol & target HNSW */}
            <text x="360" y="156" textAnchor="middle" fill={COLORS.white} fontSize="34" fontWeight="900">
              ∩
            </text>
            <line x1="177" y1="274" x2="330" y2="338" stroke={COLORS.cyan} strokeWidth="3" />
            <line x1="542" y1="274" x2="390" y2="338" stroke={COLORS.cyan} strokeWidth="3" />

            <rect x="52" y="338" width="616" height="94" rx="16" fill="#082032" stroke={COLORS.cyan} strokeWidth="2.5" />
            <text x="360" y="376" textAnchor="middle" fill={COLORS.white} fontSize="22" fontWeight="800">
              Filtered Nearest-Neighbor Search (HNSW)
            </text>
            <text x="360" y="408" textAnchor="middle" fill={COLORS.cyan} fontSize="16" fontFamily={FONT_MONO}>
              Find Top-k closest v_i ∈ Φ(u, C_q, ζ) with 0 leaks
            </text>
          </svg>
        </div>

        {/* Right: Three Fundamental Structural Tensions */}
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", gap: 22 }}>
          {[
            {
              pop: w1,
              tag: "TENSION 01 · AUTHORIZATION GRAPH",
              title: "Leaf-Disjunction Explosion — Θ(b^L)",
              desc: "Evaluating an upper-level grant down a depth-L, branching-b hierarchy expands exponentially many leaf documents before vector search can even start.",
              col: COLORS.coral,
            },
            {
              pop: w2,
              tag: "TENSION 02 · VECTOR GRAPH TOPOLOGY",
              title: "Filtered HNSW Percolation Collapse",
              desc: "Under strict visibility or negative query-permission correlation, almost all HNSW neighbors are forbidden — shattering the navigable graph into disconnected islands.",
              col: COLORS.amber,
            },
            {
              pop: w3,
              tag: "TENSION 03 · MUTABLE PERMISSIONS",
              title: "Revocation Write Amplification — Θ(N_chunks)",
              desc: "Copying permissions onto vector rows avoids query-time tree walks, but revoking one department triggers massive in-place rewrites across the vector index.",
              col: COLORS.coral,
            },
          ].map((item) => (
            <div
              key={item.tag}
              style={{
                background: COLORS.card,
                border: `2px solid ${item.col}66`,
                borderRadius: 22,
                padding: "24px 30px",
                opacity: item.pop,
                transform: `translateX(${(1 - item.pop) * 44}px)`,
                flex: 1,
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
              }}
            >
              <div style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 800, color: item.col, letterSpacing: 1.5 }}>
                {item.tag}
              </div>
              <div style={{ fontSize: 28, fontWeight: 800, marginTop: 8 }}>{item.title}</div>
              <div style={{ fontSize: 20, color: COLORS.muted, marginTop: 8, lineHeight: 1.4 }}>{item.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </IdeaShell>
  );
};
