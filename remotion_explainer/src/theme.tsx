import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export const COLORS = {
  bg: "#070D1D",
  bgGrad: "radial-gradient(circle at 20% 18%, #132347 0%, #070D1D 62%, #040812 100%)",
  card: "#0F1A33",
  cardBorder: "#23365E",
  white: "#F8FAFC",
  muted: "#94A3B8",
  blue: "#3B82F6",
  cyan: "#22D3EE",
  emerald: "#10B981",
  amber: "#F59E0B",
  coral: "#EF4444",
  violet: "#8B5CF6",
};

export const FONT_SANS =
  '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", "Helvetica Neue", Arial, sans-serif';
export const FONT_MONO = '"SF Mono", Menlo, Monaco, Consolas, monospace';

export const usePop = (delay = 0, damping = 14) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: Math.max(0, frame - delay), fps, config: { damping, stiffness: 120, mass: 0.8 } });
};

export const useFade = (start: number, dur = 15) => {
  const frame = useCurrentFrame();
  return interpolate(frame, [start, start + dur], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
};

export const SceneShell: React.FC<{
  step: string;
  title: string;
  subtitle: string;
  sceneIdx: number;
  totalScenes: number;
  durationInFrames: number;
  children: React.ReactNode;
}> = ({ step, title, subtitle, sceneIdx, totalScenes, durationInFrames, children }) => {
  const frame = useCurrentFrame();
  const fadeIn = interpolate(frame, [0, 14], [0, 1], { extrapolateRight: "clamp" });
  const fadeOut = interpolate(frame, [durationInFrames - 14, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const scenePct = ((sceneIdx - 1 + frame / durationInFrames) / totalScenes) * 100;

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
        opacity: Math.min(fadeIn, fadeOut),
      }}
    >

      {/* Top Accent Bar */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 6,
          background: `linear-gradient(90deg, ${COLORS.blue}, ${COLORS.cyan}, ${COLORS.emerald})`,
        }}
      />

      {/* Header */}
      <div
        style={{
          position: "absolute",
          top: 32,
          left: 72,
          right: 72,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <div>
          <div
            style={{
              display: "inline-block",
              fontSize: 18,
              fontWeight: 700,
              letterSpacing: 2,
              color: COLORS.cyan,
              textTransform: "uppercase",
              marginBottom: 8,
            }}
          >
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
            border: "1px solid rgba(16,185,129,0.35)",
            padding: "8px 18px",
            borderRadius: 999,
          }}
        >
          PRISM-ANN v3 · SCENE {String(sceneIdx).padStart(2, "0")}/{String(totalScenes).padStart(2, "0")}
        </div>
      </div>

      {/* Main Animated Stage */}
      <div style={{ position: "absolute", top: 190, left: 72, right: 72, bottom: 72 }}>{children}</div>

      {/* Global Bottom Progress Bar */}
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
              width: `${scenePct}%`,
              height: "100%",
              background: `linear-gradient(90deg, ${COLORS.blue}, ${COLORS.emerald})`,
              borderRadius: 99,
            }}
          />
        </div>
        <div style={{ fontFamily: FONT_MONO, fontSize: 16, color: COLORS.muted }}>
          169,810 Raw JSONL · 0 Leaks · 7.5/10 ACCEPT
        </div>
      </div>
    </div>
  );
};
