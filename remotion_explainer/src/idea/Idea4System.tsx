import React from "react";
import { COLORS, FONT_MONO } from "../theme";
import { IdeaShell, useIdeaPop } from "./IdeaShell";

export const Idea4System: React.FC = () => {
  const topPop = useIdeaPop(20);
  const q1 = useIdeaPop(90);
  const q2 = useIdeaPop(150);
  const q3 = useIdeaPop(215);

  return (
    <IdeaShell
      step="04 · SYSTEM-LEVEL ARCHITECTURE"
      title="How the Three Ideas Compose Into One Co-Designed System"
      subtitle="Decoupled ingest & zero-write revocation on top; tri-modal query execution & stall guard below"
      sceneIdx={4}
      totalScenes={5}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 28, height: "100%" }}>
        {/* Top Band: Ingest & O(1) Revocation Path */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${COLORS.emerald}66`,
            borderRadius: 22,
            padding: "22px 30px",
            opacity: topPop,
            transform: `translateY(${(1 - topPop) * 24}px)`,
          }}
        >
          <div style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 800, color: COLORS.emerald, letterSpacing: 1.5, marginBottom: 14 }}>
            INGEST &amp; O(1) ZERO-WRITE REVOCATION PATH (IMMUTABLE STRUCTURE vs. MUTABLE PERMISSIONS)
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 44px 1fr 44px 1fr 44px 1fr", alignItems: "center" }}>
            {[
              { t: "1. Ingest Chunks", s: "Stamp immutable lineage Anc(v_i) + Concept", c: COLORS.blue },
              { t: "2. Lexicographic Z-Order", s: "Sort vector IDs by (Anc(v_i), Magnet)", c: COLORS.cyan },
              { t: "3. Build H-HNSW + Bridges", s: "Base HNSW + sparse intra-container RNG edges", c: COLORS.violet },
              { t: "4. Revoke Edge in SpiceDB", s: "Delete 1 graph edge → 0 vector-store writes", c: COLORS.emerald },
            ].map((b, i) => (
              <React.Fragment key={b.t}>
                <div style={{ background: "#081226", border: `2px solid ${b.c}77`, borderRadius: 14, padding: "16px 18px" }}>
                  <div style={{ fontSize: 20, fontWeight: 800, color: COLORS.white }}>{b.t}</div>
                  <div style={{ fontSize: 16, color: COLORS.muted, marginTop: 6 }}>{b.s}</div>
                </div>
                {i < 3 && <div style={{ textAlign: "center", fontSize: 26, fontWeight: 900, color: COLORS.emerald }}>→</div>}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Bottom Band: Online Query Execution Path */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${COLORS.blue}66`,
            borderRadius: 22,
            padding: "24px 30px",
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 800, color: COLORS.cyan, letterSpacing: 1.5 }}>
            ONLINE QUERY EXECUTION PATH (TRI-MODAL PLANNER + LOCAL-STALL GUARD)
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "0.95fr 36px 1fr 36px 1.55fr", alignItems: "center", flex: 1 }}>
            {/* Step A: UBP + CRoaring */}
            <div
              style={{
                background: "#081226",
                border: `2px solid ${COLORS.blue}`,
                borderRadius: 16,
                padding: 22,
                opacity: q1,
                transform: `scale(${0.94 + q1 * 0.06})`,
              }}
            >
              <div style={{ fontFamily: FONT_MONO, fontSize: 15, color: COLORS.cyan, fontWeight: 800 }}>CONTROL PLANE</div>
              <div style={{ fontSize: 23, fontWeight: 800, marginTop: 8 }}>Query (q, u, C_q, ζ)</div>
              <div style={{ fontSize: 17, color: COLORS.muted, marginTop: 8, lineHeight: 1.4 }}>
                P_UBP resolves untainted boundary tokens and intersects with ontology → contiguous <strong>CRoaring RunContainers</strong>.
              </div>
            </div>

            <div style={{ textAlign: "center", fontSize: 28, fontWeight: 900, color: COLORS.cyan, opacity: q2 }}>→</div>

            {/* Step B: Tri-Modal Planner */}
            <div
              style={{
                background: "#081226",
                border: `2px solid ${COLORS.amber}`,
                borderRadius: 16,
                padding: 22,
                opacity: q2,
                transform: `scale(${0.94 + q2 * 0.06})`,
              }}
            >
              <div style={{ fontFamily: FONT_MONO, fontSize: 15, color: COLORS.amber, fontWeight: 800 }}>COST ROUTER</div>
              <div style={{ fontSize: 23, fontWeight: 800, marginTop: 8 }}>Tri-Modal Planner</div>
              <div style={{ fontSize: 17, color: COLORS.muted, marginTop: 8, lineHeight: 1.4 }}>
                Checks authorized cardinality N_cand against the SIMD crossover threshold, and monitors graph health at runtime.
              </div>
            </div>

            <div style={{ textAlign: "center", fontSize: 28, fontWeight: 900, color: COLORS.amber, opacity: q3 }}>→</div>

            {/* Step C: Dual Execution Engines + Stall Escalation */}
            <div style={{ display: "flex", flexDirection: "column", gap: 18, opacity: q3, transform: `translateX(${(1 - q3) * 32}px)` }}>
              <div style={{ background: "#091B2E", border: `2px solid ${COLORS.cyan}`, borderRadius: 16, padding: "18px 22px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 21, fontWeight: 800, color: COLORS.cyan }}>Mode 1 / 2 · Adaptive H-HNSW (ACORN-GLS)</span>
                  <span style={{ fontFamily: FONT_MONO, fontSize: 14, color: COLORS.amber }}>⚡ Stall Guard</span>
                </div>
                <div style={{ fontSize: 17, color: COLORS.muted, marginTop: 6 }}>
                  POPCNT estimates local survival Ŝ_loc(v): dense pockets use 1-hop fast path; sparse pockets traverse geometric bridges; depleted stalls escalate down to Mode 3.
                </div>
              </div>

              <div style={{ background: "#06231D", border: `2px solid ${COLORS.emerald}`, borderRadius: 16, padding: "18px 22px" }}>
                <div style={{ fontSize: 21, fontWeight: 800, color: COLORS.emerald }}>Mode 3 · Contiguous SIMD Interval Scan</div>
                <div style={{ fontSize: 17, color: COLORS.muted, marginTop: 6 }}>
                  Streams quantized vectors directly across Z-ordered RunContainer spans with zero scatter-gather, followed by exact top-k FP32 reranking.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </IdeaShell>
  );
};
