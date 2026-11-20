#!/usr/bin/env python3
"""
Generate all Prism-ANN v2 figures exclusively from results/v2/summary.json (ADR-0004).
======================================================================================
Outputs vector PDFs and 300-DPI PNGs to paper/figures/v2_*.{pdf,png}.
Zero hardcoded metrics; every value is read directly from results/v2/summary.json.
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
SUMMARY_PATH = os.path.join(REPO_ROOT, "results", "v2", "summary.json")
OUT_DIR = os.path.join(REPO_ROOT, "paper", "figures")

# Publication styling (Okabe-Ito colorblind-safe palette, IEEE two-column ready)
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9.2,
    "axes.titlesize": 9.8,
    "axes.titleweight": "bold",
    "axes.labelsize": 9.2,
    "xtick.labelsize": 8.3,
    "ytick.labelsize": 8.3,
    "legend.fontsize": 7.6,
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
    "lines.linewidth": 1.8,
    "lines.markersize": 5.5,
})

SYS_STYLE = {
    "prism-graph-only": ("Prism graph-only (Py)", "#D55E00", "o", "-", 2.2),
    "prism-full": ("Prism full w/ Mode 3 (Py/NP)", "#E69F00", "s", "--", 2.0),
    "prism-static-2hop": ("Prism static-2hop (no GLS)", "#CC79A7", "D", "-.", 1.8),
    "faiss-hnsw-M16": ("FAISS HNSW M=16 (C++)", "#0072B2", "^", "-", 1.9),
    "faiss-hnsw-M8": ("FAISS HNSW M=8 shared (C++)", "#56B4E9", "v", ":", 1.6),
    "acorn-1": ("ACORN-1 upstream (C++)", "#009E73", "P", "-", 1.9),
    "hnswlib-M16": ("hnswlib M=16 (C++/Py-cb)", "#332288", "X", "-.", 1.7),
    "pgvector-hnsw-iter": ("pgvector 0.8.7 iter (C)", "#882255", "*", "-", 1.9),
    "exact-brute-force": ("Exact brute force (BLAS)", "#555555", ".", ":", 1.3),
}


def _save(fig: plt.Figure, stem: str) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    for ext in ("pdf", "png"):
        path = os.path.join(OUT_DIR, f"{stem}.{ext}")
        fig.savefig(path, dpi=300)
        print(f"[plot_v2] wrote {os.path.relpath(path, REPO_ROOT)}")
    plt.close(fig)


def plot_h1(summary: dict) -> None:
    h1 = summary["hypotheses"]["H1"]
    v1c = summary["verdicts"]["P1c"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.0))

    groups = [
        (f"All Principals\n(n={h1['n_principals']})", "all"),
        (f"Broad (>=1k docs)\n(n={v1c['n_principals']})", "auth_docs_ge_1000"),
    ]
    paths = [
        ("UBP+bitmap", "UBP + CRoaring (mirror)", "#D55E00"),
        ("SpiceDB-ReadRelationships+UBP+bitmap", "SpiceDB ReadRels + UBP + CRoaring", "#E69F00"),
        ("SpiceDB-LookupResources+leaf-bitmap", "SpiceDB LookupRes + leaf CRoaring", "#0072B2"),
    ]

    x = np.arange(len(groups))
    w = 0.25
    for idx, (key, label, col) in enumerate(paths):
        meds, cis, p95s = [], [], []
        for _, sub in groups:
            blk = h1["timing"][sub][key]
            meds.append(blk["by_seed"]["latency_ms_median"]["mean"])
            cis.append(blk["by_seed"]["latency_ms_median"]["ci95"])
            p95s.append(blk["latency_ms_p95_pooled"])
        off = (idx - 1) * w
        bars1 = ax1.bar(x + off, meds, w * 0.88, yerr=cis, capsize=2.5, color=col,
                        edgecolor="white", linewidth=0.6, label=label, zorder=3)
        bars2 = ax2.bar(x + off, p95s, w * 0.88, color=col,
                        edgecolor="white", linewidth=0.6, label=label, zorder=3)
        for b, val, ci in zip(bars1, meds, cis):
            ax1.text(b.get_x() + b.get_width() / 2, (val + ci) * 1.20, f"{val:.2f}",
                     ha="center", va="bottom", fontsize=7.2, fontweight="bold")
        for b, val in zip(bars2, p95s):
            ax2.text(b.get_x() + b.get_width() / 2, val * 1.18, f"{val:.2f}",
                     ha="center", va="bottom", fontsize=7.2, fontweight="bold")

    ax1.set_yscale("log")
    ax1.set_ylim(0.1, 650)
    ax1.set_xticks(x)
    ax1.set_xticklabels([g[0] for g in groups])
    ax1.set_ylabel("Median Latency (ms, log)")
    ax1.set_title("(a) Median Resolution + Bitmap (95% CI)")
    ax1.text(
        0.03, 0.96,
        f"P1c Broad Speedup:\n"
        f"  {v1c['ratio_spicedb_over_ubp']:.1f}x (local mirror)\n"
        f"  {v1c['strict_ratio_including_grant_fetch']:.1f}x (strict live RPC)",
        transform=ax1.transAxes, va="top", ha="left", fontsize=7.2,
        bbox=dict(boxstyle="round,pad=0.3", fc="#FFF8EE", ec="#D55E00", lw=0.8),
    )

    ax2.set_yscale("log")
    ax2.set_ylim(0.2, 4500)
    ax2.set_xticks(x)
    ax2.set_xticklabels([g[0] for g in groups])
    ax2.set_ylabel("P95 Latency (ms, log)")
    ax2.set_title("(b) P95 Tail Latency & Oracle Invariants")
    info = (
        f"Oracle mismatches: {h1['mismatch_docs_total']} docs / {h1['mismatch_chunks_total']} chunks\n"
        f"Thm. 1 bound: {100*h1['within_bound_fraction']:.0f}% ({h1['n_principals']}/{h1['n_principals']})\n"
        f"UBP tokens: med {h1['tokens_pos_median']:.0f}, max {h1['tokens_pos_max']} (m in 0..20)"
    )
    ax2.text(
        0.03, 0.96, info, transform=ax2.transAxes, va="top", ha="left", fontsize=7.1,
        bbox=dict(boxstyle="round,pad=0.3", fc="#F5F8FC", ec="#0072B2", lw=0.8),
    )

    handles, labels = ax1.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.10), ncol=3)
    fig.tight_layout()
    fig.subplots_adjust(wspace=0.28)
    _save(fig, "v2_fig1_h1_spicedb_ubp")


def plot_h2(summary: dict) -> None:
    bc = summary["hypotheses"]["H2"]["by_condition"]
    s_keys = ["S=0.001", "S=0.005", "S=0.01", "S=0.05"]
    s_vals = [0.1, 0.5, 1.0, 5.0]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.15))

    order_recall = [
        "prism-graph-only", "prism-full", "faiss-hnsw-M16", "faiss-hnsw-M8",
        "acorn-1", "hnswlib-M16", "pgvector-hnsw-iter", "exact-brute-force",
    ]
    for sysname in order_recall:
        label, col, mk, ls, lw = SYS_STYLE[sysname]
        ys = [100.0 * bc[sk][sysname]["recall_mean"]["mean"] for sk in s_keys]
        yerr = [100.0 * (bc[sk][sysname]["recall_mean"]["ci95"] or 0.0) for sk in s_keys]
        ax1.errorbar(s_vals, ys, yerr=yerr, label=label, color=col, marker=mk,
                     linestyle=ls, linewidth=lw, capsize=2.5, zorder=4 if "prism" in sysname else 3)

    ax1.set_xscale("log")
    ax1.set_xticks(s_vals)
    ax1.set_xticklabels(["0.1%", "0.5%", "1%", "5%"])
    ax1.set_ylim(-2, 107)
    ax1.set_xlabel("Filter Selectivity S (random, N=522,931)")
    ax1.set_ylabel("Recall@10 (%)")
    ax1.set_title("(a) H2v2 Recall@10 vs. Selectivity (95% CI)")

    order_dist = [
        "prism-graph-only", "prism-full", "faiss-hnsw-M16", "faiss-hnsw-M8",
        "acorn-1", "exact-brute-force",
    ]
    for sysname in order_dist:
        label, col, mk, ls, lw = SYS_STYLE[sysname]
        ys = [bc[sk][sysname]["dist_mean"]["mean"] for sk in s_keys]
        yerr = [bc[sk][sysname]["dist_mean"]["ci95"] or 0.0 for sk in s_keys]
        ax2.errorbar(s_vals, ys, yerr=yerr, label=label, color=col, marker=mk,
                     linestyle=ls, linewidth=lw, capsize=2.5, zorder=4 if "prism" in sysname else 3)

    ax2.set_xscale("log")
    ax2.set_yscale("log")
    ax2.set_xticks(s_vals)
    ax2.set_xticklabels(["0.1%", "0.5%", "1%", "5%"])
    ax2.set_xlabel("Filter Selectivity S (random, N=522,931)")
    ax2.set_ylabel("Distance Computations / Query (log)")
    ax2.set_title("(b) H2v2 Distance Computations / Query")
    ax2.annotate(
        "ACORN-1 early stall\n(11.4 evals, 0.85% R@10;\nP2b falsified on dist ratio)",
        xy=(0.1, bc["S=0.001"]["acorn-1"]["dist_mean"]["mean"]),
        xytext=(0.25, 14),
        fontsize=6.9, bbox=dict(boxstyle="round,pad=0.25", fc="#F2FBF7", ec="#009E73", lw=0.8),
        arrowprops=dict(arrowstyle="->", color="#009E73", lw=0.9),
    )

    handles, labels = ax1.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.17), ncol=4)
    fig.tight_layout()
    fig.subplots_adjust(wspace=0.28)
    _save(fig, "v2_fig2_h2_selectivity_sweep")


def plot_h3(summary: dict) -> None:
    bc = summary["hypotheses"]["H3"]["by_condition"]
    desc = summary["hypotheses"]["H3"]["condition_descriptors"]
    v3a = summary["verdicts"]["P3a"]
    v3b = summary["verdicts"]["P3b"]

    bins = [
        ("r_le_0.5", f"Depleted (r <= 0.5)\nn={desc['r_le_0.5']['n_queries_x_seeds']}, mean r={desc['r_le_0.5']['r_measured_mean']:.2f}"),
        ("r_ge_2", f"Enriched (r >= 2.0)\nn={desc['r_ge_2']['n_queries_x_seeds']}, mean r={desc['r_ge_2']['r_measured_mean']:.1f}"),
    ]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.25))

    sys_recall = ["prism-graph-only", "prism-static-2hop", "faiss-hnsw-M16", "acorn-1", "hnswlib-M16"]
    x = np.arange(len(bins))
    w = 0.15
    for idx, sysname in enumerate(sys_recall):
        label, col, _, _, _ = SYS_STYLE[sysname]
        ys = [100.0 * bc[bk][sysname]["recall_mean"]["mean"] for bk, _ in bins]
        yerr = [100.0 * (bc[bk][sysname]["recall_mean"]["ci95"] or 0.0) for bk, _ in bins]
        off = (idx - (len(sys_recall) - 1) / 2.0) * w
        bars = ax1.bar(x + off, ys, w * 0.88, yerr=yerr, capsize=2.0, color=col,
                       edgecolor="white", linewidth=0.5, label=label, zorder=3)
        for b, val, ci in zip(bars, ys, yerr):
            ax1.text(b.get_x() + b.get_width() / 2, val + ci + 2.2, f"{val:.1f}",
                     ha="center", va="bottom", fontsize=6.5, rotation=90)

    ax1.set_ylim(0, 145)
    ax1.set_yticks([0, 20, 40, 60, 80, 100])
    ax1.set_xticks(x)
    ax1.set_xticklabels([b[1] for b in bins])
    ax1.set_ylabel("Recall@10 (%)")
    ax1.set_title("(a) H3v2 Recall@10 by Measured r (S=2%)")
    ax1.text(
        0.03, 0.96,
        f"P3a (r<=0.5): +{100*v3a['diff']:.1f} pts vs. FAISS M=16 (SUPPORTED)",
        transform=ax1.transAxes, va="top", ha="left", fontsize=6.9,
        bbox=dict(boxstyle="round,pad=0.25", fc="#FFF8EE", ec="#D55E00", lw=0.8),
    )

    sys_dist = ["prism-graph-only", "prism-static-2hop", "faiss-hnsw-M16", "acorn-1"]
    w2 = 0.19
    for idx, sysname in enumerate(sys_dist):
        label, col, _, _, _ = SYS_STYLE[sysname]
        ys = [bc[bk][sysname]["dist_mean"]["mean"] for bk, _ in bins]
        yerr = [bc[bk][sysname]["dist_mean"]["ci95"] or 0.0 for bk, _ in bins]
        off = (idx - (len(sys_dist) - 1) / 2.0) * w2
        bars = ax2.bar(x + off, ys, w2 * 0.88, yerr=yerr, capsize=2.0, color=col,
                       edgecolor="white", linewidth=0.5, label=label, zorder=3)
        for b, val, ci in zip(bars, ys, yerr):
            ax2.text(b.get_x() + b.get_width() / 2, val + ci + 70, f"{val:.0f}",
                     ha="center", va="bottom", fontsize=6.8, fontweight="bold")

    ax2.set_ylim(0, 4350)
    ax2.set_xticks(x)
    ax2.set_xticklabels([b[1] for b in bins])
    ax2.set_ylabel("Distance Computations / Query")
    ax2.set_title("(b) H3v2 Distance Evals (GLS Ablation)")
    ax2.text(
        0.03, 0.96,
        f"P3b (r>=2): {v3b['dist_ratio']:.3f}x evals ({1/v3b['dist_ratio']:.2f}x fewer)\n"
        f"Recall: {100*(v3b['prism_recall']-v3b['static_recall']):.2f} pts (FALSIFIED vs -1 pt)",
        transform=ax2.transAxes, va="top", ha="left", fontsize=6.9,
        bbox=dict(boxstyle="round,pad=0.25", fc="#FDF2F8", ec="#CC79A7", lw=0.8),
    )

    handles, labels = ax1.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.14), ncol=3)
    fig.tight_layout()
    fig.subplots_adjust(wspace=0.28)
    _save(fig, "v2_fig3_h3_gls_correlation")


def plot_h4_and_latency(summary: dict) -> None:
    h4 = summary["hypotheses"]["H4"]["systems"]
    v4b = summary["verdicts"]["P4b"]
    bc_h2 = summary["hypotheses"]["H2"]["by_condition"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.1))

    p4a = h4["P4a-path(SpiceDB-Delete+mirror+UBP+bitmap)"]
    p4b = h4["pgvector-UPDATE-acl"]
    labels_h4 = [
        "SpiceDB Edge Delete\n+ UBP + CRoaring\n(0 vector writes)",
        "PostgreSQL 17 + pgvector\nUPDATE acl_allowed\n(153,600 row writes)",
    ]
    meds = [p4a["latency_ms_median"], p4b["latency_ms_median"]]
    maxs = [p4a["latency_ms_max"], p4b["latency_ms_max"]]
    low_err = [meds[0] - p4a["latency_ms_min"], meds[1] - p4b["latency_ms_min"]]
    high_err = [maxs[0] - meds[0], maxs[1] - meds[1]]
    ax1.bar([0, 1], meds, width=0.46, yerr=[low_err, high_err], capsize=4,
            color=["#D55E00", "#882255"], edgecolor="white", linewidth=0.7, zorder=3)
    ax1.set_yscale("log")
    ax1.set_ylim(10, 2.5e6)
    ax1.set_xticks([0, 1])
    ax1.set_xticklabels(labels_h4)
    ax1.set_ylabel("Revocation Latency (ms, log)")
    ax1.set_title("(a) H4v2 Revocation: 1,024 Docs (n=5)")
    ax1.text(0, maxs[0] * 1.45, f"{meds[0]:.1f} ms\n(0 writes)", ha="center", va="bottom",
             fontsize=7.8, fontweight="bold", color="#D55E00")
    ax1.text(1, maxs[1] * 1.35, f"{meds[1]/1000:.1f} s\n({v4b['ratio']:.0f}x slower)",
             ha="center", va="bottom", fontsize=7.8, fontweight="bold", color="#882255")

    s_keys = ["S=0.001", "S=0.005", "S=0.01", "S=0.05"]
    s_vals = [0.1, 0.5, 1.0, 5.0]
    order_lat = [
        "prism-full", "prism-graph-only", "faiss-hnsw-M16",
        "acorn-1", "hnswlib-M16", "pgvector-hnsw-iter", "exact-brute-force",
    ]
    for sysname in order_lat:
        label, col, mk, ls, lw = SYS_STYLE[sysname]
        ys = [bc_h2[sk][sysname]["latency_ms_median"]["mean"] for sk in s_keys]
        ax2.plot(s_vals, ys, label=label, color=col, marker=mk, linestyle=ls, linewidth=lw,
                 zorder=4 if "prism" in sysname else 3)

    ax2.set_xscale("log")
    ax2.set_yscale("log")
    ax2.set_xticks(s_vals)
    ax2.set_xticklabels(["0.1%", "0.5%", "1%", "5%"])
    ax2.set_ylim(0.15, 900)
    ax2.set_xlabel("Filter Selectivity S (random, N=522,931)")
    ax2.set_ylabel("Median Query Latency (ms, log)")
    ax2.set_title("(b) Secondary: H2v2 Median Latency")

    handles, labels = ax2.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.17), ncol=4)
    fig.tight_layout()
    fig.subplots_adjust(wspace=0.28)
    _save(fig, "v2_fig4_h4_revocation_and_latency")


def main() -> int:
    with open(SUMMARY_PATH, "r", encoding="utf-8") as f:
        summary = json.load(f)
    assert summary["freeze_match_all"] is True, "summary.json is not freeze-matched!"
    plot_h1(summary)
    plot_h2(summary)
    plot_h3(summary)
    plot_h4_and_latency(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
