#!/usr/bin/env python3
"""
Publication-Grade Academic Figure Generator for Prism-ANN (generate_prism_ann_plots.py)
=======================================================================================
Reads `results/prism_ann_benchmark_results.json` and generates 4 dual-panel
vector PDF + 300-DPI PNG figures in `paper/figures/` adhering to `academic-plotting`
and `PaperVizAgent` (Google Research, arXiv:2601.23265) standards:
  1. fig1_prism_selectivity_sweep.{pdf,png}
  2. fig2_prism_ubp_token_compression.{pdf,png}
  3. fig3_prism_gls_correlation.{pdf,png}
  4. fig4_prism_revocation_throughput.{pdf,png}
"""

import os
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS_PATH = os.path.join(REPO_ROOT, "results", "prism_ann_benchmark_results.json")
FIG_DIR = os.path.join(REPO_ROOT, "paper", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# Configure IEEE / VLDB publication-grade serif typography
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif", "Times"],
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.labelsize": 10.5,
    "axes.labelweight": "bold",
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 7.4,
    "figure.titlesize": 12,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linestyle": "--",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

# Colorblind-safe Ocean Dusk + Okabe-Ito high-contrast academic palette
PALETTE = {
    "Prism_ANN_Full": "#0F766E",                    # Deep Emerald Teal (Hero)
    "Ablation2_UBP_TriModal_NoBridges": "#0284C7",  # Sky Blue
    "Ablation1_UBP_Static_ACORN1": "#6366F1",       # Indigo
    "B3_Standalone_ACORN_1": "#D97706",             # Warm Amber
    "B4_Standalone_ACORN_Gamma10": "#7C3AED",       # Royal Purple
    "B5_HoneyBee_RBAC": "#DB2777",                  # Magenta Rose
    "B6_UNG_Static_LNG": "#4D7C0F",                 # Olive Green
    "B7_pgvector_Iterative_HNSW": "#DC2626",        # Crimson Red
    "B2_NaiveLookup_1HopHNSW": "#64748B",           # Slate Grey
    "B1_PostFilter_CheckBulk": "#94A3B8",           # Muted Silver
}


def save_dual(fig, base_name: str) -> None:
    pdf_path = os.path.join(FIG_DIR, f"{base_name}.pdf")
    png_path = os.path.join(FIG_DIR, f"{base_name}.png")
    fig.savefig(pdf_path, format="pdf", bbox_inches="tight", pad_inches=0.06)
    fig.savefig(png_path, format="png", dpi=300, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print(f"  [OK] Saved {pdf_path} and {png_path} (300 DPI)")


def generate_fig1_selectivity_sweep(data: dict) -> None:
    sweep_data = data["h2_h3_selectivity_sweep"]
    S = np.array(sweep_data["selectivities"], dtype=np.float64) * 100.0  # in %
    hl = sweep_data["key_highlights"]

    def get_curve(sys_key: str, metric: str):
        return [row["systems"][sys_key][metric] for row in sweep_data["sweep"]]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.8, 5.2))

    # Panel (a): Recall@10 across 5 Orders of Magnitude of Selectivity
    series_a = [
        ("Prism_ANN_Full", "Prism-ANN (Full Proposed, 1.06× RAM)", "-o", 2.6, 6.0),
        ("Ablation2_UBP_TriModal_NoBridges", "Ablation 2 (Tri-Modal w/o Bridges)", "--s", 1.8, 4.8),
        ("B4_Standalone_ACORN_Gamma10", "B4: ACORN-$\\gamma$ ($\\gamma_{\\mathrm{eff}}=6$, 1.56× RAM)", "-.^", 1.7, 4.8),
        ("B5_HoneyBee_RBAC", "B5: HoneyBee RBAC (5.68× RAM)", ":D", 1.6, 4.5),
        ("B6_UNG_Static_LNG", "B6: UNG Static LNG", ":v", 1.5, 4.5),
        ("B3_Standalone_ACORN_1", "B3: Standalone ACORN-1 ($\\gamma=1$)", "-d", 2.0, 5.2),
        ("B2_NaiveLookup_1HopHNSW", "B2: Naive Lookup + 1-Hop HNSW", "--x", 1.5, 4.8),
        ("B1_PostFilter_CheckBulk", "B1: HNSW + CheckBulk (Post-Filter)", ":+", 1.5, 5.0),
    ]

    for key, label, style, lw, ms in series_a:
        y = get_curve(key, "recall_at_10")
        ax1.plot(S, y, style, color=PALETTE[key], linewidth=lw, markersize=ms, label=label)

    # Highlight Percolation Cliffs (Theorem 2 vs Theorem 3) in unobstructed regions
    ax1.axvline(1.47, color="#D97706", linestyle="--", linewidth=1.2, alpha=0.85)
    ax1.annotate(
        "ACORN-1 Cliff ($S_{\\mathrm{crit}} \\approx 1.47\\%$)\nDrops $92.4\\% \\rightarrow 53.8\\% \\rightarrow 33.6\\%$",
        xy=(1.47, 58.0),
        xytext=(0.011, 38.0),
        arrowprops=dict(arrowstyle="->", color="#B45309", lw=1.1),
        color="#B45309", fontsize=7.8, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#FDE68A", alpha=0.95),
    )

    ax1.axvline(0.08, color="#0F766E", linestyle="-.", linewidth=1.2, alpha=0.85)
    ax1.text(0.011, 79.0, "H-HNSW Bridge Cliff\n$S_{\\mathrm{crit}}^{\\mathrm{bridge}}\\approx 0.08\\%$\n(94.8% Recall at $S=0.5\\%$)",
             color="#0F766E", fontsize=7.8, fontweight="bold",
             bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#99F6E4", alpha=0.95))

    ax1.set_xscale("log")
    ax1.set_xlim(0.008, 115.0)
    ax1.set_ylim(0, 106)
    ax1.set_xlabel("Global Predicate Selectivity $S = N_{\\mathrm{cand}} / N$ (%, Log Scale)")
    ax1.set_ylabel("Recall@10 (%)")
    ax1.set_title("(a) Recall@10 vs. Selectivity ($S \\in [10^{-4}, 1.0]$)")
    ax1.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), frameon=True, facecolor="white", framealpha=0.96, ncol=2, fontsize=7.2)

    # Panel (b): P99 Latency (ms) across Selectivity (Log-Log)
    series_b = [
        ("Prism_ANN_Full", "Prism-ANN (Full Proposed)", "-o", 2.6, 6.0),
        ("Ablation2_UBP_TriModal_NoBridges", "Ablation 2 (Tri-Modal w/o Bridges)", "--s", 1.7, 4.6),
        ("Ablation1_UBP_Static_ACORN1", "Ablation 1 (UBP + Static ACORN-1)", "-.^", 1.6, 4.6),
        ("B7_pgvector_Iterative_HNSW", "B7: pgvector Iterative HNSW Scan", "-v", 2.0, 5.2),
        ("B4_Standalone_ACORN_Gamma10", "B4: ACORN-$\\gamma$ ($\\gamma_{\\mathrm{eff}}=6$)", ":^", 1.8, 4.8),
        ("B3_Standalone_ACORN_1", "B3: Standalone ACORN-1", "-d", 1.8, 4.8),
        ("B5_HoneyBee_RBAC", "B5: HoneyBee RBAC", ":D", 1.5, 4.4),
        ("B2_NaiveLookup_1HopHNSW", "B2: Naive Lookup + 1-Hop HNSW", "--x", 1.6, 4.8),
    ]

    for key, label, style, lw, ms in series_b:
        y = get_curve(key, "p99_latency_ms")
        ax2.plot(S, y, style, color=PALETTE[key], linewidth=lw, markersize=ms, label=label)

    ax2.annotate(
        "pgvector Iterative Scan\n19.11 ms at $S=10^{-4}$ (39.8× slower)",
        xy=(0.01, 19.11),
        xytext=(0.013, 68.0),
        arrowprops=dict(arrowstyle="->", color="#DC2626", lw=1.2),
        fontsize=7.9,
        fontweight="bold",
        color="#DC2626",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="#FECACA", alpha=0.94),
    )
    ax2.annotate(
        "ACORN-$\\gamma$ Degree Expansion\n80.95 ms at $S=1.0$",
        xy=(100.0, 80.95),
        xytext=(1.1, 125.0),
        arrowprops=dict(arrowstyle="->", color="#7C3AED", lw=1.2),
        fontsize=7.9,
        fontweight="bold",
        color="#7C3AED",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="#DDD6FE", alpha=0.94),
    )
    min_p99 = hl["min_prism_p99_ms_across_all_S"]
    max_p99 = hl["max_prism_p99_ms_across_all_S"]
    ax2.annotate(
        f"Prism-ANN: {min_p99:.2f}–{max_p99:.2f} ms P99\n({hl['s_0_001_prism_p99_ms']:.2f} ms via Roaring-SIMD at $S=10^{{-3}}$)",
        xy=(0.1, hl["s_0_001_prism_p99_ms"]),
        xytext=(0.012, 0.011),
        arrowprops=dict(arrowstyle="->", color="#0F766E", lw=1.3),
        fontsize=7.9,
        fontweight="bold",
        color="#0F766E",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="#99F6E4", alpha=0.94),
    )

    ax2.set_xscale("log")
    ax2.set_yscale("log")
    ax2.set_xlim(0.008, 115.0)
    ax2.set_ylim(0.007, 320.0)
    ax2.set_xlabel("Global Predicate Selectivity $S = N_{\\mathrm{cand}} / N$ (%, Log Scale)")
    ax2.set_ylabel("End-to-End P99 Query Latency (ms, Log Scale)")
    ax2.set_title("(b) End-to-End P99 Latency (ms) vs. Selectivity")
    ax2.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), frameon=True, facecolor="white", framealpha=0.96, ncol=2, fontsize=7.2)

    plt.tight_layout()
    save_dual(fig, "fig1_prism_selectivity_sweep")


def generate_fig2_ubp_token_compression(data: dict) -> None:
    h1 = data["h1_ubp_token_compression"]
    deny_sweep = h1["deny_rule_sweep"]
    depth_sweep = h1["hierarchy_depth_sweep"]

    m_vals = [r["m_denies"] for r in deny_sweep]
    naive_toks = [r["naive_leaf_tokens"] for r in deny_sweep]
    bound_toks = [r["theorem1_upper_bound"] for r in deny_sweep]
    ubp_toks = [r["ubp_positive_tokens"] for r in deny_sweep]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.6, 4.3))

    # Panel (a): Capability Token Count vs DENY Exclusions m
    ax1.plot(m_vals, naive_toks, "--s", color="#64748B", linewidth=2.0, markersize=5.5,
             label="Naive SpiceDB LookupResources ($\\Theta(b^L)$ Leaves)")
    ax1.plot(m_vals, bound_toks, ":^", color="#D97706", linewidth=2.0, markersize=5.5,
             label="Theorem 1 Upper Bound: $k_0 + m(b-1)L$")
    ax1.plot(m_vals, ubp_toks, "-o", color="#0F766E", linewidth=2.6, markersize=6.2,
             label="Prism-ANN UBP ($|T_{\\mathrm{UBP}}^+(u)|$, 0 FP / 0 FN)")

    ax1.fill_between(m_vals, ubp_toks, naive_toks, color="#0F766E", alpha=0.07)
    ax1.annotate(
        "$m=5$: 8,152 $\\rightarrow$ 60 tokens\n(135.9× compression, 0 FP/FN)\n$m=0$: 8,192 $\\rightarrow$ 2 tokens (4,096×)",
        xy=(5, 60),
        xytext=(5.5, 3.2),
        arrowprops=dict(arrowstyle="->", color="#0F766E", lw=1.3),
        fontsize=8.1,
        fontweight="bold",
        color="#0F766E",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#99F6E4", alpha=0.94),
    )

    ax1.set_yscale("log")
    ax1.set_ylim(1, 35000)
    ax1.set_xlabel("Explicit Subtractive DENY Rules $m = |V^-(u)|$ ($L=4, b=8, k_0=2$)")
    ax1.set_ylabel("Emitted Capability Tokens $|T|$ (Log Scale)")
    ax1.set_title("(a) Theorem 1 Token Compression Bound vs. DENY Walls")
    ax1.legend(loc="center", bbox_to_anchor=(0.55, 0.56), frameon=True, facecolor="white", framealpha=0.96)

    # Panel (b): Roaring Bitmap Compilation Latency across Hierarchy Depth L
    L_vals = np.array([r["depth_L"] for r in depth_sweep])
    naive_ms = [r["naive_bitmap_union_ms"] for r in depth_sweep]
    ubp_ms = [r["ubp_roaring_compile_ms"] for r in depth_sweep]

    width = 0.34
    b1 = ax2.bar(L_vals - width / 2, naive_ms, width, color="#64748B", alpha=0.88,
                 label="Naive Leaf Disjunction Bitmap Union")
    b2 = ax2.bar(L_vals + width / 2, ubp_ms, width, color="#0F766E", alpha=0.95,
                 label="Prism-ANN UBP + Z-Order RunContainer Merge")

    for rect in b1:
        h = rect.get_height()
        ax2.text(rect.get_x() + rect.get_width() / 2.0, h * 1.15, f"{h:.2f}",
                 ha="center", va="bottom", fontsize=7.9, color="#334155", fontweight="bold")
    for rect in b2:
        h = rect.get_height()
        ax2.text(rect.get_x() + rect.get_width() / 2.0, h * 1.18, f"{h:.2f}",
                 ha="center", va="bottom", fontsize=7.9, color="#0F766E", fontweight="bold")

    ax2.set_yscale("log")
    ax2.set_ylim(0.005, 25.0)
    ax2.set_xticks(L_vals)
    ax2.set_xticklabels([f"$L={l}$" for l in L_vals])
    ax2.set_xlabel("Zanzibar Organizational Hierarchy Depth $L$ ($b=4, k_0=2, m=3$)")
    ax2.set_ylabel("Pre-Filter Bitmap Compilation Latency (ms, Log)")
    ax2.set_title("(b) Pre-Filter Roaring Bitmap Compilation Latency")
    ax2.legend(loc="upper left", frameon=True, facecolor="white", framealpha=0.94)

    plt.tight_layout()
    save_dual(fig, "fig2_prism_ubp_token_compression")


def generate_fig3_gls_correlation(data: dict) -> None:
    gls = data["h3_gls_correlation_sweep"]["sweep"]
    r_vals = [row["gls_ratio_r"] for row in gls]
    rec_prism = [row["Prism_ANN_ACORN_GLS_recall"] for row in gls]
    rec_hhnsw = [row["HHNSW_Static2Hop_recall"] for row in gls]
    rec_abl2 = [row["Ablation2_NoBridges_recall"] for row in gls]
    rec_acorn1 = [row["B3_Standalone_ACORN_1_recall"] for row in gls]

    eval_acorn1 = [row["B3_Standalone_ACORN_1_dist_evals"] for row in gls]
    eval_prism = [row["Prism_ANN_ACORN_GLS_dist_evals"] for row in gls]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.6, 4.3))

    # Panel (a): Recall@10 vs Global-Local Selectivity Ratio r
    ax1.plot(r_vals, rec_prism, "-o", color="#0F766E", linewidth=2.6, markersize=6.0,
             label="Prism-ANN (H-HNSW + Adaptive ACORN-GLS)")
    ax1.plot(r_vals, rec_hhnsw, "--^", color="#0284C7", linewidth=1.9, markersize=5.2,
             label="H-HNSW ($M_{\\mathrm{bridge}}=4$, Static 2-Hop)")
    ax1.plot(r_vals, rec_abl2, ":s", color="#6366F1", linewidth=1.8, markersize=5.0,
             label="Ablation 2 (No Express Bridges)")
    ax1.plot(r_vals, rec_acorn1, "-d", color="#D97706", linewidth=2.1, markersize=5.5,
             label="B3: Standalone ACORN-1 ($\\gamma=1$)")

    ax1.axvline(1.0, color="#64748B", linestyle="--", linewidth=1.0, alpha=0.7)
    ax1.text(0.30, 64.0, "Depleted Regime\n($r = S_{\\mathrm{loc}}/S < 1$)",
             fontsize=8.0, color="#B45309", fontweight="bold",
             bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#FDE68A", alpha=0.95))
    gain_r02 = round(rec_prism[0] - rec_acorn1[0], 1)
    ax1.annotate(
        f"+{gain_r02:.1f}% Recall Gain at $r=0.20$\nvia Express-Bridge Teleportation\n({rec_prism[0]:.1f}% vs. {rec_acorn1[0]:.1f}%)",
        xy=(0.20, rec_prism[0]),
        xytext=(1.10, 72.5),
        arrowprops=dict(arrowstyle="->", color="#0F766E", lw=1.3),
        fontsize=8.1,
        fontweight="bold",
        color="#0F766E",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#99F6E4", alpha=0.95),
    )

    ax1.set_xlim(0.1, 3.1)
    ax1.set_ylim(60, 103.5)
    ax1.set_xlabel("Global-Local Selectivity Ratio $r = S_{\\mathrm{loc}} / S$ (at $S = 2.0\\%$)")
    ax1.set_ylabel("Recall@10 (%)")
    ax1.set_title("(a) Recall@10 Across Global-Local Selectivity Ratio $r$")
    ax1.legend(loc="lower right", frameon=True, facecolor="white", framealpha=0.95)

    # Panel (b): Distance Evaluations vs Global-Local Selectivity Ratio r
    ax2.plot(r_vals, eval_acorn1, "-d", color="#D97706", linewidth=2.2, markersize=5.5,
             label="B3: Static ACORN-1 (Always 2-Hop Expansion)")
    ax2.plot(r_vals, eval_prism, "-o", color="#0F766E", linewidth=2.6, markersize=6.0,
             label="Prism-ANN ACORN-GLS (Bitmask-POPCNT Adaptive)")

    red_r3 = gls[-1]["dist_eval_reduction_x"]
    ax2.fill_between(r_vals, eval_prism, eval_acorn1, color="#0F766E", alpha=0.12,
                     label=f"CPU Distance Evaluations Saved (Up to {red_r3:.2f}×)")

    ax2.annotate(
        f"{red_r3:.2f}× fewer distance evals at $r=3.0$\n({eval_acorn1[-1]} $\\rightarrow$ {eval_prism[-1]} evals; $\\tau_{{\\mathrm{{high}}}}=0.25$)\nvia Bitmask-POPCNT 1-Hop Bypass",
        xy=(3.0, eval_prism[-1]),
        xytext=(1.15, 110),
        arrowprops=dict(arrowstyle="->", color="#0F766E", lw=1.3),
        fontsize=8.1,
        fontweight="bold",
        color="#0F766E",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#99F6E4", alpha=0.95),
    )

    ax2.set_xlim(0.1, 3.1)
    ax2.set_ylim(80, 620)
    ax2.set_xlabel("Global-Local Selectivity Ratio $r = S_{\\mathrm{loc}} / S$ (at $S = 2.0\\%$)")
    ax2.set_ylabel("Average Distance Evaluations per Query")
    ax2.set_title("(b) Bitmask-POPCNT Distance Evaluation Savings")
    ax2.legend(loc="upper right", frameon=True, facecolor="white", framealpha=0.94)

    plt.tight_layout()
    save_dual(fig, "fig3_prism_gls_correlation")


def generate_fig4_revocation_and_pareto(data: dict) -> None:
    h4 = data["h4_revocation_and_footprint"]
    rev_sweep = h4["revocation_sweep"]
    footprints = h4["index_footprint_comparison"]

    docs = [r["revoked_documents"] for r in rev_sweep]
    lat_prism = [r["prism_ann_ubp_zero_write_ms"] for r in rev_sweep]
    lat_flat = [r["flat_acl_payload_rewrite_ms"] for r in rev_sweep]
    lat_honeybee = [r["honeybee_partition_update_ms"] for r in rev_sweep]
    lat_ung = [r["ung_label_graph_update_ms"] for r in rev_sweep]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.8, 4.35))

    # Panel (a): Document Revocation Latency (Log-Log)
    ax1.plot(docs, lat_honeybee, ":D", color="#DB2777", linewidth=2.0, markersize=5.5,
             label="B5: HoneyBee RBAC Partition Update")
    ax1.plot(docs, lat_ung, "--v", color="#4D7C0F", linewidth=1.9, markersize=5.2,
             label="B6: UNG Label-Graph Edge Rebuild")
    ax1.plot(docs, lat_flat, "-s", color="#64748B", linewidth=2.1, markersize=5.5,
             label="Flat ACL-Stamped Vector Payload Rewrite ($O(N_{\\mathrm{chunks}})$)")
    ax1.plot(docs, lat_prism, "-o", color="#0F766E", linewidth=2.7, markersize=6.2,
             label="Prism-ANN UBP Zero-Write Edge Deletion ($O(1)$)")

    r1k = [r for r in rev_sweep if r["revoked_documents"] == 1000][0]
    r5k = [r for r in rev_sweep if r["revoked_documents"] == 5000][0]
    ax1.annotate(
        f"1,000 Docs (15K Chunks): {r1k['prism_ann_ubp_zero_write_ms']:.2f} ms vs. {r1k['flat_acl_payload_rewrite_ms']:.2f} ms ({r1k['speedup_vs_flat_rewrite_x']:.1f}×)\n"
        f"5,000 Docs (75K Chunks): {r5k['prism_ann_ubp_zero_write_ms']:.2f} ms vs. {r5k['flat_acl_payload_rewrite_ms']:.2f} ms ({r5k['speedup_vs_flat_rewrite_x']:.1f}×)",
        xy=(1000, r1k["prism_ann_ubp_zero_write_ms"]),
        xytext=(12, 0.007),
        arrowprops=dict(arrowstyle="->", color="#0F766E", lw=1.3),
        fontsize=7.9,
        fontweight="bold",
        color="#0F766E",
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#99F6E4", alpha=0.95),
    )

    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.set_ylim(0.004, 280.0)
    ax1.set_xlabel("Revoked / Superseded Documents $D_{\\mathrm{rev}}$ (15 Chunks/Doc)")
    ax1.set_ylabel("End-to-End Revocation Latency (ms, Log Scale)")
    ax1.set_title("(a) Zero-Write Revocation Throughput (Corollary 1)")
    ax1.legend(loc="upper left", frameon=True, facecolor="white", framealpha=0.94)

    # Panel (b): Index RAM Footprint (MB) vs Sub-1% Recall@10 (S=0.005) Pareto Frontier
    s005_row = [r for r in data["h2_h3_selectivity_sweep"]["sweep"] if r["selectivity"] == 0.005][0]["systems"]
    ram_map = {item["system_id"]: item["ram_mb"] for item in footprints}

    points = [
        ("Prism_ANN_Full", f"Prism-ANN (Proposed, {ram_map['Prism_ANN_Full']:.2f} MB, {s005_row['Prism_ANN_Full']['recall_at_10']:.1f}%)", (1.1, -6.5)),
        ("B7_pgvector_Iterative_HNSW", f"B7: pgvector Iterative ({ram_map['B7_pgvector_Iterative_HNSW']:.2f} MB, {s005_row['B7_pgvector_Iterative_HNSW']['recall_at_10']:.1f}%)", (1.1, 2.0)),
        ("B4_Standalone_ACORN_Gamma10", f"B4: ACORN-$\\gamma_{{\\mathrm{{eff}}}}=6$ ({ram_map['B4_Standalone_ACORN_Gamma10']:.2f} MB, {s005_row['B4_Standalone_ACORN_Gamma10']['recall_at_10']:.1f}%)", (1.1, -13.0)),
        ("Ablation2_UBP_TriModal_NoBridges", f"Ablation 2 / B3: ACORN-1\n(5.57–5.65 MB, {s005_row['Ablation2_UBP_TriModal_NoBridges']['recall_at_10']:.1f}%)", (1.1, 3.0)),
        ("B6_UNG_Static_LNG", f"B6: UNG ({ram_map['B6_UNG_Static_LNG']:.2f} MB, {s005_row['B6_UNG_Static_LNG']['recall_at_10']:.1f}%)", (1.1, -2.5)),
        ("B5_HoneyBee_RBAC", f"B5: HoneyBee RBAC\n({ram_map['B5_HoneyBee_RBAC']:.2f} MB, {s005_row['B5_HoneyBee_RBAC']['recall_at_10']:.1f}%)", (-11.5, 6.5)),
        ("B1_PostFilter_CheckBulk", f"B1: Post-Filter ({ram_map['B1_PostFilter_CheckBulk']:.2f} MB, {s005_row['B1_PostFilter_CheckBulk']['recall_at_10']:.1f}%)", (1.1, -2.5)),
        ("B2_NaiveLookup_1HopHNSW", f"B2: 1-Hop HNSW ({ram_map['B2_NaiveLookup_1HopHNSW']:.2f} MB, {s005_row['B2_NaiveLookup_1HopHNSW']['recall_at_10']:.1f}%)", (1.1, -3.0)),
    ]

    for sys_id, lbl, (dx, dy) in points:
        x_ram = ram_map[sys_id]
        y_rec = s005_row[sys_id]["recall_at_10"]
        size = 150 if sys_id == "Prism_ANN_Full" else 75
        marker = "*" if sys_id == "Prism_ANN_Full" else "o"
        ax2.scatter(x_ram, y_rec, s=size, color=PALETTE[sys_id], marker=marker, zorder=5, edgecolors="black", linewidths=0.7)
        ax2.text(x_ram + dx, y_rec + dy, lbl, fontsize=7.8,
                 fontweight="bold" if sys_id == "Prism_ANN_Full" else "normal",
                 color=PALETTE[sys_id])

    ax2.set_xlim(3.8, 35.5)
    ax2.set_ylim(-5, 108)
    ax2.set_xlabel("Measured Index Memory Footprint ($N=10{,}000, d=128$, MB)")
    ax2.set_ylabel("Sub-1% Selectivity Recall@10 (%, at $S = 0.5\\%$)")
    ax2.set_title("(b) Memory vs. Sub-1% Recall Pareto Frontier")

    plt.tight_layout()
    save_dual(fig, "fig4_prism_revocation_throughput")


def main():
    print(">>> Generating Publication-Grade Figures for Prism-ANN...")
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    generate_fig1_selectivity_sweep(data)
    generate_fig2_ubp_token_compression(data)
    generate_fig3_gls_correlation(data)
    generate_fig4_revocation_and_pareto(data)
    print("✅ All 4 Prism-ANN figures generated in PDF (vector) and PNG (300 DPI) formats!")


if __name__ == "__main__":
    main()
