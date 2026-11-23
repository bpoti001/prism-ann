import React from "react";
import { COLORS, FONT_MONO } from "../theme";
import { OnbShell, useOnbPop } from "./OnbShell";

export const Onb5QueryFlow: React.FC = () => {
  const f1 = useOnbPop(18);
  const f2 = useOnbPop(85);
  const f3 = useOnbPop(150);
  const tbl = useOnbPop(215);

  return (
    <OnbShell
      step="05 · TRACING ONE LIVE QUERY END-TO-END"
      title="How a Query Moves Through Our Codebase (API → Top-k)"
      subtitle="Recognize every module you'll touch — and why we never post-filter after search"
      sceneIdx={5}
      totalScenes={6}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 26, height: "100%" }}>
        {/* Top Pipeline Flow */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${COLORS.blue}66`,
            borderRadius: 24,
            padding: "26px 30px",
            display: "grid",
            gridTemplateColumns: "0.95fr 34px 1fr 34px 1.65fr",
            alignItems: "center",
          }}
        >
          <div style={{ background: "#081226", border: `2px solid ${COLORS.emerald}`, borderRadius: 16, padding: 22, opacity: f1 }}>
            <div style={{ fontFamily: FONT_MONO, fontSize: 14, color: COLORS.emerald, fontWeight: 800 }}>STEP 1 · CONTROL PLANE</div>
            <div style={{ fontSize: 23, fontWeight: 800, marginTop: 6 }}>SpiceDB + UBP</div>
            <div style={{ fontSize: 17, color: COLORS.muted, marginTop: 8, lineHeight: 1.4 }}>
              Resolves Maya's untainted folder tokens (e.g., <code>Eng/FE</code>) — stopping above leaves in <strong>0.35 ms</strong>.
            </div>
          </div>

          <div style={{ textAlign: "center", fontSize: 28, fontWeight: 900, color: COLORS.cyan, opacity: f2 }}>→</div>

          <div style={{ background: "#081226", border: `2px solid ${COLORS.cyan}`, borderRadius: 16, padding: 22, opacity: f2 }}>
            <div style={{ fontFamily: FONT_MONO, fontSize: 14, color: COLORS.cyan, fontWeight: 800 }}>STEP 2 · BITSET + ROUTER</div>
            <div style={{ fontSize: 23, fontWeight: 800, marginTop: 6 }}>Roaring + Cost Router</div>
            <div style={{ fontSize: 17, color: COLORS.muted, marginTop: 8, lineHeight: 1.4 }}>
              Intersects folders with topic filter into Z-ordered spans and checks candidate count <code>N_cand</code>.
            </div>
          </div>

          <div style={{ textAlign: "center", fontSize: 28, fontWeight: 900, color: COLORS.amber, opacity: f3 }}>→</div>

          <div style={{ display: "flex", flexDirection: "column", gap: 14, opacity: f3 }}>
            <div style={{ background: "#091B2E", border: `2px solid ${COLORS.blue}`, borderRadius: 14, padding: "14px 18px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 20, fontWeight: 800, color: COLORS.cyan }}>Dense Query → Bridged H-HNSW</span>
                <span style={{ fontFamily: FONT_MONO, fontSize: 14, color: COLORS.amber }}>⚡ Stall Guard Watches</span>
              </div>
              <div style={{ fontSize: 16, color: COLORS.muted, marginTop: 4 }}>Fast 1-hop or express bridges; if dead-ended, trips breaker straight down to Mode 3.</div>
            </div>
            <div style={{ background: "#06231D", border: `2px solid ${COLORS.emerald}`, borderRadius: 14, padding: "14px 18px" }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: COLORS.emerald }}>Strict (≤1%) or Stalled → Mode 3 SIMD Scan</div>
              <div style={{ fontSize: 16, color: COLORS.muted, marginTop: 4 }}>Streams contiguous int8 intervals + exact FP32 rerank → <strong>Top-k with 0 leaks</strong>.</div>
            </div>
          </div>
        </div>

        {/* Bottom Comparison Strip: Why Post-Filter vs Naive Pre-Filter Fail */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${COLORS.cardBorder}`,
            borderRadius: 24,
            padding: "24px 30px",
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            opacity: tbl,
            transform: `translateY(${(1 - tbl) * 28}px)`,
          }}
        >
          <div style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 800, color: COLORS.cyan, letterSpacing: 1.5 }}>
            QUICK CHEAT SHEET: WHY OTHER FILTER STRATEGIES HIT TRADE-OFFS
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 20, marginTop: 14, flex: 1 }}>
            {[
              {
                name: "Post-Filtering",
                how: "Search HNSW first, then throw away forbidden docs after.",
                verdict: "✕ Returns 0 results at 0.1% visibility unless over-fetching 10,000+ rows.",
                col: COLORS.coral,
              },
              {
                name: "Naive Pre-Filter",
                how: "Ask SpiceDB for every allowed leaf file, then mask plain HNSW.",
                verdict: "✕ 98.3 ms SpiceDB stall + FAISS strands at 5.75% recall.",
                col: COLORS.coral,
              },
              {
                name: "Inline SQL ACLs",
                how: "Copy allowed user IDs directly onto every pgvector row.",
                verdict: "✕ Revoking 1 folder locks 153k rows for 179.4 seconds.",
                col: COLORS.amber,
              },
              {
                name: "Prism-ANN (Ours)",
                how: "Immutable folder tokens + express bridges + Z-Order SIMD.",
                verdict: "✓ 0.35 ms filter · 67 ms revoke · 97–100% recall · 0 leaks.",
                col: COLORS.emerald,
              },
            ].map((item) => (
              <div key={item.name} style={{ background: "#081226", border: `2px solid ${item.col}66`, borderRadius: 16, padding: 22, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                <div>
                  <div style={{ fontSize: 24, fontWeight: 800, color: COLORS.white }}>{item.name}</div>
                  <div style={{ fontFamily: FONT_MONO, fontSize: 13, fontWeight: 700, color: COLORS.cyan, marginTop: 14 }}>HOW IT WORKS</div>
                  <div style={{ fontSize: 18, color: COLORS.muted, marginTop: 6, lineHeight: 1.4 }}>{item.how}</div>
                </div>
                <div style={{ background: `${item.col}14`, border: `1px solid ${item.col}44`, borderRadius: 12, padding: "12px 14px" }}>
                  <div style={{ fontFamily: FONT_MONO, fontSize: 13, fontWeight: 800, color: item.col }}>PRODUCTION OUTCOME</div>
                  <div style={{ fontSize: 17, fontWeight: 700, color: COLORS.white, marginTop: 6, lineHeight: 1.38 }}>{item.verdict}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </OnbShell>
  );
};
