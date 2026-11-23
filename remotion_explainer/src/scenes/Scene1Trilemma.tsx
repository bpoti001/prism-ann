import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { METRICS } from "../data";
import { COLORS, FONT_MONO, SceneShell, usePop } from "../theme";

export const Scene1Trilemma: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const frame = useCurrentFrame();
  const c1 = usePop(35);
  const c2 = usePop(130);
  const c3 = usePop(220);
  const banner = usePop(340);

  const spiceVal = interpolate(frame, [45, 110], [0, METRICS.h1PgSpicedbMs], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const faissVal = interpolate(frame, [140, 200], [100, METRICS.h2QuoraS001Faiss], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const revokeVal = interpolate(frame, [230, 310], [0, METRICS.h4PgvSec], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const cards = [
    {
      pop: c1,
      num: "WALL 01",
      title: "SpiceDB Leaf Explosion",
      metric: `${spiceVal.toFixed(1)} ms`,
      sub: "Persistent PG17 LookupResources stall before vector search begins",
      accent: COLORS.coral,
      pct: Math.min(100, (spiceVal / 100) * 100),
    },
    {
      pop: c2,
      num: "WALL 02",
      title: "Sub-1% HNSW Collapse",
      metric: `${faissVal.toFixed(2)}%`,
      sub: "FAISS M=16 Recall@10 when user visibility S = 0.1% (1 in 1,000 docs)",
      accent: COLORS.amber,
      pct: faissVal,
    },
    {
      pop: c3,
      num: "WALL 03",
      title: "Revocation Write Storm",
      metric: `${revokeVal.toFixed(1)} s`,
      sub: "PostgreSQL 17 + pgvector UPDATE across 153,600 vector chunks",
      accent: COLORS.coral,
      pct: Math.min(100, (revokeVal / 180) * 100),
    },
  ];

  return (
    <SceneShell
      step="01 · THE ENTERPRISE REBAC-ANN TRILEMMA"
      title="Half a Million Docs. 0.1% Permitted. Three Hard Walls."
      subtitle="Why standard SpiceDB + HNSW RAG pipelines fail latency, accuracy, or compliance SLAs"
      sceneIdx={1}
      totalScenes={8}
      durationInFrames={durationInFrames}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 36, marginTop: 28 }}>
        {cards.map((c) => (
          <div
            key={c.num}
            style={{
              background: COLORS.card,
              border: `2px solid ${c.accent}55`,
              borderRadius: 24,
              padding: 36,
              transform: `translateY(${(1 - c.pop) * 48}px) scale(${0.92 + c.pop * 0.08})`,
              opacity: c.pop,
            }}
          >
            <div style={{ fontFamily: FONT_MONO, fontSize: 17, fontWeight: 700, color: c.accent, letterSpacing: 2 }}>
              {c.num}
            </div>
            <div style={{ fontSize: 30, fontWeight: 800, marginTop: 10 }}>{c.title}</div>
            <div
              style={{
                fontFamily: FONT_MONO,
                fontSize: 72,
                fontWeight: 900,
                color: c.accent,
                marginTop: 28,
                marginBottom: 18,
              }}
            >
              {c.metric}
            </div>
            <div style={{ height: 12, background: "#1E293B", borderRadius: 99, overflow: "hidden", marginBottom: 22 }}>
              <div style={{ width: `${c.pct}%`, height: "100%", background: c.accent, borderRadius: 99 }} />
            </div>
            <div style={{ fontSize: 21, color: COLORS.muted, lineHeight: 1.4 }}>{c.sub}</div>
          </div>
        ))}
      </div>

      {/* Solution Thesis Banner */}
      <div
        style={{
          marginTop: 48,
          background: "linear-gradient(90deg, rgba(37,99,235,0.22), rgba(16,185,129,0.22))",
          border: `2px solid ${COLORS.emerald}`,
          borderRadius: 22,
          padding: "28px 40px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          transform: `translateY(${(1 - banner) * 32}px)`,
          opacity: banner,
        }}
      >
        <div>
          <div style={{ fontSize: 17, fontWeight: 700, color: COLORS.emerald, letterSpacing: 2 }}>
            THE PRISM-ANN CO-DESIGN BREAKTHROUGH
          </div>
          <div style={{ fontSize: 32, fontWeight: 800, marginTop: 6 }}>
            Co-Design SpiceDB Taint Pruning × Geometric Express Bridges × Native ARM NEON SIMD
          </div>
        </div>
        <div
          style={{
            fontFamily: FONT_MONO,
            fontSize: 22,
            fontWeight: 800,
            color: COLORS.white,
            background: COLORS.emerald,
            padding: "14px 26px",
            borderRadius: 14,
          }}
        >
          0 LEAKS · 11/11 VERIFIED
        </div>
      </div>
    </SceneShell>
  );
};
