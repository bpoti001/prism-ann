#!/usr/bin/env python3
"""
Generate all Prism-ANN v3 figures exclusively from results/v3/summary.json (ADR-0005).
======================================================================================
Outputs vector PDFs and 300-DPI PNGs to paper/figures/v3_*.{pdf,png}.
100% dynamic interpolation from results/v3/summary.json (zero hardcoded metrics).
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
SUMMARY_PATH = os.path.join(REPO_ROOT, "results", "v3", "summary.json")
OUT_DIR = os.path.join(REPO_ROOT, "paper", "figures")

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9.0,
    "axes.titlesize": 9.5,
    "axes.titleweight": "bold",
    "axes.labelsize": 9.0,
    "xtick.labelsize": 8.2,
    "ytick.labelsize": 8.2,
    "legend.fontsize": 7.4,
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
    "lines.markersize": 5.2,
})

SYS_STYLE = {
    "v3-geom-M8": ("Prism v3 geom M8 (C++, graph)", "#D55E00", "o", "-", 2.2),
    "v3-full-guard-sq8": ("Prism v3 full + NEON SQ8 (C++)", "#E69F00", "s", "--", 2.0),
    "v3-static-2hop": ("Prism v3 static-2hop (no GLS)", "#CC79A7", "D", "-.", 1.8),
    "v2-ring-chord-M4": ("Prism v2 ring-chord M4 (C++)", "#AA4499", "v", ":", 1.7),
    "hhnsw-v2-geom-M8-noportal": ("Prism v3 geom M8 (0 portals)", "#117733", "D", "-", 2.1),
    "faiss-M16+4portals": ("FAISS M=16 + 4 Portals (C++)", "#56B4E9", "v", "--", 1.8),
    "faiss-hnsw-M16": ("FAISS HNSW M=16 (C++)", "#0072B2", "^", "-", 1.9),
    "acorn-1": ("ACORN-1 upstream (C++)", "#009E73", "P", "-", 1.8),
    "acorn-gamma": ("ACORN-gamma g=4 (C++)", "#44AA99", "h", "-.", 1.8),
    "hnswlib-M16": ("hnswlib M=16 (C++/Py-cb)", "#332288", "X", "-.", 1.7),
    "pgvector-hnsw-iter": ("pgvector 0.8.7 iter (C)", "#882255", "*", "-", 1.9),
    "exact-brute-force": ("Exact brute force (BLAS)", "#555555", ".", ":", 1.4),
    "cpp-mode3-sq8": ("Prism C++ NEON Mode 3 SQ8", "#E69F00", "s", ":", 1.6),
}


def _save(fig: plt.Figure, stem: str) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    for ext in ("pdf", "png"):
        path = os.path.join(OUT_DIR, f"{stem}.{ext}")
        fig.savefig(path, dpi=300)
        print(f"[plot_v3] wrote {os.path.relpath(path, REPO_ROOT)}")
    plt.close(fig)


def plot_fig1_h1(summary: dict) -> None:
    h1_mem = summary["hypotheses"]["H1_memory"]
    h1_pg = summary["hypotheses"]["H1_postgres"]
    v1c = summary["verdicts"]["P1c"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.1))

    backends = [
        (f"SpiceDB Memory\n(Broad n={v1c['memory']['n']})", h1_mem, v1c["memory"]),
        (f"SpiceDB PostgreSQL 17\n(Broad n={v1c['postgres']['n']})", h1_pg, v1c["postgres"]),
    ]
    paths = [
        ("UBP+bitmap", "UBP + CRoaring (mirror)", "#D55E00"),
        ("SpiceDB-ReadRelationships+UBP+bitmap", "SpiceDB ReadRels + UBP + CRoaring", "#E69F00"),
        ("SpiceDB-LookupResources+leaf-bitmap", "SpiceDB LookupRes + leaf CRoaring", "#0072B2"),
    ]

    x = np.arange(len(backends))
    w = 0.25
    for idx, (key, label, col) in enumerate(paths):
        meds, p95s = [], []
        for _, h1_obj, _ in backends:
            blk = h1_obj["timing"]["auth_docs_ge_1000"][key]
            meds.append(blk["latency_ms_median_pooled"])
            p95s.append(blk["latency_ms_p95_pooled"])
        off = (idx - 1) * w
        b1 = ax1.bar(x + off, meds, w * 0.88, color=col, edgecolor="white", linewidth=0.6, label=label, zorder=3)
        b2 = ax2.bar(x + off, p95s, w * 0.88, color=col, edgecolor="white", linewidth=0.6, label=label, zorder=3)
        for b, val in zip(b1, meds):
            ax1.text(b.get_x() + b.get_width() / 2, val * 1.18, f"{val:.2f}", ha="center", va="bottom", fontsize=7.0, fontweight="bold")
        for b, val in zip(b2, p95s):
            ax2.text(b.get_x() + b.get_width() / 2, val * 1.18, f"{val:.2f}", ha="center", va="bottom", fontsize=7.0, fontweight="bold")

    ax1.set_yscale("log")
    ax1.set_ylim(0.1, max(v1c["postgres"]["spicedb_median_ms"], 300.0) * 14.0)
    ax1.set_xticks(x)
    ax1.set_xticklabels([b[0] for b in backends])
    ax1.set_ylabel("Pooled Median Latency (ms, log)")
    ax1.set_title("(a) Broad-Principal Median Latency")
    ax1.text(
        0.03, 0.96,
        f"P1c Speedup (UBP / Strict RPC):\n"
        f"  Memory: {v1c['memory']['ratio_spicedb_over_ubp']:.1f}x / {v1c['memory']['strict_ratio']:.1f}x\n"
        f"  Postgres: {v1c['postgres']['ratio_spicedb_over_ubp']:.1f}x / {v1c['postgres']['strict_ratio']:.1f}x",
        transform=ax1.transAxes, va="top", ha="left", fontsize=7.0,
        bbox=dict(boxstyle="round,pad=0.3", fc="#FFF8EE", ec="#D55E00", lw=0.8),
    )

    ax2.set_yscale("log")
    pg_p95_max = h1_pg["timing"]["auth_docs_ge_1000"]["SpiceDB-LookupResources+leaf-bitmap"]["latency_ms_p95_pooled"]
    ax2.set_ylim(0.2, max(pg_p95_max, 500.0) * 14.0)
    ax2.set_xticks(x)
    ax2.set_xticklabels([b[0] for b in backends])
    ax2.set_ylabel("Pooled P95 Latency (ms, log)")
    ax2.set_title("(b) Broad-Principal P95 & Oracle Invariants")
    total_n = h1_mem["n_principals"] + h1_pg["n_principals"]
    total_mism = (
        h1_mem["mismatch_docs_total"] + h1_mem["mismatch_chunks_total"]
        + h1_pg["mismatch_docs_total"] + h1_pg["mismatch_chunks_total"]
    )
    ax2.text(
        0.03, 0.96,
        f"Live SpiceDB Oracle Mismatches: {total_mism}/{total_n}\n"
        f"Thm. 1 Bound: {100.0 * h1_mem['within_bound_fraction']:.0f}% (mem), {100.0 * h1_pg['within_bound_fraction']:.0f}% (PG)\n"
        f"UBP tokens: med {h1_mem['tokens_pos_median']:.0f}, max {h1_mem['tokens_pos_max']}",
        transform=ax2.transAxes, va="top", ha="left", fontsize=7.0,
        bbox=dict(boxstyle="round,pad=0.3", fc="#F5F8FC", ec="#0072B2", lw=0.8),
    )

    handles, labels = ax1.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.10), ncol=3)
    fig.tight_layout()
    fig.subplots_adjust(wspace=0.28)
    _save(fig, "v3_fig1_h1_spicedb_mem_and_postgres")


def plot_fig2_h2(summary: dict) -> None:
    s_keys = ["S=0.001", "S=0.005", "S=0.01", "S=0.05"]
    s_vals = np.array([0.1, 0.5, 1.0, 5.0])
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.2))

    panels = [
        (ax1, "H2_quora", "(a) Corpus 1: BEIR Quora (N=522,931)"),
        (ax2, "H2_nq", "(b) Corpus 2: BEIR NQ Wiki (N=250,000)"),
    ]
    order = [
        "v3-geom-M8", "v3-full-guard-sq8", "v2-ring-chord-M4",
        "faiss-hnsw-M16", "acorn-1", "acorn-gamma", "hnswlib-M16", "pgvector-hnsw-iter",
    ]
    # Tiny horizontal jitter multiplier for 100%-overlapping curves to prevent marker occlusion
    x_mult = {"v3-full-guard-sq8": 0.96, "hnswlib-M16": 1.04}

    for ax, hyp, title in panels:
        if hyp not in summary["hypotheses"]:
            continue
        bc = summary["hypotheses"][hyp]["by_condition"]
        for sysname in order:
            if sysname not in bc[s_keys[0]]:
                continue
            label, col, mk, ls, lw = SYS_STYLE[sysname]
            ys = [100.0 * bc[sk][sysname]["recall_mean"]["mean"] for sk in s_keys]
            yerr = [100.0 * (bc[sk][sysname]["recall_mean"]["ci95"] or 0.0) for sk in s_keys]
            xs = s_vals * x_mult.get(sysname, 1.0)
            mfc = "none" if sysname == "v3-full-guard-sq8" else col
            ax.errorbar(
                xs, ys, yerr=yerr, label=label, color=col, marker=mk,
                markerfacecolor=mfc, markeredgewidth=1.3,
                linestyle=ls, linewidth=lw, capsize=2.2, zorder=4 if "v3" in sysname else 3,
            )
        ax.set_xscale("log")
        ax.set_xticks(s_vals)
        ax.set_xticklabels(["0.1%", "0.5%", "1%", "5%"])
        ax.set_ylim(-2, 108)
        ax.set_xlabel("Filter Selectivity S (random overlay)")
        ax.set_ylabel("Recall@10 (%)")
        ax.set_title(title)

    handles, labels = ax1.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.18), ncol=4)
    fig.tight_layout()
    fig.subplots_adjust(wspace=0.25)
    _save(fig, "v3_fig2_h2_multi_corpus_recall")


def plot_fig3_h3(summary: dict) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.25))
    h3_q = summary["hypotheses"]["H3_quora"]["by_condition"]
    h3_n = summary["hypotheses"]["H3_nq"]["by_condition"]
    v3a = summary["verdicts"]["P3a"]["by_corpus"]
    v3b = summary["verdicts"]["P3b"]["by_corpus"]

    # Panel (a): Depleted (r <= 0.5) Recall@10 across BOTH corpora
    corpora_lbl = ["Quora (523k)\nDepleted r<=0.5", "BEIR NQ (250k)\nDepleted r<=0.5"]
    sys_a = ["v3-full-guard-sq8", "v3-geom-M8", "faiss-hnsw-M16", "acorn-1", "hnswlib-M16"]
    x = np.arange(len(corpora_lbl))
    w = 0.15
    for idx, sysname in enumerate(sys_a):
        label, col, _, _, _ = SYS_STYLE[sysname]
        ys = [100.0 * h3_q["r_le_0.5"][sysname]["recall_mean"]["mean"],
              100.0 * h3_n["r_le_0.5"][sysname]["recall_mean"]["mean"]]
        cis = [100.0 * (h3_q["r_le_0.5"][sysname]["recall_mean"]["ci95"] or 0.0),
               100.0 * (h3_n["r_le_0.5"][sysname]["recall_mean"]["ci95"] or 0.0)]
        off = (idx - (len(sys_a) - 1) / 2.0) * w
        bars = ax1.bar(x + off, ys, w * 0.88, yerr=cis, capsize=2.0, color=col, edgecolor="white", linewidth=0.5, label=label, zorder=3)
        for b, val, ci in zip(bars, ys, cis):
            ax1.text(b.get_x() + b.get_width() / 2, val + ci + 2.0, f"{val:.1f}", ha="center", va="bottom", fontsize=6.4, rotation=90)
    ax1.set_ylim(0, 148)
    ax1.set_yticks([0, 20, 40, 60, 80, 100])
    ax1.set_xticks(x)
    ax1.set_xticklabels(corpora_lbl)
    ax1.set_ylabel("Recall@10 (%)")
    ax1.set_title("(a) H3v3 Depleted (r<=0.5): Stall Guard")
    ax1.text(
        0.03, 0.96,
        f"Guard R@10 / med lat:\n"
        f"  Quora: {100*v3a['quora']['v3_full_recall']:.1f}% ({v3a['quora']['v3_full_med_ms']:.2f} ms)\n"
        f"  NQ:    {100*v3a['nq']['v3_full_recall']:.1f}% ({v3a['nq']['v3_full_med_ms']:.2f} ms)",
        transform=ax1.transAxes, va="top", ha="left", fontsize=6.8,
        bbox=dict(boxstyle="round,pad=0.25", fc="#FFF8EE", ec="#D55E00", lw=0.8),
    )

    # Panel (b): Enriched (r >= 2.0) Distance Evals across BOTH corpora (GLS vs static 2-hop)
    corpora_lbl2 = ["Quora (523k)\nEnriched r>=2.0", "BEIR NQ (250k)\nEnriched r>=2.0"]
    sys_b = ["v3-geom-M8", "v3-static-2hop", "faiss-hnsw-M16", "acorn-1"]
    w2 = 0.19
    max_d = 0.0
    for idx, sysname in enumerate(sys_b):
        label, col, _, _, _ = SYS_STYLE[sysname]
        ys = [h3_q["r_ge_2"][sysname]["dist_mean"]["mean"],
              h3_n["r_ge_2"][sysname]["dist_mean"]["mean"]]
        cis = [h3_q["r_ge_2"][sysname]["dist_mean"]["ci95"] or 0.0,
               h3_n["r_ge_2"][sysname]["dist_mean"]["ci95"] or 0.0]
        max_d = max(max_d, max(y + c for y, c in zip(ys, cis)))
        off = (idx - (len(sys_b) - 1) / 2.0) * w2
        bars = ax2.bar(x + off, ys, w2 * 0.88, yerr=cis, capsize=2.0, color=col, edgecolor="white", linewidth=0.5, label=label, zorder=3)
        for b, val, ci in zip(bars, ys, cis):
            ax2.text(b.get_x() + b.get_width() / 2, val + ci + max_d * 0.025, f"{val:.0f}", ha="center", va="bottom", fontsize=6.6, fontweight="bold")
    ax2.set_ylim(0, max_d * 1.48)
    ax2.set_xticks(x)
    ax2.set_xticklabels(corpora_lbl2)
    ax2.set_ylabel("Distance Evaluations / Query")
    ax2.set_title("(b) H3v3 Enriched (r>=2.0): GLS Savings")
    ax2.text(
        0.03, 0.96,
        f"P3b (tau_high=0.55 vs static-2hop):\n"
        f"  Quora: {v3b['quora']['eval_savings_x']:.2f}x fewer ({100*v3b['quora']['recall_diff']:+.2f} pt)\n"
        f"  NQ:    {v3b['nq']['eval_savings_x']:.2f}x fewer ({100*v3b['nq']['recall_diff']:+.2f} pt)",
        transform=ax2.transAxes, va="top", ha="left", fontsize=6.8,
        bbox=dict(boxstyle="round,pad=0.25", fc="#FDF2F8", ec="#CC79A7", lw=0.8),
    )

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    seen = {}
    for h, l in list(zip(h1, l1)) + list(zip(h2, l2)):
        seen.setdefault(l, h)
    fig.legend(list(seen.values()), list(seen.keys()), loc="lower center", bbox_to_anchor=(0.5, -0.15), ncol=3)
    fig.tight_layout()
    fig.subplots_adjust(wspace=0.28)
    _save(fig, "v3_fig3_h3_correlation_guard")


def plot_fig4_h4_and_latency(summary: dict) -> None:
    h4 = summary["hypotheses"]["H4_postgres"]["systems"]
    v4b = summary["verdicts"]["P4b"]
    bc_q = summary["hypotheses"]["H2_quora"]["by_condition"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.15))

    p4a = h4["P4a-path(SpiceDB-Postgres-Delete+mirror+UBP+bitmap)"]
    p4b = h4["pgvector-UPDATE-acl"]
    meds = [p4a["latency_ms_median"], p4b["latency_ms_median"]]
    maxs = [p4a["latency_ms_max"], p4b["latency_ms_max"]]
    low_e = [meds[0] - p4a["latency_ms_min"], meds[1] - p4b["latency_ms_min"]]
    hi_e = [maxs[0] - meds[0], maxs[1] - meds[1]]
    ax1.bar([0, 1], meds, width=0.46, yerr=[low_e, hi_e], capsize=4,
            color=["#D55E00", "#882255"], edgecolor="white", linewidth=0.7, zorder=3)
    ax1.set_yscale("log")
    ax1.set_ylim(10, maxs[1] * 12.0)
    ax1.set_xticks([0, 1])
    ax1.set_xticklabels([
        "SpiceDB (PostgreSQL 17)\nDelete + UBP + CRoaring\n(0 vector writes)",
        f"PostgreSQL 17 + pgvector\nUPDATE acl_allowed\n({int(p4b['rows_affected_median']):,} row writes)",
    ])
    ax1.set_ylabel("Revocation Latency (ms, log)")
    ax1.set_title("(a) H4v3 Persistent Revocation (n=5)")
    ax1.text(0, maxs[0] * 1.45, f"{meds[0]:.2f} ms\n(0 writes)", ha="center", va="bottom",
             fontsize=7.4, fontweight="bold", color="#D55E00")
    ax1.text(1, maxs[1] * 1.35, f"{meds[1]/1000:.1f} s\n({v4b['ratio']:,.1f}x slower)",
             ha="center", va="bottom", fontsize=7.4, fontweight="bold", color="#882255")

    s_keys = ["S=0.001", "S=0.005", "S=0.01", "S=0.05"]
    s_vals = [0.1, 0.5, 1.0, 5.0]
    order_lat = [
        "v3-full-guard-sq8", "v3-geom-M8", "exact-brute-force",
        "faiss-hnsw-M16", "acorn-1", "acorn-gamma", "hnswlib-M16", "pgvector-hnsw-iter",
    ]
    for sysname in order_lat:
        if sysname not in bc_q[s_keys[0]]:
            continue
        label, col, mk, ls, lw = SYS_STYLE[sysname]
        ys = [bc_q[sk][sysname]["latency_ms_median_pooled"] for sk in s_keys]
        ax2.plot(s_vals, ys, label=label, color=col, marker=mk, linestyle=ls, linewidth=lw,
                 zorder=4 if "v3" in sysname else 3)
    ax2.set_xscale("log")
    ax2.set_yscale("log")
    ax2.set_xticks(s_vals)
    ax2.set_xticklabels(["0.1%", "0.5%", "1%", "5%"])
    ax2.set_yticks([0.05, 0.1, 0.5, 1.0, 5.0, 20.0, 100.0, 500.0])
    ax2.set_yticklabels(["0.05", "0.1", "0.5", "1", "5", "20", "100", "500"])
    ax2.set_ylim(0.03, 900)
    ax2.set_xlabel("Filter Selectivity S (Quora N=522,931)")
    ax2.set_ylabel("Pooled Median Latency (ms, log)")
    ax2.set_title("(b) H2v3 Native C++ / NEON Latency")

    handles, labels = ax2.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.18), ncol=4)
    fig.tight_layout()
    fig.subplots_adjust(wspace=0.28)
    _save(fig, "v3_fig4_h4_revocation_and_neon_latency")


def plot_fig5_h5_portals(summary: dict) -> None:
    bc = summary["hypotheses"]["H5_quora"]["by_condition"]
    v5 = summary["verdicts"]["P5"]["by_S"]
    s_keys = ["S=0.001", "S=0.005", "S=0.01", "S=0.05"]
    s_lbls = ["0.1%", "0.5%", "1.0%", "5.0%"]
    variants = [
        "faiss-hnsw-M16",
        "faiss-M16+4portals",
        "hhnsw-v2-geom-M8-noportal",
        "v3-geom-M8",
    ]

    fig, ax = plt.subplots(figsize=(6.8, 3.05))
    x = np.arange(len(s_keys))
    w = 0.19
    for idx, sysname in enumerate(variants):
        label, col, _, _, _ = SYS_STYLE[sysname]
        ys = [100.0 * bc[sk][sysname]["recall_mean"]["mean"] for sk in s_keys]
        cis = [100.0 * (bc[sk][sysname]["recall_mean"]["ci95"] or 0.0) for sk in s_keys]
        off = (idx - 1.5) * w
        bars = ax.bar(x + off, ys, w * 0.88, yerr=cis, capsize=2.2, color=col, edgecolor="white", linewidth=0.6, label=label, zorder=3)
        for b, val, ci in zip(bars, ys, cis):
            ax.text(b.get_x() + b.get_width() / 2, val + ci + 1.5, f"{val:.1f}", ha="center", va="bottom", fontsize=6.8, fontweight="bold")

    ax.set_ylim(0, 122)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.set_xticks(x)
    ax.set_xticklabels([f"S = {lbl}" for lbl in s_lbls])
    ax.set_ylabel("Recall@10 (%) — 3-Seed Mean ± 95% CI")
    ax.set_title("H5v3 4-Way InitEntryPortals Ablation on Full BEIR Quora (N=522,931, Shared M=16 Graph)")
    ret_txt = " | ".join(
        f"S={sk.split('=')[1]}: {100.0 * v5[sk]['retained_gain_fraction']:.1f}%"
        for sk in ("S=0.001", "S=0.005", "S=0.01")
    )
    ax.text(
        0.02, 0.96,
        f"P5 Gain Retained w/ 0 Portals (vs. +4 Portals): {ret_txt}",
        transform=ax.transAxes, va="top", ha="left", fontsize=7.2,
        bbox=dict(boxstyle="round,pad=0.28", fc="#F2FBF5", ec="#117733", lw=0.8),
    )
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.34), ncol=2)
    fig.tight_layout()
    _save(fig, "v3_fig5_h5_portal_ablation")


def main() -> int:
    with open(SUMMARY_PATH, "r", encoding="utf-8") as f:
        summary = json.load(f)
    assert summary["freeze_match_all"] is True, "summary.json is not freeze_v3-matched!"
    plot_fig1_h1(summary)
    plot_fig2_h2(summary)
    plot_fig3_h3(summary)
    plot_fig4_h4_and_latency(summary)
    plot_fig5_h5_portals(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
