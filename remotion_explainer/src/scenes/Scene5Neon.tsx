import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { METRICS } from "../data";
import { COLORS, FONT_MONO, SceneShell, usePop } from "../theme";

// 24 visual memory blocks showing scattered random IDs morphing into sorted Z-order contiguous spans!
const BLOCKS = Array.from({ length: 24 }, (_, idx) => {
  const folder = idx % 4; // 0=authorized green, 1,2,3=other folders
  const sortedPos = folder * 6 + Math.floor(idx / 4);
  return { idx, folder, sortedPos };
});

const FOLDER_COLORS = [COLORS.emerald, "#334155", "#1E3A5F", "#312E81"];

export const Scene5Neon: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const frame = useCurrentFrame();

  // Phase A (60..190): Sort blocks into contiguous Z-order!
  const sortProgress = interpolate(frame, [60, 185], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const runBracket = usePop(215);
  // Phase B (260..460): Glowing ARM NEON vdotq_s32 SIMD beam sweeps across the 6 green contiguous blocks!
  const scanPct = interpolate(frame, [260, 440], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const kpiPop = usePop(460);

  return (
    <SceneShell
      step="05 · Z-ORDER CRoaring & ARMv8.2-A NEON MODE 3"
      title="Zero Scatter-Gather. 64 int8 MACs per SIMD Iteration."
      subtitle="Lexicographic (Anc(v), Magnet) Z-ordering collapses UBP tokens into contiguous RunContainers"
      sceneIdx={5}
      totalScenes={8}
      durationInFrames={durationInFrames}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 30 }}>
        {/* Top Interactive Memory Sort & SIMD Wave Stage */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${COLORS.cardBorder}`,
            borderRadius: 24,
            padding: 34,
            position: "relative",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 18 }}>
            <div style={{ fontFamily: FONT_MONO, fontSize: 19, fontWeight: 700, color: sortProgress > 0.8 ? COLORS.emerald : COLORS.amber }}>
              {sortProgress < 0.2
                ? "BEFORE: Random Document IDs (Scattered Cache Misses)"
                : sortProgress < 0.95
                ? "SORTING BY LEXICOGRAPHIC Z-ORDER: (Anc(v_i), Meaning Magnet)..."
                : "AFTER: Contiguous CRoaring RunContainer [0, 5234) → Streaming ARM NEON vdotq_s32"}
            </div>
            <div style={{ fontFamily: FONT_MONO, fontSize: 18, color: COLORS.cyan }}>
              4-WAY UNROLLED vdotq_s32 + TOP-4k FP32 RERANK
            </div>
          </div>

          <svg viewBox="0 0 1700 220" width="100%" height="220">
            {BLOCKS.map((b) => {
              const xStart = 20 + b.idx * 69;
              const xEnd = 20 + b.sortedPos * 69;
              const x = interpolate(sortProgress, [0, 1], [xStart, xEnd]);
              const isAuth = b.folder === 0;
              const isScanned = isAuth && scanPct > (b.sortedPos + 0.5) / 6;
              return (
                <g key={b.idx}>
                  <rect
                    x={x}
                    y={48}
                    width={58}
                    height={88}
                    rx={10}
                    fill={isScanned ? "#10B981" : FOLDER_COLORS[b.folder]}
                    stroke={isAuth ? COLORS.cyan : "#475569"}
                    strokeWidth={isAuth ? 3 : 1.5}
                    opacity={isAuth ? 1 : 0.45}
                  />
                  <text x={x + 29} y={98} textAnchor="middle" fill={COLORS.white} fontSize="16" fontWeight="800" fontFamily={FONT_MONO}>
                    {isAuth ? `A${b.sortedPos}` : `X${b.idx}`}
                  </text>
                </g>
              );
            })}

            {/* Contiguous RunContainer Bracket */}
            {runBracket > 0.1 && (
              <g opacity={runBracket}>
                <path d="M 20 150 L 20 172 L 424 172 L 424 150" fill="none" stroke={COLORS.emerald} strokeWidth="4" />
                <text x="20" y="202" textAnchor="start" fill={COLORS.emerald} fontSize="20" fontWeight="800" fontFamily={FONT_MONO}>
                  RunContainer [start, end) · Zero-Copy Span
                </text>
              </g>
            )}

            {/* Moving Neon SIMD Beam */}
            {scanPct > 0.01 && scanPct < 0.99 && (
              <rect
                x={20 + scanPct * 380}
                y={30}
                width={32}
                height={122}
                rx={8}
                fill="rgba(34,211,238,0.45)"
                stroke={COLORS.cyan}
                strokeWidth="3"
              />
            )}
          </svg>
        </div>

        {/* Bottom 3 Big Proof Cards */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 28,
            opacity: Math.max(0.25, kpiPop),
            transform: `translateY(${(1 - kpiPop) * 30}px)`,
          }}
        >
          <div style={{ background: COLORS.card, border: `2px solid ${COLORS.emerald}66`, borderRadius: 22, padding: 30 }}>
            <div style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 700, color: COLORS.emerald }}>EXACTNESS AT S ≤ 1%</div>
            <div style={{ fontFamily: FONT_MONO, fontSize: 64, fontWeight: 900, color: COLORS.emerald, marginTop: 10 }}>
              100.00%
            </div>
            <div style={{ fontSize: 20, color: COLORS.muted, marginTop: 8 }}>
              Recall@10 on both BEIR Quora (523k) &amp; BEIR NQ Wikipedia (250k) — 0 leaks.
            </div>
          </div>
          <div style={{ background: COLORS.card, border: `2px solid ${COLORS.cyan}66`, borderRadius: 22, padding: 30 }}>
            <div style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 700, color: COLORS.cyan }}>NATIVE KERNEL SPEED</div>
            <div style={{ fontFamily: FONT_MONO, fontSize: 64, fontWeight: 900, color: COLORS.cyan, marginTop: 10 }}>
              {METRICS.h2NqS001V3FullMs}–0.11 ms
            </div>
            <div style={{ fontSize: 20, color: COLORS.muted, marginTop: 8 }}>
              Up to 30.8× faster than Accelerate BLAS brute force (zero Python scatter-gather).
            </div>
          </div>
          <div style={{ background: COLORS.card, border: `2px solid ${COLORS.blue}66`, borderRadius: 22, padding: 30 }}>
            <div style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 700, color: COLORS.blue }}>END-TO-END WITH PG17 RPC</div>
            <div style={{ fontFamily: FONT_MONO, fontSize: 64, fontWeight: 900, color: COLORS.blue, marginTop: 10 }}>
              ~3.6 ms
            </div>
            <div style={{ fontSize: 20, color: COLORS.muted, marginTop: 8 }}>
              Still 5.5×–41× faster than hnswlib (20–147 ms) &amp; pgvector (22–68 ms) end-to-end.
            </div>
          </div>
        </div>
      </div>
    </SceneShell>
  );
};
