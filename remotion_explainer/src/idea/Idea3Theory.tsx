import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { COLORS, FONT_MONO } from "../theme";
import { IdeaShell, useIdeaPop } from "./IdeaShell";

export const Idea3Theory: React.FC = () => {
  const frame = useCurrentFrame();
  const p1 = useIdeaPop(20);
  const p2 = useIdeaPop(110);
  const p3 = useIdeaPop(200);
  const sortT = interpolate(frame, [215, 290], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <IdeaShell
      step="03 · THEORETICAL CORE (BEFORE SYSTEM DESIGN)"
      title="Three Mathematical Pillars Co-Designed From First Principles"
      subtitle="Bounding authorization tokens, shifting the HNSW percolation cliff, and aligning memory to hardware"
      sceneIdx={3}
      totalScenes={5}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 30, height: "100%" }}>
        {/* Pillar 1: Theorem 1 UBP */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${COLORS.emerald}66`,
            borderRadius: 24,
            padding: 28,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            opacity: p1,
            transform: `translateY(${(1 - p1) * 34}px)`,
          }}
        >
          <div>
            <div style={{ fontFamily: FONT_MONO, fontSize: 15, fontWeight: 800, color: COLORS.emerald }}>
              PILLAR 1 · THEOREM 1 (EXACT GRAPH CUT)
            </div>
            <div style={{ fontSize: 27, fontWeight: 800, marginTop: 8 }}>Subtractive Upward Boundary Pruning</div>
          </div>

          <svg viewBox="0 0 460 220" width="100%" height="220">
            <line x1="230" y1="36" x2="115" y2="105" stroke="#475569" strokeWidth="2.5" />
            <line x1="230" y1="36" x2="345" y2="105" stroke={COLORS.amber} strokeWidth="4" strokeDasharray="8 5" />
            <line x1="345" y1="105" x2="285" y2="180" stroke="#475569" strokeWidth="2.5" />
            <line x1="345" y1="105" x2="405" y2="180" stroke={COLORS.amber} strokeWidth="4" strokeDasharray="8 5" />

            <rect x="165" y="16" width="130" height="38" rx="10" fill="#451A03" stroke={COLORS.amber} strokeWidth="2.5" />
            <text x="230" y="40" textAnchor="middle" fill={COLORS.white} fontSize="15" fontWeight="700">Root (Tainted)</text>

            <rect x="42" y="86" width="146" height="40" rx="10" fill="#064E3B" stroke={COLORS.emerald} strokeWidth="3" />
            <text x="115" y="111" textAnchor="middle" fill={COLORS.white} fontSize="15" fontWeight="800">Halt! Untainted</text>

            <rect x="275" y="86" width="140" height="40" rx="10" fill="#451A03" stroke={COLORS.amber} strokeWidth="2.5" />
            <text x="345" y="111" textAnchor="middle" fill={COLORS.white} fontSize="15" fontWeight="700">Split Ancestor</text>

            <rect x="235" y="162" width="96" height="36" rx="9" fill="#064E3B" stroke={COLORS.emerald} strokeWidth="2.5" />
            <text x="283" y="185" textAnchor="middle" fill={COLORS.white} fontSize="14" fontWeight="700">Emit OK</text>

            <rect x="355" y="162" width="96" height="36" rx="9" fill="#450A0A" stroke={COLORS.coral} strokeWidth="2.5" />
            <text x="403" y="185" textAnchor="middle" fill={COLORS.white} fontSize="14" fontWeight="800">DENY</text>
          </svg>

          <div style={{ background: "#070E20", borderRadius: 14, padding: 18 }}>
            <div style={{ fontFamily: FONT_MONO, fontSize: 22, fontWeight: 800, color: COLORS.emerald }}>
              |T_UBP+| ≤ k0 + m(b − 1)L
            </div>
            <div style={{ fontSize: 17, color: COLORS.muted, marginTop: 8, lineHeight: 1.35 }}>
              Linear in tree depth L (not exponential b^L), exact set equivalence (0 FP / 0 FN), and O(1) zero-write revocation.
            </div>
          </div>
        </div>

        {/* Pillar 2: Conditional Percolation & Semantic Bridges */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${COLORS.blue}66`,
            borderRadius: 24,
            padding: 28,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            opacity: p2,
            transform: `translateY(${(1 - p2) * 34}px)`,
          }}
        >
          <div>
            <div style={{ fontFamily: FONT_MONO, fontSize: 15, fontWeight: 800, color: COLORS.cyan }}>
              PILLAR 2 · CONDITIONAL PERCOLATION
            </div>
            <div style={{ fontSize: 27, fontWeight: 800, marginTop: 8 }}>Container-Scoped Geometric Bridges</div>
          </div>

          <svg viewBox="0 0 460 220" width="100%" height="220">
            <rect x="135" y="25" width="175" height="170" rx="16" fill="rgba(239,68,68,0.08)" stroke="rgba(239,68,68,0.35)" strokeDasharray="6 4" />
            <text x="222" y="50" textAnchor="middle" fill={COLORS.coral} fontSize="14" fontWeight="800">FORBIDDEN GAP</text>
            <path d="M 62 118 Q 222 10 385 118" fill="none" stroke={COLORS.cyan} strokeWidth="5" strokeDasharray="10 5" />
            <path d="M 62 118 Q 222 215 385 118" fill="none" stroke={COLORS.emerald} strokeWidth="4" />
            <circle cx="62" cy="118" r="24" fill="#064E3B" stroke={COLORS.emerald} strokeWidth="3.5" />
            <text x="62" y="123" textAnchor="middle" fill={COLORS.white} fontSize="14" fontWeight="800">v_a</text>
            <circle cx="222" cy="118" r="14" fill="#1E293B" stroke="#64748B" strokeWidth="2" />
            <circle cx="385" cy="118" r="24" fill="#064E3B" stroke={COLORS.emerald} strokeWidth="3.5" />
            <text x="385" y="123" textAnchor="middle" fill={COLORS.white} fontSize="14" fontWeight="800">v_b</text>
          </svg>

          <div style={{ background: "#070E20", borderRadius: 14, padding: 18 }}>
            <div style={{ fontFamily: FONT_MONO, fontSize: 20, fontWeight: 800, color: COLORS.cyan }}>
              S_crit' ≈ S_crit · S_container
            </div>
            <div style={{ fontSize: 17, color: COLORS.muted, marginTop: 8, lineHeight: 1.35 }}>
              Vamana/RNG-diverse semantic bridges inside folders &amp; concepts preserve greedy navigability, gated adaptively by local survival Ŝ_loc(v).
            </div>
          </div>
        </div>

        {/* Pillar 3: Z-Order Hardware Crossover */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${COLORS.violet}66`,
            borderRadius: 24,
            padding: 28,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            opacity: p3,
            transform: `translateY(${(1 - p3) * 34}px)`,
          }}
        >
          <div>
            <div style={{ fontFamily: FONT_MONO, fontSize: 15, fontWeight: 800, color: COLORS.violet }}>
              PILLAR 3 · MEMORY-HARDWARE CROSSOVER
            </div>
            <div style={{ fontSize: 27, fontWeight: 800, marginTop: 8 }}>Lexicographic Z-Order &amp; SIMD Crossover</div>
          </div>

          <svg viewBox="0 0 460 220" width="100%" height="220">
            {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => {
              const isAuth = i % 2 === 0;
              const targetIdx = isAuth ? i / 2 : 4 + Math.floor(i / 2);
              const x = interpolate(sortT, [0, 1], [22 + i * 52, 22 + targetIdx * 52]);
              return (
                <rect
                  key={i}
                  x={x}
                  y={66}
                  width={42}
                  height={64}
                  rx={8}
                  fill={isAuth ? COLORS.emerald : "#1E293B"}
                  stroke={isAuth ? COLORS.cyan : "#475569"}
                  strokeWidth={2.5}
                />
              );
            })}
            <path d="M 22 146 L 22 162 L 220 162 L 220 146" fill="none" stroke={COLORS.emerald} strokeWidth="3.5" opacity={sortT} />
            <text x="121" y="190" textAnchor="middle" fill={COLORS.emerald} fontSize="15" fontWeight="800" fontFamily={FONT_MONO} opacity={sortT}>
              Contiguous Interval [s, e)
            </text>
          </svg>

          <div style={{ background: "#070E20", borderRadius: 14, padding: 18 }}>
            <div style={{ fontFamily: FONT_MONO, fontSize: 20, fontWeight: 800, color: COLORS.violet }}>
              N_cand ≤ κ · E_graph ⇒ SIMD Scan
            </div>
            <div style={{ fontSize: 17, color: COLORS.muted, marginTop: 8, lineHeight: 1.35 }}>
              Sorting IDs by (Anc(v_i), Concept) eliminates scatter-gather, enabling a principled crossover to linear SIMD scanning when sparse or stalled.
            </div>
          </div>
        </div>
      </div>
    </IdeaShell>
  );
};
