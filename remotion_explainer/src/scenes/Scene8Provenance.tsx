import React from "react";
import { METRICS } from "../data";
import { COLORS, FONT_MONO, SceneShell, usePop } from "../theme";

export const Scene8Provenance: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const c1 = usePop(30);
  const c2 = usePop(95);
  const c3 = usePop(160);
  const c4 = usePop(225);
  const seal = usePop(330);

  const checks = [
    { pop: c1, label: "Cryptographic Freeze", detail: "FREEZE_v3.md (7/7) & FREEZE.md (5/5) matched; Dev [0..499] strictly disjoint from Test [500..9,984] + NQ 250k." },
    { pop: c2, label: "Bit-for-Bit Raw Provenance", detail: `${METRICS.nRecords.toLocaleString()} raw per-query JSONL logs → recompute_v3 --check MATCH · 0 authorization leaks.` },
    { pop: c3, label: "Honest Engineering Tradeoffs (D9)", detail: "+1.91% RAM graph-only vs. +24.8% with 200.8 MB SQ8 buffer; ~0.823 ms Python mask prep disclosed plainly." },
    { pop: c4, label: "All 3 Verification Brakes Pass", detail: "238/238 hallucination checks, 10/10 figure SHA-256s, PDF SHA-256 sign-off, 19/19 pytest passing." },
  ];

  return (
    <SceneShell
      step="08 · PROVENANCE VERIFICATION & INDEPENDENT SIGN-OFF"
      title="Zero Leaks. Instant Revocation. Co-Designed to Silicon."
      subtitle="Independently audited from raw JSONL and C++ source with zero prior builder context"
      sceneIdx={8}
      totalScenes={8}
      durationInFrames={durationInFrames}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1.45fr 1fr", gap: 36, height: "100%" }}>
        {/* Left: Animated Verification Checklist */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {checks.map((item) => (
            <div
              key={item.label}
              style={{
                background: COLORS.card,
                border: `2px solid ${COLORS.emerald}55`,
                borderRadius: 20,
                padding: "22px 28px",
                display: "flex",
                gap: 20,
                alignItems: "flex-start",
                opacity: item.pop,
                transform: `translateX(${(1 - item.pop) * -36}px)`,
              }}
            >
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 12,
                  background: "rgba(16,185,129,0.2)",
                  color: COLORS.emerald,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 26,
                  fontWeight: 900,
                  flexShrink: 0,
                }}
              >
                ✓
              </div>
              <div>
                <div style={{ fontSize: 24, fontWeight: 800, color: COLORS.white }}>{item.label}</div>
                <div style={{ fontSize: 19, color: COLORS.muted, marginTop: 6, lineHeight: 1.35 }}>{item.detail}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Right: Final Acceptance Seal */}
        <div
          style={{
            background: "linear-gradient(160deg, #0E2244 0%, #09172E 100%)",
            border: `3px solid ${COLORS.emerald}`,
            borderRadius: 28,
            padding: 36,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            alignItems: "center",
            textAlign: "center",
            opacity: Math.max(0.2, seal),
            transform: `scale(${0.88 + seal * 0.12})`,
          }}
        >
          <div style={{ fontFamily: FONT_MONO, fontSize: 18, fontWeight: 800, color: COLORS.cyan, letterSpacing: 2 }}>
            INDEPENDENT PHASE 20 REVIEW
          </div>
          <div>
            <div style={{ fontFamily: FONT_MONO, fontSize: 96, fontWeight: 900, color: COLORS.emerald, lineHeight: 1 }}>
              7.5 / 10
            </div>
            <div
              style={{
                display: "inline-block",
                marginTop: 18,
                fontFamily: FONT_MONO,
                fontSize: 24,
                fontWeight: 900,
                color: COLORS.bg,
                background: COLORS.emerald,
                padding: "10px 28px",
                borderRadius: 99,
              }}
            >
              READY · ACCEPT · 0 BLOCKERS
            </div>
          </div>

          <div style={{ width: "100%", borderTop: `1px solid ${COLORS.cardBorder}`, paddingTop: 22 }}>
            <div style={{ fontSize: 24, fontWeight: 800, color: COLORS.white }}>Prism-ANN v3</div>
            <div style={{ fontSize: 19, color: COLORS.muted, marginTop: 8 }}>
              12-Page IEEEtran Manuscript · 11/11 Predictions Supported · Ready for arXiv &amp; Enterprise Pilot
            </div>
          </div>
        </div>
      </div>
    </SceneShell>
  );
};
