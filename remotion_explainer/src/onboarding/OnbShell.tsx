import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONT_MONO, FONT_SANS } from "../theme";

export const useOnbPop = (delay = 0, damping = 15) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: Math.max(0, frame - delay), fps, config: { damping, stiffness: 120, mass: 0.8 } });
};

export const OnbShell: React.FC<{
  step: string;
  title: string;
  subtitle: string;
  sceneIdx: number;
  totalScenes: number;
  children: React.ReactNode;
}> = ({ step, title, subtitle, sceneIdx, totalScenes, children }) => {
  const frame = useCurrentFrame();
  const fadeIn = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: "clamp" });
  const pct = (sceneIdx / totalScenes) * 100;

  return (
    <div
      style={{
        width: 1920,
        height: 1080,
        backgroundColor: COLORS.bg,
        fontFamily: FONT_SANS,
        color: COLORS.white,
        position: "relative",
        overflow: "hidden",
        opacity: fadeIn,
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 6,
          background: `linear-gradient(90deg, ${COLORS.emerald}, ${COLORS.cyan}, ${COLORS.blue}, ${COLORS.violet})`,
        }}
      />

      <div
        style={{
          position: "absolute",
          top: 34,
          left: 72,
          right: 72,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <div>
          <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: 2.2, color: COLORS.emerald, textTransform: "uppercase", marginBottom: 8 }}>
            {step}
          </div>
          <div style={{ fontSize: 48, fontWeight: 800, letterSpacing: -0.8, lineHeight: 1.1 }}>{title}</div>
          <div style={{ fontSize: 23, color: COLORS.muted, marginTop: 8 }}>{subtitle}</div>
        </div>
        <div
          style={{
            fontFamily: FONT_MONO,
            fontSize: 18,
            fontWeight: 700,
            color: COLORS.emerald,
            background: "rgba(16,185,129,0.12)",
            border: "1px solid rgba(16,185,129,0.4)",
            padding: "8px 18px",
            borderRadius: 999,
          }}
        >
          ONBOARDING {String(sceneIdx).padStart(2, "0")} / {String(totalScenes).padStart(2, "0")}
        </div>
      </div>

      <div style={{ position: "absolute", top: 192, left: 72, right: 72, bottom: 72 }}>{children}</div>

      <div
        style={{
          position: "absolute",
          bottom: 24,
          left: 72,
          right: 72,
          display: "flex",
          alignItems: "center",
          gap: 18,
        }}
      >
        <div style={{ flex: 1, height: 6, background: "#1E293B", borderRadius: 99, overflow: "hidden" }}>
          <div
            style={{
              width: `${pct}%`,
              height: "100%",
              background: `linear-gradient(90deg, ${COLORS.emerald}, ${COLORS.cyan})`,
              borderRadius: 99,
            }}
          />
        </div>
        <div style={{ fontFamily: FONT_MONO, fontSize: 16, color: COLORS.muted }}>
          Prism-ANN · Engineering Onboarding (Zero Leaks · Instant Revoke · Sub-ms Search)
        </div>
      </div>
    </div>
  );
};
