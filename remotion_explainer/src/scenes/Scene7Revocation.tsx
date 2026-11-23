import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { METRICS } from "../data";
import { COLORS, FONT_MONO, SceneShell, usePop } from "../theme";

export const Scene7Revocation: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const frame = useCurrentFrame();
  // Live race starts at frame 50: Prism finishes almost immediately (frame 68), pgvector grinds all the way to frame 420!
  const prismProg = interpolate(frame, [50, 74], [0, 100], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const pgvProg = interpolate(frame, [50, 420], [0, 100], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const pgvSec = (pgvProg / 100) * METRICS.h4PgvSec;
  const rowsUpdated = Math.round((pgvProg / 100) * 153600);
  const donePop = usePop(82);
  const ratioPop = usePop(340);

  return (
    <SceneShell
      step="07 · ZERO-WRITE ETHICAL-WALL REVOCATION RACE (H4v3)"
      title="Revoking 153,600 Chunks: 67 ms vs. 179.4 Seconds"
      subtitle="Live persistent PostgreSQL 17 SpiceDB DeleteRelationships vs. PostgreSQL 17 + pgvector 0.8.7 UPDATE (n = 5 trials)"
      sceneIdx={7}
      totalScenes={8}
      durationInFrames={durationInFrames}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 34, marginTop: 18 }}>
        {/* Lane 1: Prism-ANN */}
        <div
          style={{
            background: COLORS.card,
            border: `2.5px solid ${COLORS.emerald}`,
            borderRadius: 24,
            padding: 34,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
            <div>
              <div style={{ fontFamily: FONT_MONO, fontSize: 17, fontWeight: 800, color: COLORS.emerald }}>
                LANE 1 · PRISM-ANN (PERSISTENT PG17 SPICEDB DELETE EDGE + UBP)
              </div>
              <div style={{ fontSize: 24, fontWeight: 700, marginTop: 6 }}>
                Deletes 1 graph edge → RevokedSubtrees excises all 153,600 descendant chunks immediately
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontFamily: FONT_MONO, fontSize: 54, fontWeight: 900, color: COLORS.emerald }}>
                {prismProg >= 100 ? `${METRICS.h4P4aMs} ms` : `${(prismProg * 0.67).toFixed(1)} ms`}
              </div>
              <div style={{ fontFamily: FONT_MONO, fontSize: 17, color: COLORS.emerald, opacity: donePop }}>
                ✓ DONE · 0 VECTOR WRITES · 0 LEAKS
              </div>
            </div>
          </div>
          <div style={{ height: 32, background: "#070E20", borderRadius: 12, overflow: "hidden" }}>
            <div
              style={{
                width: `${prismProg}%`,
                height: "100%",
                background: `linear-gradient(90deg, ${COLORS.blue}, ${COLORS.emerald})`,
                borderRadius: 12,
              }}
            />
          </div>
        </div>

        {/* Lane 2: pgvector inline UPDATE */}
        <div
          style={{
            background: COLORS.card,
            border: `2.5px solid ${COLORS.coral}88`,
            borderRadius: 24,
            padding: 34,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
            <div>
              <div style={{ fontFamily: FONT_MONO, fontSize: 17, fontWeight: 800, color: COLORS.coral }}>
                LANE 2 · POSTGRESQL 17 + pgvector 0.8.7 (INLINE ACL COLUMN UPDATE)
              </div>
              <div style={{ fontSize: 24, fontWeight: 700, marginTop: 6 }}>
                Non-HOT heap rewrites + HNSW index maintenance + synchronous WAL flush
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontFamily: FONT_MONO, fontSize: 54, fontWeight: 900, color: COLORS.coral }}>
                {pgvSec.toFixed(1)} s
              </div>
              <div style={{ fontFamily: FONT_MONO, fontSize: 17, color: COLORS.muted }}>
                {rowsUpdated.toLocaleString()} / 153,600 rows rewritten
              </div>
            </div>
          </div>
          <div style={{ height: 32, background: "#070E20", borderRadius: 12, overflow: "hidden" }}>
            <div
              style={{
                width: `${pgvProg}%`,
                height: "100%",
                background: `linear-gradient(90deg, ${COLORS.amber}, ${COLORS.coral})`,
                borderRadius: 12,
              }}
            />
          </div>
        </div>

        {/* Bottom Speedup Callout */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            background: "linear-gradient(90deg, rgba(16,185,129,0.18), rgba(59,130,246,0.18))",
            border: `2px solid ${COLORS.cyan}`,
            borderRadius: 20,
            padding: "24px 36px",
            opacity: Math.max(0.2, ratioPop),
            transform: `scale(${0.95 + ratioPop * 0.05})`,
          }}
        >
          <div style={{ fontSize: 26, fontWeight: 800 }}>
            Immutable Lineage Stamping Eliminates Θ(N_chunks) Revocation Write Storms
          </div>
          <div style={{ fontFamily: FONT_MONO, fontSize: 44, fontWeight: 900, color: COLORS.emerald }}>
            {METRICS.h4Speedup.toLocaleString()}× FASTER
          </div>
        </div>
      </div>
    </SceneShell>
  );
};
