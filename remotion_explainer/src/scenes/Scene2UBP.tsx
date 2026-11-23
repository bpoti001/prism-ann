import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { METRICS } from "../data";
import { COLORS, FONT_MONO, SceneShell, usePop } from "../theme";

export const Scene2UBP: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const frame = useCurrentFrame();

  // Animation timeline phases:
  // 0..160: Naive leaf explosion (every leaf lights up red)
  // 160..320: DENY wall drops on D6 -> upward amber taint propagates to F3 -> L1B -> Root
  // 320+: UBP halts at untainted L1A & F4 (emerald glow!), excising only D6!
  const naivePhase = interpolate(frame, [20, 90, 155, 175], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const denyPop = usePop(170);
  const taintL2 = usePop(210);
  const taintL1 = usePop(245);
  const taintRoot = usePop(280);
  const cutPop = usePop(340);
  const statPop = usePop(440);

  const nodes = [
    { id: "org", x: 540, y: 70, label: "Org (Grant k0)", tier: 0 },
    { id: "l1a", x: 260, y: 205, label: "L1-A (Untainted)", tier: 1 },
    { id: "l1b", x: 820, y: 205, label: "L1-B (Tainted)", tier: 1 },
    { id: "f1", x: 130, y: 345, label: "Folder 1", tier: 2 },
    { id: "f2", x: 390, y: 345, label: "Folder 2", tier: 2 },
    { id: "f3", x: 690, y: 345, label: "Folder 3", tier: 2 },
    { id: "f4", x: 950, y: 345, label: "Folder 4", tier: 2 },
    { id: "d1", x: 75, y: 495, label: "Doc 1..512", tier: 3 },
    { id: "d2", x: 200, y: 495, label: "Doc 513..", tier: 3 },
    { id: "d3", x: 335, y: 495, label: "Doc 1k..", tier: 3 },
    { id: "d4", x: 460, y: 495, label: "Doc 1.5k..", tier: 3 },
    { id: "d5", x: 625, y: 495, label: "Doc OK", tier: 3 },
    { id: "d6", x: 760, y: 495, label: "DENY Wall", tier: 3 },
    { id: "d7", x: 900, y: 495, label: "Doc 3k..", tier: 3 },
    { id: "d8", x: 1020, y: 495, label: "Doc 4096", tier: 3 },
  ];

  const edges: [string, string][] = [
    ["org", "l1a"], ["org", "l1b"],
    ["l1a", "f1"], ["l1a", "f2"], ["l1b", "f3"], ["l1b", "f4"],
    ["f1", "d1"], ["f1", "d2"], ["f2", "d3"], ["f2", "d4"],
    ["f3", "d5"], ["f3", "d6"], ["f4", "d7"], ["f4", "d8"],
  ];

  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));

  const nodeStyle = (id: string) => {
    if (id === "d6" && denyPop > 0.05) return { fill: "#450A0A", stroke: COLORS.coral, glow: true };
    if (id === "f3" && taintL2 > 0.05) return { fill: "#451A03", stroke: COLORS.amber, glow: true };
    if (id === "l1b" && taintL1 > 0.05) return { fill: "#451A03", stroke: COLORS.amber, glow: true };
    if (id === "org" && taintRoot > 0.05) return { fill: "#451A03", stroke: COLORS.amber, glow: true };
    if (cutPop > 0.05 && ["l1a", "f4", "d5"].includes(id))
      return { fill: "#064E3B", stroke: COLORS.emerald, glow: true };
    if (cutPop > 0.05 && ["f1", "f2", "d1", "d2", "d3", "d4", "d7", "d8"].includes(id))
      return { fill: "#0F172A", stroke: "#334155", glow: false, dim: true };
    if (naivePhase > 0.1 && id.startsWith("d")) return { fill: "#450A0A", stroke: COLORS.coral, glow: true };
    return { fill: COLORS.card, stroke: COLORS.blue, glow: false };
  };

  return (
    <SceneShell
      step="02 · SUBTRACTIVE-AWARE UPWARD BOUNDARY PRUNING (P_UBP)"
      title="Cut Above the Leaves. Split Only Around DENY Walls."
      subtitle="Immutable lineage Anc(v_i) at ingest + upward taint propagation at query time (Theorem 1)"
      sceneIdx={2}
      totalScenes={8}
      durationInFrames={durationInFrames}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1.55fr 1fr", gap: 36, height: "100%" }}>
        {/* Left: Live Animated Tree SVG */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${COLORS.cardBorder}`,
            borderRadius: 24,
            padding: 20,
            position: "relative",
          }}
        >
          <svg viewBox="0 0 1100 580" width="100%" height="100%">
            {/* Edges */}
            {edges.map(([a, b]) => {
              const na = byId[a];
              const nb = byId[b];
              const isTaintEdge =
                (a === "f3" && b === "d6" && taintL2 > 0.1) ||
                (a === "l1b" && b === "f3" && taintL1 > 0.1) ||
                (a === "org" && b === "l1b" && taintRoot > 0.1);
              return (
                <line
                  key={`${a}-${b}`}
                  x1={na.x}
                  y1={na.y + 24}
                  x2={nb.x}
                  y2={nb.y - 24}
                  stroke={isTaintEdge ? COLORS.amber : "#334155"}
                  strokeWidth={isTaintEdge ? 5 : 2.5}
                  strokeDasharray={isTaintEdge ? "10 6" : undefined}
                />
              );
            })}

            {/* Pruned Frontier Cut Line */}
            {cutPop > 0.1 && (
              <g opacity={cutPop}>
                <rect x="65" y="162" width="390" height="86" rx="18" fill="none" stroke={COLORS.emerald} strokeWidth="3.5" strokeDasharray="10 6" />
                <text x="260" y="274" textAnchor="middle" fill={COLORS.emerald} fontSize="19" fontWeight="800">
                  HALT! Emit 1 Token (Covers 2,048 Leaves)
                </text>
              </g>
            )}

            {/* Nodes */}
            {nodes.map((n) => {
              const st = nodeStyle(n.id);
              const w = n.tier === 3 ? 114 : 185;
              const h = 48;
              return (
                <g key={n.id} opacity={st.dim ? 0.35 : 1}>
                  <rect
                    x={n.x - w / 2}
                    y={n.y - h / 2}
                    width={w}
                    height={h}
                    rx={12}
                    fill={st.fill}
                    stroke={st.stroke}
                    strokeWidth={st.glow ? 3.5 : 2}
                  />
                  <text
                    x={n.x}
                    y={n.y + 6}
                    textAnchor="middle"
                    fill={COLORS.white}
                    fontSize={n.tier === 3 ? 15 : 18}
                    fontWeight={700}
                  >
                    {n.label}
                  </text>
                </g>
              );
            })}
          </svg>

          {/* Animated Phase Callout Pill */}
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
              color: cutPop > 0.3 ? COLORS.emerald : denyPop > 0.3 ? COLORS.amber : COLORS.coral,
            }}
          >
            {cutPop > 0.3
              ? "✓ UBP Halts at Untainted Boundaries: Emits {L1-A, Folder 4, Doc OK} − {DENY Wall} → Exact Set Equivalence"
              : denyPop > 0.3
              ? "▲ Subtractive DENY Wall Detected: Upward Taint Splits Only Tainted Ancestors (Folder 3 → L1-B → Org)"
              : "✕ Naive SpiceDB LookupResources: Expands All 4,096 Leaf Docs → 98.30 ms PG17 Pre-Filter Stall"}
          </div>
        </div>

        {/* Right: Theorem 1 & Measured H1v3 Proof */}
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", gap: 22 }}>
          <div
            style={{
              background: COLORS.card,
              border: `2px solid ${COLORS.blue}66`,
              borderRadius: 22,
              padding: 28,
            }}
          >
            <div style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 700, color: COLORS.cyan }}>
              THEOREM 1 · TOKEN COMPRESSION BOUND
            </div>
            <div
              style={{
                fontFamily: FONT_MONO,
                fontSize: 32,
                fontWeight: 800,
                color: COLORS.white,
                marginTop: 14,
                padding: "14px 18px",
                background: "#070E20",
                borderRadius: 12,
                border: `1px solid ${COLORS.cardBorder}`,
              }}
            >
              |T_UBP+| ≤ k0 + m(b − 1)L
            </div>
            <div style={{ fontSize: 20, color: COLORS.muted, marginTop: 14, lineHeight: 1.4 }}>
              100% bound satisfaction across 1,200 live SpiceDB principals (median 76, max 285 tokens vs. 4,096 leaves).
            </div>
          </div>

          <div
            style={{
              background: COLORS.card,
              border: `2px solid ${COLORS.emerald}66`,
              borderRadius: 22,
              padding: 28,
              transform: `scale(${0.94 + statPop * 0.06})`,
              opacity: Math.max(0.25, statPop),
              flex: 1,
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
            }}
          >
            <div style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 700, color: COLORS.emerald }}>
              H1v3 LIVE PERSISTENT POSTGRESQL 17 SPICEDB
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, marginTop: 14 }}>
              <div style={{ background: "#070E20", padding: 18, borderRadius: 14 }}>
                <div style={{ fontFamily: FONT_MONO, fontSize: 44, fontWeight: 900, color: COLORS.emerald }}>
                  {METRICS.h1PgSpeedup}×
                </div>
                <div style={{ fontSize: 17, color: COLORS.muted }}>Local UBP ({METRICS.h1UbpMs} vs {METRICS.h1PgSpicedbMs} ms)</div>
              </div>
              <div style={{ background: "#070E20", padding: 18, borderRadius: 14 }}>
                <div style={{ fontFamily: FONT_MONO, fontSize: 44, fontWeight: 900, color: COLORS.cyan }}>
                  {METRICS.h1PgRpcSpeedup}×
                </div>
                <div style={{ fontSize: 17, color: COLORS.muted }}>Live gRPC ({METRICS.h1PgRpcMs} ms)</div>
              </div>
            </div>
            <div
              style={{
                marginTop: 16,
                padding: "12px 16px",
                borderRadius: 12,
                background: "rgba(16,185,129,0.14)",
                fontFamily: FONT_MONO,
                fontSize: 19,
                fontWeight: 700,
                color: COLORS.emerald,
              }}
            >
              ✓ 0 / 1,200 Mismatches (600 Mem + 600 PG17)
            </div>
          </div>
        </div>
      </div>
    </SceneShell>
  );
};
