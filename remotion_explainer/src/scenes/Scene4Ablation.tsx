import React from "react";
import { METRICS } from "../data";
import { COLORS, FONT_MONO, SceneShell, usePop } from "../theme";

export const Scene4Ablation: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const b1 = usePop(30);
  const b2 = usePop(120);
  const b3 = usePop(230);
  const badge = usePop(330);

  return (
    <SceneShell
      step="04 · CAUSAL ABLATION PROOF (EXPERIMENT H5v3)"
      title="Bridges — Not Entry Portals — Drive 100%+ of the Recall Lift"
      subtitle="4-way controlled isolation on the exact same 522,931-node FAISS M=16 base graph (3 seeds ± 95% CI)"
      sceneIdx={4}
      totalScenes={8}
      durationInFrames={durationInFrames}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 32, marginTop: 18 }}>
        {METRICS.h5Bars.map((group) => (
          <div
            key={group.s}
            style={{
              background: COLORS.card,
              border: `2px solid ${COLORS.cardBorder}`,
              borderRadius: 24,
              padding: 30,
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              height: 540,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ fontFamily: FONT_MONO, fontSize: 28, fontWeight: 900, color: COLORS.white }}>
                S = {group.s}
              </div>
              <div
                style={{
                  fontFamily: FONT_MONO,
                  fontSize: 18,
                  fontWeight: 800,
                  color: COLORS.emerald,
                  background: "rgba(16,185,129,0.16)",
                  padding: "6px 14px",
                  borderRadius: 99,
                  opacity: badge,
                }}
              >
                {group.retained}% retained
              </div>
            </div>

            {/* Animated Vertical Bar Group */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr 1fr 1fr",
                gap: 16,
                alignItems: "end",
                height: 350,
                paddingTop: 24,
                borderBottom: `2px solid ${COLORS.cardBorder}`,
              }}
            >
              {[
                { lbl: "FAISS", val: group.faiss, col: "#64748B", p: b1 },
                { lbl: "+4 Portals", val: group.faiss4p, col: COLORS.amber, p: b2 },
                { lbl: "v3 +4P", val: group.v3geom, col: COLORS.blue, p: b3 },
                { lbl: "v3 (0P)", val: group.v3noportal, col: COLORS.emerald, p: b3 },
              ].map((bar) => (
                <div key={bar.lbl} style={{ display: "flex", flexDirection: "column", alignItems: "center", height: "100%", justifyContent: "flex-end" }}>
                  <div style={{ fontFamily: FONT_MONO, fontSize: 18, fontWeight: 800, color: bar.col, marginBottom: 8 }}>
                    {(bar.val * bar.p).toFixed(1)}%
                  </div>
                  <div
                    style={{
                      width: "82%",
                      height: `${Math.max(3, bar.val * bar.p * 2.9)}px`,
                      background: bar.col,
                      borderRadius: "10px 10px 0 0",
                    }}
                  />
                </div>
              ))}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 10, textAlign: "center", fontSize: 15, fontWeight: 700, color: COLORS.muted }}>
              <span>FAISS</span>
              <span style={{ color: COLORS.amber }}>+4 Portals</span>
              <span style={{ color: COLORS.blue }}>v3 +4P</span>
              <span style={{ color: COLORS.emerald }}>v3 (0P)</span>
            </div>
          </div>
        ))}
      </div>

      {/* Verdict Strip */}
      <div
        style={{
          marginTop: 32,
          background: "rgba(16,185,129,0.14)",
          border: `2px solid ${COLORS.emerald}`,
          borderRadius: 18,
          padding: "20px 32px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          opacity: badge,
          transform: `translateY(${(1 - badge) * 20}px)`,
        }}
      >
        <div style={{ fontSize: 24, fontWeight: 800 }}>
          Zero-Portal <span style={{ color: COLORS.emerald }}>hhnsw-v2-geom-M8-noportal</span> retains 101.0%–102.3% of the gain — Portals alone add ≤ +0.62 pt.
        </div>
        <div style={{ fontFamily: FONT_MONO, fontSize: 20, fontWeight: 800, color: COLORS.emerald }}>
          PREDICTION P5: SUPPORTED ✓
        </div>
      </div>
    </SceneShell>
  );
};
