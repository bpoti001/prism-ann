import React from "react";
import { COLORS, FONT_MONO } from "../theme";
import { OnbShell, useOnbPop } from "./OnbShell";

export const Onb3UbpBridges: React.FC = () => {
  const leftPop = useOnbPop(18);
  const rightPop = useOnbPop(130);

  return (
    <OnbShell
      step="03 · HOW PRISM-ANN SOLVES IT (PART 1 OF 2)"
      title="Smart Folder Pruning + Highway Express Overpasses"
      subtitle="Fix Trap 1 & Trap 3 with immutable folder paths; fix Trap 2 with a tiny budget of shortcut links"
      sceneIdx={3}
      totalScenes={6}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 36, height: "100%" }}>
        {/* Left: Fix 1 Upward Boundary Pruning */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${COLORS.emerald}66`,
            borderRadius: 24,
            padding: 32,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            opacity: leftPop,
            transform: `translateY(${(1 - leftPop) * 34}px)`,
          }}
        >
          <div>
            <div style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 800, color: COLORS.emerald }}>
              FIX 1 · UPWARD BOUNDARY PRUNING (UBP)
            </div>
            <div style={{ fontSize: 32, fontWeight: 800, marginTop: 8 }}>Mail to "Building B" — Not Every Desk</div>
            <div style={{ fontSize: 19, color: COLORS.cyan, marginTop: 6 }}>
              Stamp immutable folder paths once on ingest; never copy mutable user lists!
            </div>
          </div>

          <svg viewBox="0 0 680 260" width="100%" height="260">
            <line x1="340" y1="54" x2="170" y2="128" stroke={COLORS.emerald} strokeWidth="3.5" />
            <line x1="340" y1="54" x2="510" y2="128" stroke={COLORS.amber} strokeWidth="4.5" strokeDasharray="9 5" />
            <line x1="510" y1="168" x2="410" y2="222" stroke={COLORS.emerald} strokeWidth="3" />
            <line x1="510" y1="168" x2="600" y2="222" stroke={COLORS.coral} strokeWidth="4" strokeDasharray="7 5" />

            <rect x="225" y="14" width="230" height="44" rx="12" fill="#451A03" stroke={COLORS.amber} strokeWidth="2.5" />
            <text x="340" y="42" textAnchor="middle" fill={COLORS.white} fontSize="17" fontWeight="800">Engineering (Tainted)</text>

            <rect x="52" y="122" width="236" height="48" rx="12" fill="#064E3B" stroke={COLORS.emerald} strokeWidth="3" />
            <text x="170" y="152" textAnchor="middle" fill={COLORS.white} fontSize="17" fontWeight="800">STOP! Emit "Frontend"</text>

            <rect x="392" y="122" width="236" height="48" rx="12" fill="#451A03" stroke={COLORS.amber} strokeWidth="2.5" />
            <text x="510" y="152" textAnchor="middle" fill={COLORS.white} fontSize="17" fontWeight="800">Split Only This Branch</text>

            <rect x="335" y="212" width="146" height="40" rx="10" fill="#065F46" stroke={COLORS.emerald} strokeWidth="2.5" />
            <text x="408" y="237" textAnchor="middle" fill={COLORS.white} fontSize="16" fontWeight="800">Docs ✓</text>

            <rect x="515" y="212" width="150" height="40" rx="10" fill="#7F1D1D" stroke={COLORS.coral} strokeWidth="2.5" />
            <text x="590" y="237" textAnchor="middle" fill={COLORS.white} fontSize="16" fontWeight="800">Secret DENY</text>
          </svg>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div style={{ background: "#081226", border: `1.5px solid ${COLORS.emerald}55`, borderRadius: 14, padding: 16 }}>
              <div style={{ fontFamily: FONT_MONO, fontSize: 28, fontWeight: 900, color: COLORS.emerald }}>0.35 ms</div>
              <div style={{ fontSize: 16, color: COLORS.muted, marginTop: 4 }}>vs 98.3 ms SpiceDB (<strong>278× faster</strong>)</div>
            </div>
            <div style={{ background: "#081226", border: `1.5px solid ${COLORS.emerald}55`, borderRadius: 14, padding: 16 }}>
              <div style={{ fontFamily: FONT_MONO, fontSize: 28, fontWeight: 900, color: COLORS.emerald }}>67 ms</div>
              <div style={{ fontSize: 16, color: COLORS.muted, marginTop: 4 }}>O(1) folder revoke · <strong>0 vector writes</strong></div>
            </div>
          </div>
        </div>

        {/* Right: Fix 2 Semantic Shortcut Bridges */}
        <div
          style={{
            background: COLORS.card,
            border: `2px solid ${COLORS.cyan}66`,
            borderRadius: 24,
            padding: 32,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            opacity: rightPop,
            transform: `translateY(${(1 - rightPop) * 34}px)`,
          }}
        >
          <div>
            <div style={{ fontFamily: FONT_MONO, fontSize: 16, fontWeight: 800, color: COLORS.cyan }}>
              FIX 2 · SEMANTIC SHORTCUT BRIDGES (H-HNSW)
            </div>
            <div style={{ fontSize: 32, fontWeight: 800, marginTop: 8 }}>Express Overpasses Over Blocked Zones</div>
            <div style={{ fontSize: 19, color: COLORS.cyan, marginTop: 6 }}>
              8 diverse shortcuts/node: 4 same-folder, 2 sibling-folder, 2 same-topic
            </div>
          </div>

          <svg viewBox="0 0 680 260" width="100%" height="260">
            <rect x="200" y="34" width="280" height="190" rx="18" fill="rgba(239,68,68,0.1)" stroke={COLORS.coral} strokeWidth="2" strokeDasharray="7 5" />
            <text x="340" y="64" textAnchor="middle" fill={COLORS.coral} fontSize="16" fontWeight="800">99.9% FORBIDDEN NEIGHBORHOOD</text>
            {[260, 340, 420].map((cx) => (
              <circle key={cx} cx={cx} cy={135} r={14} fill="#7F1D1D" stroke={COLORS.coral} strokeWidth="2" />
            ))}
            <path d="M 105 135 Q 340 -8 575 135" fill="none" stroke={COLORS.cyan} strokeWidth="5.5" strokeDasharray="11 5" />
            <path d="M 105 135 Q 340 262 575 135" fill="none" stroke={COLORS.emerald} strokeWidth="4.5" />
            <text x="340" y="24" textAnchor="middle" fill={COLORS.cyan} fontSize="16" fontWeight="800" fontFamily={FONT_MONO}>
              EXPRESS BRIDGE OVERPASS
            </text>
            <circle cx="105" cy="135" r="32" fill="#064E3B" stroke={COLORS.emerald} strokeWidth="3.5" />
            <text x="105" y="141" textAnchor="middle" fill={COLORS.white} fontSize="16" fontWeight="800">Doc A</text>
            <circle cx="575" cy="135" r="32" fill="#064E3B" stroke={COLORS.emerald} strokeWidth="3.5" />
            <text x="575" y="141" textAnchor="middle" fill={COLORS.white} fontSize="16" fontWeight="800">Doc B</text>
          </svg>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div style={{ background: "#081226", border: `1.5px solid ${COLORS.cyan}55`, borderRadius: 14, padding: 16 }}>
              <div style={{ fontFamily: FONT_MONO, fontSize: 28, fontWeight: 900, color: COLORS.cyan }}>5.75% → 66.6%</div>
              <div style={{ fontSize: 16, color: COLORS.muted, marginTop: 4 }}>Graph-only recall jump at 0.1% visibility</div>
            </div>
            <div style={{ background: "#081226", border: `1.5px solid ${COLORS.cyan}55`, borderRadius: 14, padding: 16 }}>
              <div style={{ fontFamily: FONT_MONO, fontSize: 28, fontWeight: 900, color: COLORS.cyan }}>+1.9% RAM</div>
              <div style={{ fontSize: 16, color: COLORS.muted, marginTop: 4 }}>Tiny graph overhead (beats ACORN)</div>
            </div>
          </div>
        </div>
      </div>
    </OnbShell>
  );
};
