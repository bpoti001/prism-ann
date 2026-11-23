import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { COLORS, FONT_MONO } from "../theme";
import { OnbShell, useOnbPop } from "./OnbShell";

export const Onb4ZorderSimd: React.FC = () => {
  const frame = useCurrentFrame();
  const s1 = useOnbPop(18);
  const sortT = interpolate(frame, [55, 145], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const s2 = useOnbPop(150);
  const s3 = useOnbPop(215);

  return (
    <OnbShell
      step="04 · HOW PRISM-ANN SOLVES IT (PART 2 OF 2)"
      title="Put Allowed Books on One Shelf — Then Sweep With SIMD"
      subtitle="Z-Ordering groups folder chunks side-by-side in RAM; Roaring Bitmaps & SIMD sweep them at memory speed"
      sceneIdx={4}
      totalScenes={6}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 28, height: "100%" }}>
        {/* Top Card: Interactive Memory Shuffle Animation */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${COLORS.emerald}66`,
            borderRadius: 24,
            padding: "24px 32px",
            opacity: s1,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <div style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 800, color: COLORS.emerald }}>
              LIBRARY SHELF ANALOGY · LEXICOGRAPHIC Z-ORDERING BY (FOLDER PATH, TOPIC)
            </div>
            <div style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 800, color: COLORS.cyan }}>
              {sortT < 0.5 ? "BEFORE: Random Scattered RAM Jumps" : "AFTER: Contiguous Slice [1024..1535]"}
            </div>
          </div>

          <svg viewBox="0 0 1660 190" width="100%" height="190">
            {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11].map((i) => {
              const isAllowed = i === 1 || i === 4 || i === 7 || i === 10;
              const allowedOrder = [1, 4, 7, 10].indexOf(i);
              const blockedOrder = [0, 2, 3, 5, 6, 8, 9, 11].indexOf(i);
              const targetIdx = isAllowed ? allowedOrder : 4 + blockedOrder;
              const x = interpolate(sortT, [0, 1], [30 + i * 134, 30 + targetIdx * 134]);
              return (
                <g key={i}>
                  <rect
                    x={x}
                    y={24}
                    width={114}
                    height={86}
                    rx={14}
                    fill={isAllowed ? "#065F46" : "#1E293B"}
                    stroke={isAllowed ? COLORS.emerald : "#475569"}
                    strokeWidth={3}
                  />
                  <text x={x + 57} y={62} textAnchor="middle" fill={COLORS.white} fontSize="16" fontWeight="800">
                    {isAllowed ? "Eng/FE" : "Other"}
                  </text>
                  <text x={x + 57} y={88} textAnchor="middle" fill={isAllowed ? COLORS.cyan : COLORS.muted} fontSize="14" fontFamily={FONT_MONO}>
                    {isAllowed ? "ALLOWED" : "blocked"}
                  </text>
                </g>
              );
            })}
            <path d="M 30 126 L 30 144 L 546 144 L 546 126" fill="none" stroke={COLORS.emerald} strokeWidth="4" opacity={sortT} />
            <text x="30" y="176" textAnchor="start" fill={COLORS.emerald} fontSize="20" fontWeight="800" fontFamily={FONT_MONO} opacity={sortT}>
              1 Contiguous Roaring RunContainer: [1024 .. 1535] → Zero Pointer Chasing!
            </text>
          </svg>
        </div>

        {/* Bottom 3 Concept Cards: Roaring + SIMD + Stall Guard */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 28, flex: 1 }}>
          {[
            {
              pop: s2,
              tag: "CONCEPT 1 · ROARING BITMAPS",
              title: "Range-Compressed ID Sets",
              metric: "1 pair: [start, end]",
              body: "Instead of storing 500 individual integer IDs in memory, a Roaring RunContainer stores one compact start-to-end range — shrinking permission masks to bytes.",
              col: COLORS.cyan,
            },
            {
              pop: s2,
              tag: "CONCEPT 2 · SIMD SCANNING",
              title: "Dozens of Ops Per CPU Tick",
              metric: "100% recall · 0.05–0.11 ms",
              body: "SIMD (Single Instruction, Multiple Data) multiplies dozens of quantized int8 vector numbers in one hardware cycle, then reranks top hits in exact FP32.",
              col: COLORS.emerald,
            },
            {
              pop: s3,
              tag: "CONCEPT 3 · LOCAL-STALL GUARD",
              title: "Automatic Circuit Breaker",
              metric: "97.2% recall · 0.35 ms",
              body: "Even if Maya can see 2% of docs, her allowed folders might be far from the query. The Stall Guard detects dead-end graph hops live and escalates straight into SIMD.",
              col: COLORS.amber,
            },
          ].map((c) => (
            <div
              key={c.tag}
              style={{
                background: COLORS.card,
                border: `2px solid ${c.col}66`,
                borderRadius: 22,
                padding: 28,
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                opacity: c.pop,
                transform: `translateY(${(1 - c.pop) * 32}px)`,
              }}
            >
              <div>
                <div style={{ fontFamily: FONT_MONO, fontSize: 15, fontWeight: 800, color: c.col }}>{c.tag}</div>
                <div style={{ fontSize: 28, fontWeight: 800, marginTop: 8 }}>{c.title}</div>
                <div style={{ fontSize: 19, color: COLORS.muted, marginTop: 12, lineHeight: 1.42 }}>{c.body}</div>
              </div>
              <div style={{ background: "#081226", border: `1.5px solid ${c.col}55`, borderRadius: 12, padding: "12px 16px", fontFamily: FONT_MONO, fontSize: 20, fontWeight: 900, color: c.col }}>
                {c.metric}
              </div>
            </div>
          ))}
        </div>
      </div>
    </OnbShell>
  );
};
