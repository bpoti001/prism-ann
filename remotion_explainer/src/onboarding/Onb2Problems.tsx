import React from "react";
import { COLORS, FONT_MONO } from "../theme";
import { OnbShell, useOnbPop } from "./OnbShell";

export const Onb2Problems: React.FC = () => {
  const c1 = useOnbPop(18);
  const c2 = useOnbPop(105);
  const c3 = useOnbPop(195);

  const traps = [
    {
      pop: c1,
      tag: "TRAP 01 · SPICEDB PRE-FILTERING",
      title: "Leaf-Set Explosion",
      analogy: "Analogy: Listing every desk in a skyscraper instead of saying 'Floor 4'",
      stat: "98.3 ms",
      statLabel: "wasted BEFORE vector search starts",
      desc: "Asking SpiceDB for every individual leaf file Maya can read forces a deep walk down the folder tree and streams thousands of doc IDs over gRPC.",
      col: COLORS.coral,
      svg: (
        <svg viewBox="0 0 440 160" width="100%" height="160">
          <rect x="155" y="10" width="130" height="34" rx="8" fill="#1E3A8A" stroke={COLORS.blue} strokeWidth="2" />
          <text x="220" y="32" textAnchor="middle" fill={COLORS.white} fontSize="14" fontWeight="800">Engineering</text>
          {[45, 115, 185, 255, 325, 395].map((x) => (
            <React.Fragment key={x}>
              <line x1="220" y1="44" x2={x} y2="108" stroke={COLORS.coral} strokeWidth="2" strokeDasharray="4 4" />
              <rect x={x - 24} y="108" width="48" height="34" rx="6" fill="#450A0A" stroke={COLORS.coral} strokeWidth="2" />
              <text x={x} y="129" textAnchor="middle" fill="#FCA5A5" fontSize="12" fontFamily={FONT_MONO}>doc</text>
            </React.Fragment>
          ))}
        </svg>
      ),
    },
    {
      pop: c2,
      tag: "TRAP 02 · FILTERED HNSW",
      title: "Getting Stranded on an Island",
      analogy: "Analogy: Driving a highway when 99.9% of towns are roadblocked",
      stat: "5.75%",
      statLabel: "FAISS recall at 0.1% visibility",
      desc: "HNSW hops neighbor-to-neighbor. When 99.9% of neighbors are forbidden, the search hits dead ends immediately and misses the true answers.",
      col: COLORS.amber,
      svg: (
        <svg viewBox="0 0 440 160" width="100%" height="160">
          {[
            [60, 80, true],
            [140, 45, false],
            [155, 118, false],
            [230, 75, false],
            [305, 48, false],
            [315, 120, false],
            [382, 80, true],
          ].map(([x, y, ok], i) => (
            <circle
              key={i}
              cx={x as number}
              cy={y as number}
              r={ok ? 18 : 13}
              fill={ok ? "#065F46" : "#7F1D1D"}
              stroke={ok ? COLORS.emerald : COLORS.coral}
              strokeWidth="2.5"
            />
          ))}
          <line x1="78" y1="74" x2="127" y2="50" stroke={COLORS.coral} strokeWidth="2.5" strokeDasharray="5 4" />
          <line x1="78" y1="86" x2="142" y2="114" stroke={COLORS.coral} strokeWidth="2.5" strokeDasharray="5 4" />
          <text x="60" y="122" textAnchor="middle" fill={COLORS.amber} fontSize="13" fontWeight="800">STRANDED</text>
          <text x="382" y="122" textAnchor="middle" fill={COLORS.emerald} fontSize="13" fontWeight="800">TARGET</text>
        </svg>
      ),
    },
    {
      pop: c3,
      tag: "TRAP 03 · INLINE SQL ACLs",
      title: "Revocation Rewrite Storm",
      analogy: "Analogy: Reprinting 153,000 ID cards whenever 1 person changes teams",
      stat: "179.4 s",
      statLabel: "pgvector stall on 1 folder revoke",
      desc: "Copying allowed user IDs onto every Postgres vector row avoids tree walks — until revoking one department locks and rewrites 153k rows.",
      col: COLORS.coral,
      svg: (
        <svg viewBox="0 0 440 160" width="100%" height="160">
          {[18, 56, 94].map((y, idx) => (
            <React.Fragment key={y}>
              <rect x="20" y={y} width="400" height="30" rx="7" fill="#450A0A" stroke={COLORS.coral} strokeWidth="2" />
              <text x="36" y={y + 20} fill="#FCA5A5" fontSize="13" fontFamily={FONT_MONO}>
                UPDATE vectors SET acl = ...  [ROW LOCK #{idx + 1}]
              </text>
            </React.Fragment>
          ))}
          <text x="220" y="148" textAnchor="middle" fill={COLORS.coral} fontSize="14" fontWeight="800" fontFamily={FONT_MONO}>
            153,000 ROWS REWRITTEN · ~3 MIN LOCK
          </text>
        </svg>
      ),
    },
  ];

  return (
    <OnbShell
      step="02 · WHY NAIVE APPROACHES FAIL"
      title="The 3 Core Traps When Combining Permissions & Vector Search"
      subtitle="Every standard workaround fixes one bottleneck while triggering a disaster somewhere else"
      sceneIdx={2}
      totalScenes={6}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 30, height: "100%" }}>
        {traps.map((t) => (
          <div
            key={t.tag}
            style={{
              background: COLORS.card,
              border: `2px solid ${t.col}66`,
              borderRadius: 24,
              padding: 28,
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              opacity: t.pop,
              transform: `translateY(${(1 - t.pop) * 38}px)`,
            }}
          >
            <div>
              <div style={{ fontFamily: FONT_MONO, fontSize: 15, fontWeight: 800, color: t.col, letterSpacing: 1.5 }}>{t.tag}</div>
              <div style={{ fontSize: 30, fontWeight: 800, marginTop: 8 }}>{t.title}</div>
              <div style={{ fontSize: 17, color: COLORS.cyan, marginTop: 8, fontWeight: 600 }}>{t.analogy}</div>
            </div>

            {t.svg}

            <div style={{ background: "#081226", border: `1.5px solid ${t.col}55`, borderRadius: 16, padding: "16px 20px" }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
                <span style={{ fontFamily: FONT_MONO, fontSize: 34, fontWeight: 900, color: t.col }}>{t.stat}</span>
                <span style={{ fontSize: 16, color: COLORS.white, fontWeight: 700 }}>{t.statLabel}</span>
              </div>
              <div style={{ fontSize: 18, color: COLORS.muted, marginTop: 10, lineHeight: 1.4 }}>{t.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </OnbShell>
  );
};
