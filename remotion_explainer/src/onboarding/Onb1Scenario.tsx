import React from "react";
import { COLORS, FONT_MONO } from "../theme";
import { OnbShell, useOnbPop } from "./OnbShell";

export const Onb1Scenario: React.FC = () => {
  const leftPop = useOnbPop(14);
  const treePop = useOnbPop(45);
  const g1 = useOnbPop(110);
  const g2 = useOnbPop(165);
  const g3 = useOnbPop(220);

  return (
    <OnbShell
      step="01 · THE REAL-WORLD SCENARIO"
      title="Welcome Aboard: Why Enterprise AI Search Is Hard"
      subtitle="Maya searches 500,000 company chunks — but can only read 1 in 1,000, with strict DENY walls"
      sceneIdx={1}
      totalScenes={6}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1.12fr 1fr", gap: 36, height: "100%" }}>
        {/* Left: Relatable AI RAG Scenario Visual */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${COLORS.cardBorder}`,
            borderRadius: 24,
            padding: 30,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            opacity: leftPop,
          }}
        >
          {/* Search Bar Mock */}
          <div style={{ background: "#081226", border: `2px solid ${COLORS.cyan}`, borderRadius: 16, padding: "18px 24px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontFamily: FONT_MONO, fontSize: 14, color: COLORS.cyan, fontWeight: 800 }}>USER: MAYA (ASSOCIATE ENGINEER)</div>
              <div style={{ fontSize: 24, fontWeight: 700, marginTop: 4 }}>"Find our Q3 vendor risk memo"</div>
            </div>
            <div style={{ background: "rgba(16,185,129,0.18)", border: `1.5px solid ${COLORS.emerald}`, borderRadius: 12, padding: "10px 16px", textAlign: "center" }}>
              <div style={{ fontFamily: FONT_MONO, fontSize: 14, color: COLORS.emerald, fontWeight: 800 }}>VISIBILITY</div>
              <div style={{ fontSize: 24, fontWeight: 900, color: COLORS.white }}>0.1%</div>
            </div>
          </div>

          {/* Company Drive Tree SVG */}
          <svg viewBox="0 0 820 350" width="100%" height="350" style={{ opacity: treePop }}>
            <line x1="410" y1="68" x2="155" y2="148" stroke="#64748B" strokeWidth="3" />
            <line x1="410" y1="68" x2="410" y2="148" stroke="#64748B" strokeWidth="3" />
            <line x1="410" y1="68" x2="665" y2="148" stroke="#64748B" strokeWidth="3" />

            <line x1="155" y1="196" x2="88" y2="270" stroke={COLORS.emerald} strokeWidth="3.5" />
            <line x1="155" y1="196" x2="232" y2="270" stroke={COLORS.coral} strokeWidth="3.5" strokeDasharray="7 5" />

            <rect x="295" y="18" width="230" height="52" rx="14" fill="#1E293B" stroke={COLORS.blue} strokeWidth="2.5" />
            <text x="410" y="50" textAnchor="middle" fill={COLORS.white} fontSize="20" fontWeight="800">Company Drive (500k)</text>

            <rect x="52" y="144" width="206" height="52" rx="14" fill="#064E3B" stroke={COLORS.emerald} strokeWidth="2.5" />
            <text x="155" y="176" textAnchor="middle" fill={COLORS.white} fontSize="19" fontWeight="800">Engineering ✓</text>

            <rect x="310" y="144" width="200" height="52" rx="14" fill="#450A0A" stroke={COLORS.coral} strokeWidth="2.5" />
            <text x="410" y="176" textAnchor="middle" fill={COLORS.coral} fontSize="19" fontWeight="800">Legal / M&amp;A ✕</text>

            <rect x="565" y="144" width="200" height="52" rx="14" fill="#450A0A" stroke={COLORS.coral} strokeWidth="2.5" />
            <text x="665" y="176" textAnchor="middle" fill={COLORS.coral} fontSize="19" fontWeight="800">HR / Comp ✕</text>

            <rect x="16" y="268" width="150" height="54" rx="12" fill="#065F46" stroke={COLORS.emerald} strokeWidth="2.5" />
            <text x="91" y="301" textAnchor="middle" fill={COLORS.white} fontSize="17" fontWeight="800">Frontend ✓</text>

            <rect x="180" y="268" width="180" height="54" rx="12" fill="#7F1D1D" stroke={COLORS.coral} strokeWidth="3" />
            <text x="270" y="294" textAnchor="middle" fill={COLORS.white} fontSize="16" fontWeight="800">Secret Project</text>
            <text x="270" y="313" textAnchor="middle" fill="#FCA5A5" fontSize="14" fontFamily={FONT_MONO} fontWeight="800">EXPLICIT DENY!</text>

            <rect x="420" y="246" width="376" height="82" rx="16" fill="rgba(239,68,68,0.14)" stroke={COLORS.coral} strokeWidth="2.5" />
            <text x="608" y="280" textAnchor="middle" fill={COLORS.coral} fontSize="20" fontWeight="900">HARD RULE: 0 PERMISSION LEAKS</text>
            <text x="608" y="308" textAnchor="middle" fill={COLORS.muted} fontSize="16">Leaking 1 forbidden paragraph = Sev-0 incident</text>
          </svg>

          <div style={{ background: "#081226", borderRadius: 14, padding: "14px 20px", fontSize: 19, color: COLORS.muted }}>
            <strong style={{ color: COLORS.white }}>Goal:</strong> Return the top-10 closest docs Maya is actually allowed to read — in <strong style={{ color: COLORS.emerald }}>a few milliseconds</strong>.
          </div>
        </div>

        {/* Right: Friendly Day-1 Glossary */}
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", gap: 22 }}>
          <div style={{ fontFamily: FONT_MONO, fontSize: 17, fontWeight: 800, color: COLORS.cyan, letterSpacing: 1.8 }}>
            DAY-1 GLOSSARY (3 TERMS YOU'LL SEE EVERYWHERE)
          </div>
          {[
            {
              pop: g1,
              term: "Embeddings (Vectors)",
              analogy: "GPS coordinates for meaning",
              desc: "An AI model turns every text chunk into a list of numbers (e.g., 384 floats). Similar topics land close together in space.",
              col: COLORS.cyan,
            },
            {
              pop: g2,
              term: "HNSW (Vector Graph Index)",
              analogy: "A multi-layer highway map",
              desc: "Links similar documents together so search hops quickly from broad regions down to exact neighbors — without scanning every row.",
              col: COLORS.blue,
            },
            {
              pop: g3,
              term: "Authorization Graph (SpiceDB)",
              analogy: "A live company org chart + folder tree",
              desc: "Stores who can view which folders via relationships, inheritance, and subtractive DENY walls (ReBAC).",
              col: COLORS.emerald,
            },
          ].map((item) => (
            <div
              key={item.term}
              style={{
                background: COLORS.card,
                border: `2px solid ${item.col}66`,
                borderRadius: 22,
                padding: "22px 26px",
                flex: 1,
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                opacity: item.pop,
                transform: `translateX(${(1 - item.pop) * 38}px)`,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
                <div style={{ fontSize: 26, fontWeight: 800, color: COLORS.white }}>{item.term}</div>
                <div style={{ fontFamily: FONT_MONO, fontSize: 15, fontWeight: 700, color: item.col }}>{item.analogy}</div>
              </div>
              <div style={{ fontSize: 19, color: COLORS.muted, marginTop: 10, lineHeight: 1.4 }}>{item.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </OnbShell>
  );
};
