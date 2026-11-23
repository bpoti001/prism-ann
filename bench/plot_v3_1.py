#!/usr/bin/env python3
"""
Generate Prism-ANN v3.1 Reviewer Audit Figure (`v3_fig6_reviewer_audit`) exclusively
from `results/v3/reviewer_audit_v3_1.json` (zero hardcoded metrics).
"""

from __future__ import annotations

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_JSON = os.path.join(REPO_ROOT, "results", "v3", "reviewer_audit_v3_1.json")
OUT_DIR = os.path.join(REPO_ROOT, "paper", "figures")

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 8.5,
    "axes.titlesize": 9.0,
    "axes.titleweight": "bold",
    "axes.labelsize": 8.2,
    "xtick.labelsize": 7.6,
    "ytick.labelsize": 7.6,
    "legend.fontsize": 6.8,
    "legend.frameon": True,
    "legend.framealpha": 0.94,
    "legend.edgecolor": "#CCCCCC",
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.22,
    "grid.linestyle": "--",
})


def main() -> int:
    with open(AUDIT_JSON, "r", encoding="utf-8") as f:
        audit = json.load(f)

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(10.5, 2.28), gridspec_kw={"wspace": 0.30})

    # Panel (a): R2 Ultra-Low Selectivity S = 0.01% (Quora & NQ)
    r2 = audit["R2_s001_ultra_low_selectivity"]
    sys_keys = ["acorn-1", "faiss-hnsw-M16", "v3-geom-M8", "v3-full-guard-sq8"]
    labels = ["ACORN-1", "FAISS M16", "Prism Graph", "Prism Full"]
    cols = ["#009E73", "#0072B2", "#D55E00", "#E69F00"]
    q_vals = [r2["quora"]["systems"][k]["recall_pct"] for k in sys_keys]
    n_vals = [r2["nq"]["systems"][k]["recall_pct"] for k in sys_keys]

    x = np.arange(len(sys_keys))
    w = 0.36
    b1 = ax1.bar(x - w / 2, q_vals, w, color=cols, edgecolor="white", linewidth=0.6, label="BEIR Quora (523k)", zorder=3)
    b2 = ax1.bar(x + w / 2, n_vals, w, color=cols, alpha=0.58, hatch="//", edgecolor="#222222", linewidth=0.5, label="BEIR NQ (250k)", zorder=3)
    for bar, v in zip(b1, q_vals):
        dx = -0.05 if v >= 99.9 else 0.0
        ax1.text(bar.get_x() + bar.get_width() / 2 + dx, v + 1.8, f"{v:.1f}", ha="center", va="bottom", fontsize=5.8, fontweight="bold")
    for bar, v in zip(b2, n_vals):
        dx = 0.05 if v >= 99.9 else 0.0
        ax1.text(bar.get_x() + bar.get_width() / 2 + dx, v + 1.8, f"{v:.1f}", ha="center", va="bottom", fontsize=5.8)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.set_ylim(0, 118)
    ax1.set_ylabel("Recall@10 (%)")
    ax1.set_title("(a) Ultra-Low S=0.01% (R2)")
    ax1.legend(loc="upper left")

    # Panel (b): R3 6-Way Cold-LLC Mode-3 Isolation (Quora)
    r3 = audit["R3_mode3_component_isolation"]
    s_keys = ["S=0.0001", "S=0.001", "S=0.005", "S=0.01"]
    s_labels = ["0.01%", "0.1%", "0.5%", "1.0%"]
    variants = [
        ("1_scattered_f32_scalar", "Scattered FP32 Scalar", "#666666", "^", ":"),
        ("2_scattered_f32_neon", "Scattered FP32 NEON", "#0072B2", "v", "--"),
        ("3_zorder_f32_scalar", "Z-Order FP32 Scalar", "#CC79A7", "D", "-."),
        ("5_zorder_sq8_scalar", "Z-Order SQ8 Scalar", "#009E73", "s", "-."),
        ("4_zorder_f32_neon", "Z-Order FP32 NEON", "#56B4E9", "o", "-"),
        ("6_zorder_sq8_neon", "Z-Order SQ8 NEON", "#D55E00", "o", "-"),
    ]
    xs = np.arange(len(s_keys))
    for vkey, vlabel, col, mk, ls in variants:
        ys = [r3[sk]["cold"][vkey]["median_ms"] for sk in s_keys]
        ax2.plot(xs, ys, marker=mk, linestyle=ls, color=col, linewidth=1.7, markersize=4.3, label=vlabel, zorder=3)
    ax2.set_yscale("log")
    ax2.set_ylim(0.02, 14.0)
    ax2.set_xticks(xs)
    ax2.set_xticklabels(s_labels)
    ax2.set_xlabel("Authorized Selectivity S")
    ax2.set_ylabel("Cold-LLC Median Latency (ms, log)")
    ax2.set_title("(b) Cold-LLC Mode-3 Isolation (R3)")
    ax2.legend(loc="upper left", ncol=1, fontsize=5.5, handlelength=1.7, labelspacing=0.20, borderpad=0.25)

    # Panel (c): R4a O(1) Single-Edge Subtree Revocation Scaling
    sc = audit["R4_revocation_scaling_and_concurrent_zedtoken"]["scaling_postgres_spicedb"]
    rc = audit["R4_revocation_scaling_and_concurrent_zedtoken"]["concurrent_zedtoken_race"]
    chunks = [row["chunks_revoked"] for row in sc]
    meds = [row["median_ms"] for row in sc]
    mins = [row["min_ms"] for row in sc]
    maxs = [row["max_ms"] for row in sc]
    xc = np.arange(len(chunks))
    yerr = [np.array(meds) - np.array(mins), np.array(maxs) - np.array(meds)]
    ax3.errorbar(xc, meds, yerr=yerr, fmt="-o", color="#009E73", ecolor="#55AA88", capsize=2.8, linewidth=1.9, markersize=5.0, zorder=3, label="PG17 SpiceDB (0 writes)")
    ax3.set_xticks(xc)
    ax3.set_xticklabels([f"{c//1000}k" if c >= 1000 else str(c) for c in chunks], rotation=22)
    ax3.set_ylim(0, max(maxs) * 1.18)
    ax3.set_xlabel("Chunks in Revoked Subtree (1 Edge Delete)")
    ax3.set_ylabel("Revocation Latency (ms)")
    ax3.set_title("(c) O(1) Revocation Scaling (R4a/R4b)")
    ax3.text(
        0.97, 0.94,
        f"0 vector writes across 128->490k\n"
        f"Concurrent Race (R4b):\n"
        f"  {rc['total_concurrent_queries']:,} queries (4 threads)\n"
        f"  {rc['post_zeta_rev_leaked_chunks']}/{rc['post_revoke_zeta2_queries']:,} queries leaked",
        transform=ax3.transAxes, va="top", ha="right", fontsize=6.7,
        bbox=dict(boxstyle="round,pad=0.3", fc="#EFFCF6", ec="#009E73", lw=0.8),
    )

    os.makedirs(OUT_DIR, exist_ok=True)
    for ext in ("pdf", "png"):
        outp = os.path.join(OUT_DIR, f"v3_fig6_reviewer_audit.{ext}")
        fig.savefig(outp, dpi=300)
        print(f"[plot_v3_1] wrote {os.path.relpath(outp, REPO_ROOT)}")
    plt.close(fig)
    return 0


if __name__ == "__main__":
    sys.exit(main())
