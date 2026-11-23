import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { METRICS } from "../data";
import { COLORS, FONT_MONO, SceneShell, usePop } from "../theme";

const NODES = [
  { x: 110, y: 290, auth: true, label: "EP" },
  { x: 245, y: 180, auth: false },
  { x: 265, y: 390, auth: false },
  { x: 400, y: 125, auth: false },
  { x: 410, y: 280, auth: false },
  { x: 420, y: 440, auth: false },
  { x: 560, y: 190, auth: true, label: "B1" },
  { x: 585, y: 365, auth: false },
  { x: 720, y: 135, auth: false },
  { x: 740, y: 315, auth: true, label: "B2" },
  { x: 895, y: 220, auth: true, label: "Top-k" },
];

const BASE_EDGES: [number, number][] = [
  [0, 1], [0, 2], [1, 3], [1, 4], [2, 4], [2, 5],
  [3, 6], [4, 6], [4, 7], [5, 7], [6, 8], [7, 9], [8, 10], [9, 10],
];

export const Scene3Bridges: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const frame = useCurrentFrame();
  // 0..220: FAISS gets trapped at EP -> blocked by unauthorized wall
  // 220..500: M_bridge=8 geometric bridges ignite (EP -> B1 -> B2 -> Top-k)
  const bridgeLit = usePop(230);
  const hop1 = interpolate(frame, [265, 320], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const hop2 = interpolate(frame, [330, 385], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const hop3 = interpolate(frame, [395, 450], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const barPop = usePop(470);

  return (
    <SceneShell
      step="03 · GEOMETRIC EXPRESS BRIDGES (H-HNSW v2)"
      title="Bypassing Forbidden Walls with +1.91% Graph RAM Overhead"
      subtitle="M_bridge = 8 Vamana/RNG edges (4 L3 Folder + 2 L2 Parent + 2 Meaning Magnet) on the exact FAISS M=16 base graph"
      sceneIdx={3}
      totalScenes={8}
      durationInFrames={durationInFrames}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1.45fr 1fr", gap: 36, height: "100%" }}>
        {/* Left: Live Vector Space Animation */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${COLORS.cardBorder}`,
            borderRadius: 24,
            padding: 20,
            position: "relative",
          }}
        >
          <svg viewBox="0 0 1000 540" width="100%" height="100%">
            {/* Unauthorized Desert Zone */}
            <rect
              x="195"
              y="75"
              width="315"
              height="410"
              rx="24"
              fill="rgba(239,68,68,0.08)"
              stroke="rgba(239,68,68,0.35)"
              strokeDasharray="8 6"
            />
            <text x="352" y="106" textAnchor="middle" fill={COLORS.coral} fontSize="17" fontWeight="800">
              99.9% UNAUTHORIZED WALL
            </text>

            {/* Base HNSW edges */}
            {BASE_EDGES.map(([a, b]) => (
              <line
                key={`${a}-${b}`}
                x1={NODES[a].x}
                y1={NODES[a].y}
                x2={NODES[b].x}
                y2={NODES[b].y}
                stroke="#334155"
                strokeWidth="2.5"
              />
            ))}

            {/* Glowing Geometric Express Bridges */}
            {bridgeLit > 0.05 && (
              <g opacity={bridgeLit}>
                <path
                  d={`M ${NODES[0].x} ${NODES[0].y} Q 330 60 ${NODES[6].x} ${NODES[6].y}`}
                  fill="none"
                  stroke={COLORS.emerald}
                  strokeWidth="6"
                  strokeDasharray="12 6"
                />
                <path
                  d={`M ${NODES[6].x} ${NODES[6].y} Q 680 210 ${NODES[9].x} ${NODES[9].y}`}
                  fill="none"
                  stroke={COLORS.cyan}
                  strokeWidth="6"
                  strokeDasharray="12 6"
                />
                <path
                  d={`M ${NODES[9].x} ${NODES[9].y} Q 840 315 ${NODES[10].x} ${NODES[10].y}`}
                  fill="none"
                  stroke={COLORS.emerald}
                  strokeWidth="6"
                />
              </g>
            )}

            {/* Animated Search Beam Dot */}
            {hop1 > 0 && hop1 < 1 && (
              <circle
                cx={interpolate(hop1, [0, 1], [NODES[0].x, NODES[6].x])}
                cy={interpolate(hop1, [0, 1], [NODES[0].y, NODES[6].y]) - Math.sin(hop1 * Math.PI) * 140}
                r="13"
                fill={COLORS.cyan}
              />
            )}
            {hop2 > 0 && hop2 < 1 && (
              <circle
                cx={interpolate(hop2, [0, 1], [NODES[6].x, NODES[9].x])}
                cy={interpolate(hop2, [0, 1], [NODES[6].y, NODES[9].y])}
                r="13"
                fill={COLORS.cyan}
              />
            )}
            {hop3 > 0 && (
              <circle
                cx={interpolate(hop3, [0, 1], [NODES[9].x, NODES[10].x])}
                cy={interpolate(hop3, [0, 1], [NODES[9].y, NODES[10].y])}
                r={hop3 >= 1 ? 18 : 13}
                fill={COLORS.emerald}
                opacity={0.85}
              />
            )}

            {/* Graph Nodes */}
            {NODES.map((n, idx) => (
              <g key={idx}>
                <circle
                  cx={n.x}
                  cy={n.y}
                  r={n.auth ? 28 : 18}
                  fill={n.auth ? "#064E3B" : "#1E293B"}
                  stroke={n.auth ? COLORS.emerald : "#64748B"}
                  strokeWidth={n.auth ? 4 : 2}
                />
                {n.label && (
                  <text x={n.x} y={n.y + 6} textAnchor="middle" fill={COLORS.white} fontSize="16" fontWeight="800">
                    {n.label}
                  </text>
                )}
              </g>
            ))}
          </svg>

          <div
            style={{
              position: "absolute",
              bottom: 20,
              left: 24,
              right: 24,
              background: "#0B1328",
              border: `1px solid ${COLORS.cardBorder}`,
              borderRadius: 14,
              padding: "14px 20px",
              fontSize: 19,
              fontWeight: 700,
              color: bridgeLit > 0.3 ? COLORS.emerald : COLORS.coral,
            }}
          >
            {bridgeLit > 0.3
              ? "✓ Geometric Express Bridges Teleport Greedy Search Across Forbidden Space (+32 B/node = +1.91% Graph RAM)"
              : "✕ Standard FAISS M=16 Hits Unauthorized Wall & Terminates Early (5.75% Recall@10 at S = 0.1%)"}
          </div>
        </div>

        {/* Right: Multi-Engine Comparison Bars (S = 0.1% Quora) */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${COLORS.cardBorder}`,
            borderRadius: 24,
            padding: 30,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 700, color: COLORS.cyan }}>
              BEIR QUORA (522,931) · GRAPH-ONLY R@10 AT S = 0.1%
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, marginTop: 6 }}>
              Outperforms FAISS, ACORN-1 &amp; ACORN-γ at 0.143× Extra Graph RAM
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 22, marginTop: 16 }}>
            {[
              { name: "v3-geom-M8 (Ours · +32 B/n)", val: METRICS.h2QuoraS001V3Geom, col: COLORS.emerald },
              { name: "v3-geom-M8 on BEIR NQ 250k", val: METRICS.h2NqS001V3Geom, col: COLORS.cyan },
              { name: "FAISS HNSW M=16", val: METRICS.h2QuoraS001Faiss, col: COLORS.blue },
              { name: "ACORN-γ (γ=4 · +224 B/n)", val: METRICS.h2QuoraS001AcornG, col: COLORS.coral },
            ].map((row) => {
              const w = row.val * Math.max(0.15, barPop);
              return (
                <div key={row.name}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 19, fontWeight: 700, marginBottom: 8 }}>
                    <span>{row.name}</span>
                    <span style={{ fontFamily: FONT_MONO, color: row.col }}>{row.val.toFixed(2)}%</span>
                  </div>
                  <div style={{ height: 22, background: "#070E20", borderRadius: 10, overflow: "hidden" }}>
                    <div style={{ width: `${Math.max(2, w)}%`, height: "100%", background: row.col, borderRadius: 10 }} />
                  </div>
                </div>
              );
            })}
          </div>

          <div
            style={{
              background: "rgba(59,130,246,0.14)",
              border: `1px solid ${COLORS.blue}66`,
              borderRadius: 14,
              padding: "16px 20px",
              fontSize: 18,
              color: COLORS.white,
              lineHeight: 1.4,
            }}
          >
            <strong>4 L3 Folder</strong> (3 RNG + 1 medoid) + <strong>2 L2 Parent</strong> + <strong>2 Meaning Magnet</strong> bridges = <strong>+49 to +61 pts</strong> over FAISS M=16.
          </div>
        </div>
      </div>
    </SceneShell>
  );
};
