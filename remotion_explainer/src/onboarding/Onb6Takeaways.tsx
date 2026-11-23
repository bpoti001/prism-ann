import React from "react";
import { COLORS, FONT_MONO } from "../theme";
import { OnbShell, useOnbPop } from "./OnbShell";

export const Onb6Takeaways: React.FC = () => {
  const k1 = useOnbPop(18);
  const k2 = useOnbPop(65);
  const k3 = useOnbPop(112);
  const k4 = useOnbPop(160);
  const banner = useOnbPop(215);

  const cards = [
    {
      pop: k1,
      tag: "01 · SECURITY INVARIANT",
      stat: "0 Leaks",
      title: "Exact Permissions Always",
      body: "0 false positives & 0 false negatives verified across 169,810 logged queries and 1,200 principals.",
      col: COLORS.emerald,
    },
    {
      pop: k2,
      tag: "02 · MUTABLE ACCESS",
      stat: "67 ms",
      title: "Zero-Write Revocation",
      body: "Deleting 1 SpiceDB edge revokes 153k chunks instantly (2,666× faster than pgvector's 179.4 s lock).",
      col: COLORS.cyan,
    },
    {
      pop: k3,
      tag: "03 · SPEED & ACCURACY",
      stat: "97–100%",
      title: "Sub-ms Recall at 0.1%",
      body: "Bridged H-HNSW + Local-Stall Guard + ARM NEON SIMD return top-k in 0.05–0.35 ms.",
      col: COLORS.blue,
    },
    {
      pop: k4,
      tag: "04 · HONEST TRADE-OFF",
      stat: "+1.9% / +24.8%",
      title: "Know the RAM Budget",
      body: "Shortcut bridges add only +1.9% graph RAM; keeping an int8 buffer for Mode-3 SIMD adds +24.8% RAM.",
      col: COLORS.amber,
    },
  ];

  return (
    <OnbShell
      step="06 · KEY TAKEAWAYS & PRODUCTION TRADE-OFFS"
      title="Four Things to Remember as You Ship Code Here"
      subtitle="Our core invariants, honest memory costs, and your Day-1 onboarding next step"
      sceneIdx={6}
      totalScenes={6}
    >
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", height: "100%" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 26, marginTop: 18 }}>
          {cards.map((c) => (
            <div
              key={c.tag}
              style={{
                background: COLORS.card,
                border: `2px solid ${c.col}77`,
                borderRadius: 24,
                padding: 28,
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                height: 490,
                opacity: c.pop,
                transform: `translateY(${(1 - c.pop) * 36}px)`,
              }}
            >
              <div>
                <div style={{ fontFamily: FONT_MONO, fontSize: 14, fontWeight: 800, color: c.col, letterSpacing: 1.5 }}>{c.tag}</div>
                <div style={{ fontFamily: FONT_MONO, fontSize: 38, fontWeight: 900, color: COLORS.white, marginTop: 14 }}>{c.stat}</div>
                <div style={{ fontSize: 25, fontWeight: 800, color: c.col, marginTop: 8 }}>{c.title}</div>
              </div>
              <div style={{ fontSize: 19, color: COLORS.muted, lineHeight: 1.45 }}>{c.body}</div>
            </div>
          ))}
        </div>

        <div
          style={{
            background: "linear-gradient(90deg, rgba(16,185,129,0.2), rgba(34,211,238,0.18), rgba(59,130,246,0.2))",
            border: `2.5px solid ${COLORS.emerald}`,
            borderRadius: 24,
            padding: "28px 40px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            opacity: banner,
            transform: `scale(${0.95 + banner * 0.05})`,
          }}
        >
          <div>
            <div style={{ fontSize: 32, fontWeight: 900 }}>Mental Model: Co-Design Permissions, Graphs &amp; RAM Together</div>
            <div style={{ fontSize: 20, color: COLORS.muted, marginTop: 6 }}>
              Day-1 Next Step: Run the pytest suite and trace one UBP → Roaring → Stall Guard query end-to-end.
            </div>
          </div>
          <div style={{ fontFamily: FONT_MONO, fontSize: 22, fontWeight: 900, color: COLORS.emerald, background: "#06231D", border: `2px solid ${COLORS.emerald}`, borderRadius: 16, padding: "14px 26px" }}>
            WELCOME ABOARD!
          </div>
        </div>
      </div>
    </OnbShell>
  );
};
