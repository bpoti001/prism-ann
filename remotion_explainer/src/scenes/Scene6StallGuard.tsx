import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { METRICS } from "../data";
import { COLORS, FONT_MONO, SceneShell, usePop } from "../theme";

export const Scene6StallGuard: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const frame = useCurrentFrame();
  const stallFlash = interpolate(Math.sin(frame * 0.25), [-1, 1], [0.4, 1]);
  const tripPop = usePop(210);
  const recoverPop = usePop(310);
  const rightPop = usePop(420);

  const recallJump = interpolate(frame, [300, 380], [METRICS.h3QuoraFarFaiss, METRICS.h3QuoraFarGuard], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <SceneShell
      step="06 · NEGATIVE-CORRELATION LOCAL-STALL GUARD (H3v3)"
      title="Circuit-Breaker Protection for Depleted Pockets (r ≤ 0.5)"
      subtitle="3-stage C++ guard (Hop-1 / Hop-16 / Post-Loop) escalates stalled queries to NEON Mode 3 when N_cand ≤ 25k"
      sceneIdx={6}
      totalScenes={8}
      durationInFrames={durationInFrames}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 36, height: "100%" }}>
        {/* Left: Depleted Pocket Circuit Breaker */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${tripPop > 0.3 ? COLORS.emerald : COLORS.coral}`,
            borderRadius: 24,
            padding: 34,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontFamily: FONT_MONO, fontSize: 18, fontWeight: 800, color: COLORS.coral }}>
              HARD REGIME · DEPLETED POCKET (r ≤ 0.5, S ≈ 2%)
            </div>
            <div
              style={{
                fontFamily: FONT_MONO,
                fontSize: 17,
                fontWeight: 800,
                padding: "6px 14px",
                borderRadius: 99,
                background: tripPop > 0.3 ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.2)",
                color: tripPop > 0.3 ? COLORS.emerald : COLORS.coral,
                opacity: tripPop > 0.3 ? 1 : stallFlash,
              }}
            >
              {tripPop > 0.3 ? "⚡ ESCALATED TO NEON MODE 3" : "⚠ HOP-1 STALLED (s_loc < 0.04)"}
            </div>
          </div>

          {/* 3-Stage Circuit Breaker Flow */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginTop: 18 }}>
            {[
              { t: "Stage A · Hop 1", d: "ep unauth & s_loc < 0.04" },
              { t: "Stage B · Hop 16", d: "early_mean < 0.04 or < k" },
              { t: "Stage C · Post-Loop", d: "n_auth < k or mean < 0.04" },
            ].map((st) => (
              <div
                key={st.t}
                style={{
                  background: "#070E20",
                  border: `1.5px solid ${COLORS.amber}66`,
                  borderRadius: 14,
                  padding: 16,
                }}
              >
                <div style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 800, color: COLORS.amber }}>{st.t}</div>
                <div style={{ fontSize: 16, color: COLORS.muted, marginTop: 6 }}>{st.d}</div>
              </div>
            ))}
          </div>

          {/* Animated Recall Jump */}
          <div style={{ marginTop: 22, background: "#070E20", borderRadius: 18, padding: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
              <span style={{ fontSize: 22, fontWeight: 700, color: COLORS.muted }}>Quora Recall@10 (r ≤ 0.5)</span>
              <span style={{ fontFamily: FONT_MONO, fontSize: 64, fontWeight: 900, color: COLORS.emerald }}>
                {recallJump.toFixed(2)}%
              </span>
            </div>
            <div style={{ height: 18, background: "#1E293B", borderRadius: 99, overflow: "hidden", marginTop: 14 }}>
              <div style={{ width: `${recallJump}%`, height: "100%", background: `linear-gradient(90deg, ${COLORS.coral}, ${COLORS.amber}, ${COLORS.emerald})` }} />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontFamily: FONT_MONO, fontSize: 17, color: COLORS.muted, marginTop: 14 }}>
              <span>FAISS: {METRICS.h3QuoraFarFaiss}%</span>
              <span>v3-geom: {METRICS.h3QuoraFarGeom}%</span>
              <span style={{ color: COLORS.emerald, fontWeight: 800 }}>
                Guard: {METRICS.h3QuoraFarGuard}% ({METRICS.h3QuoraFarGuardMs} ms)
              </span>
            </div>
          </div>

          <div
            style={{
              opacity: recoverPop,
              fontSize: 20,
              color: COLORS.cyan,
              fontWeight: 700,
              marginTop: 12,
            }}
          >
            NQ Wiki: {METRICS.h3NqFarGuard}% in {METRICS.h3NqFarGuardMs} ms · 131×–193× faster than hnswlib ({METRICS.h3QuoraFarHnswMs} ms)!
          </div>
        </div>

        {/* Right: Enriched Pocket 1-Hop Fast Path */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${COLORS.blue}66`,
            borderRadius: 24,
            padding: 34,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            opacity: Math.max(0.25, rightPop),
            transform: `translateY(${(1 - rightPop) * 32}px)`,
          }}
        >
          <div>
            <div style={{ fontFamily: FONT_MONO, fontSize: 18, fontWeight: 800, color: COLORS.cyan }}>
              EASY REGIME · ENRICHED POCKET (r ≥ 2.0)
            </div>
            <div style={{ fontSize: 30, fontWeight: 800, marginTop: 12 }}>
              Zero Penalty on High-Correlation Queries
            </div>
            <p style={{ fontSize: 21, color: COLORS.muted, marginTop: 14, lineHeight: 1.45 }}>
              When POPCNT detects local survival Ŝ_loc(v) ≥ 0.55, ACORN-GLS skips 2-hop and express bridges entirely, staying on the pure 1-hop fast path.
            </p>
          </div>

          <div style={{ background: "#070E20", borderRadius: 18, padding: 26, textAlign: "center" }}>
            <div style={{ fontFamily: FONT_MONO, fontSize: 74, fontWeight: 900, color: COLORS.cyan }}>
              {METRICS.h3QuoraNearEvalRatio}×
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, color: COLORS.white }}>Fewer Distance Evaluations</div>
            <div style={{ fontSize: 18, color: COLORS.muted, marginTop: 8 }}>
              Quora: 3.82× (750 vs 2,864) · NQ: 3.11× within −0.99 pt R@10
            </div>
          </div>

          <div
            style={{
              padding: "16px 20px",
              borderRadius: 14,
              background: "rgba(16,185,129,0.12)",
              border: `1px solid ${COLORS.emerald}55`,
              fontFamily: FONT_MONO,
              fontSize: 18,
              color: COLORS.emerald,
              fontWeight: 700,
            }}
          >
            False Guard Escalations: Only 1.3% (Quora) · 2.8% (NQ)
          </div>
        </div>
      </div>
    </SceneShell>
  );
};
