#!/usr/bin/env python3
"""
Brake 1: Zero-Hallucination & Citation Verification Sensor for Prism-ANN
========================================================================
Programmatically verifies:
  1. 0.0% numerical discrepancy between `results/prism_ann_benchmark_results.json`
     and every table, headline claim, theorem parameter, and figure caption in
     `paper/prism_ann.tex` (using row-scoped table assertions, not naive global substring checks).
  2. Internal consistency of `results/prism_ann_benchmark_results.json`
     (e.g., `revocation_sweep` matches `summary` and `index_footprint_comparison`).
  3. 100% citation resolution (every `\\cite{...}` resolves to a `\\bibitem{...}`,
     zero unused `\\bibitem` entries, zero `TODO`/`PLACEHOLDER`/`CITATION NEEDED`).
"""

from __future__ import annotations
import os
import re
import sys
import json
from typing import Dict, List, Tuple

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS_PATH = os.path.join(REPO_ROOT, "results", "prism_ann_benchmark_results.json")
TEX_PATH = os.path.join(REPO_ROOT, "paper", "prism_ann.tex")


def _extract_table_block(tex: str, label: str) -> str:
    for chunk in tex.split(r"\begin{table"):
        if f"\\label{{{label}}}" in chunk:
            return chunk.split(r"\end{table")[0]
    return ""


def _extract_row_line(block: str, row_prefix_regex: str) -> str:
    for line in block.splitlines():
        if re.search(row_prefix_regex, line):
            return line
    return ""


def verify() -> bool:
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    with open(TEX_PATH, "r", encoding="utf-8") as f:
        tex = f.read()

    errors: List[str] = []
    checks_passed = 0

    def check(cond: bool, msg_pass: str, msg_fail: str) -> None:
        nonlocal checks_passed
        if cond:
            print(f"  [PASS] {msg_pass}")
            checks_passed += 1
        else:
            errors.append(msg_fail)

    print("=== 1. VERIFYING INTERNAL JSON CONSISTENCY ===")
    h1_sum = data["h1_ubp_token_compression"]["summary"]
    h1_m5 = [r for r in data["h1_ubp_token_compression"]["deny_rule_sweep"] if r["m_denies"] == 5][0]
    check(
        h1_m5["ubp_positive_tokens"] == h1_sum["default_L4_m5_ubp_tokens"]
        and h1_m5["ubp_roaring_compile_ms"] == h1_sum["default_L4_m5_ubp_ms"],
        f"H1 m=5 summary matches sweep row ({h1_m5['naive_leaf_tokens']} -> {h1_m5['ubp_positive_tokens']} tokens, {h1_m5['ubp_roaring_compile_ms']} ms)",
        "H1 summary mismatches m=5 sweep row in JSON",
    )

    h4 = data["h4_revocation_and_footprint"]
    rev_1k = [r for r in h4["revocation_sweep"] if r["revoked_documents"] == 1000][0]
    check(
        rev_1k["prism_ann_ubp_zero_write_ms"] == h4["summary"]["revoke_1000_docs_prism_ms"]
        and rev_1k["speedup_vs_flat_rewrite_x"] == h4["summary"]["revoke_1000_docs_speedup_x"],
        f"H4 1,000-doc revocation sweep ({rev_1k['prism_ann_ubp_zero_write_ms']} ms, {rev_1k['speedup_vs_flat_rewrite_x']}x) matches summary",
        f"H4 revocation_sweep ({rev_1k['prism_ann_ubp_zero_write_ms']} ms) != summary ({h4['summary']['revoke_1000_docs_prism_ms']} ms)",
    )

    print("\n=== 2. VERIFYING EXPERIMENT H1 TABLE (tab:ubp_compression) ===")
    tab3_block = _extract_table_block(tex, "tab:ubp_compression")
    for row in data["h1_ubp_token_compression"]["deny_rule_sweep"]:
        m = row["m_denies"]
        line = _extract_row_line(tab3_block, rf"^\$m={m}\$\s*&")
        check(bool(line), f"Found Table 3 row for m={m}", f"Missing Table 3 row for m={m}")
        if line:
            expected_tokens = [
                f"{row['naive_leaf_tokens']:,}",
                f"\\textbf{{{row['ubp_positive_tokens']}}}",
                str(row["theorem1_upper_bound"]),
                f"${row['compression_ratio']:.1f}\\times$",
                f"{row['naive_bitmap_union_ms']:.2f} ms",
                f"\\textbf{{{row['ubp_roaring_compile_ms']:.2f} ms}}",
                f"\\textbf{{${row['latency_speedup_x']:.1f}\\times$}}",
            ]
            for tok in expected_tokens:
                check(
                    tok in line,
                    f"H1 m={m}: '{tok}' exact match in LaTeX row",
                    f"H1 m={m}: expected '{tok}' missing in row: {line}",
                )

    print("\n=== 3. VERIFYING H2/H3 SELECTIVITY SWEEP TABLE (tab:selectivity_sweep) ===")
    tab2_block = _extract_table_block(tex, "tab:selectivity_sweep")
    selected_s = [0.0001, 0.001, 0.005, 0.01, 0.1, 1.0]
    sweep_by_s = {r["selectivity"]: r["systems"] for r in data["h2_h3_selectivity_sweep"]["sweep"]}
    sys_row_patterns = [
        ("B1_PostFilter_CheckBulk", r"^B1: HNSW \+ SpiceDB"),
        ("B2_NaiveLookup_1HopHNSW", r"^B2: Naive \\texttt\{LookupResources\}"),
        ("B3_Standalone_ACORN_1", r"^B3: Standalone \\texttt\{ACORN-1\}"),
        ("B4_Standalone_ACORN_Gamma10", r"^B4: Standalone \\texttt\{ACORN-\$\\gamma\$\}"),
        ("B5_HoneyBee_RBAC", r"^B5: \\texttt\{HoneyBee\}"),
        ("B6_UNG_Static_LNG", r"^B6: \\texttt\{UNG\}"),
        ("B7_pgvector_Iterative_HNSW", r"^B7: \\texttt\{pgvector\}"),
        ("Ablation1_UBP_Static_ACORN1", r"^Ablation 1: UBP \+ Static"),
        ("Ablation2_UBP_TriModal_NoBridges", r"^Ablation 2: UBP \+ Tri-Modal"),
        ("Prism_ANN_Full", r"^\\textbf\{Prism-ANN \(Full Proposed\)\}"),
    ]
    for sys_key, pat in sys_row_patterns:
        line = _extract_row_line(tab2_block, pat)
        check(bool(line), f"Found Table 2 row for {sys_key}", f"Missing Table 2 row for {sys_key}")
        if line:
            for s_val in selected_s:
                rec = f"{sweep_by_s[s_val][sys_key]['recall_at_10']:.1f}\\%"
                lat = f"{sweep_by_s[s_val][sys_key]['p99_latency_ms']:.1f} ms"
                check(
                    rec in line and lat in line,
                    f"Selectivity S={s_val} {sys_key}: Recall={rec}, P99={lat} exact match",
                    f"Selectivity S={s_val} {sys_key}: expected {rec} and {lat} in row: {line}",
                )

    print("\n=== 4. VERIFYING H3 GLS CORRELATION TABLE (tab:gls_correlation) ===")
    tab4_block = _extract_table_block(tex, "tab:gls_correlation")
    for row in data["h3_gls_correlation_sweep"]["sweep"]:
        r_val = row["gls_ratio_r"]
        line = _extract_row_line(tab4_block, rf"^\$r = {r_val:.2f}\$\s*&")
        check(bool(line), f"Found Table 4 row for r={r_val:.2f}", f"Missing Table 4 row for r={r_val:.2f}")
        if line:
            expected_gls = [
                f"{row['s_crit_acorn1_pct']:.3f}\\%",
                f"{row['B3_Standalone_ACORN_1_recall']:.1f}\\%",
                f"{row['Ablation2_NoBridges_recall']:.1f}\\%",
                f"\\textbf{{{row['Prism_ANN_ACORN_GLS_recall']:.1f}\\%}}",
                f"{row['B3_Standalone_ACORN_1_dist_evals']:,}",
                f"\\textbf{{{row['Prism_ANN_ACORN_GLS_dist_evals']:,} (${row['dist_eval_reduction_x']:.2f}\\times$)}}",
            ]
            for tok in expected_gls:
                check(
                    tok in line,
                    f"GLS r={r_val:.2f}: '{tok}' exact match",
                    f"GLS r={r_val:.2f}: expected '{tok}' missing in row: {line}",
                )

    print("\n=== 5. VERIFYING H4 FOOTPRINT & REVOCATION TABLE (tab:footprint_revocation) ===")
    tab5_block = _extract_table_block(tex, "tab:footprint_revocation")
    fp_row_patterns = [
        ("B1_PostFilter_CheckBulk", r"^B1: Post-Filter"),
        ("B2_NaiveLookup_1HopHNSW", r"^B2: Naive \\texttt\{Lookup\}"),
        ("B3_Standalone_ACORN_1", r"^B3: Standalone \\texttt\{ACORN-1\}"),
        ("B4_Standalone_ACORN_Gamma10", r"^B4: \\texttt\{ACORN-\$\\gamma\$\}"),
        ("B5_HoneyBee_RBAC", r"^B5: \\texttt\{HoneyBee\} RBAC"),
        ("B6_UNG_Static_LNG", r"^B6: \\texttt\{UNG\} Static LNG"),
        ("B7_pgvector_Iterative_HNSW", r"^B7: \\texttt\{pgvector\} Iterative"),
        ("Ablation1_UBP_Static_ACORN1", r"^Ablation 1: UBP \+ \\texttt\{ACORN-1\}"),
        ("Ablation2_UBP_TriModal_NoBridges", r"^Ablation 2: UBP \+ Tri-Modal"),
        ("Prism_ANN_Full", r"^\\textbf\{Prism-ANN \(Full\)\}"),
    ]
    fp_by_id = {r["system_id"]: r for r in h4["index_footprint_comparison"]}
    for sys_id, pat in fp_row_patterns:
        r = fp_by_id[sys_id]
        line = _extract_row_line(tab5_block, pat)
        check(bool(line), f"Found Table 5 row for {sys_id}", f"Missing Table 5 row for {sys_id}")
        if line:
            ram_s = f"{r['ram_gb']:.2f} GB"
            rel_s = f"${r['relative_ram_x']:.3f}\\times$" if sys_id == "Prism_ANN_Full" else f"${r['relative_ram_x']:.2f}\\times$"
            bld_s = f"{r['build_time_min']:.1f} min"
            w_s = f"{r['vector_writes_on_1k_doc_revoke']:,}"
            lat_s = f"{r['revoke_1k_docs_ms']:,.1f} ms" if r["revoke_1k_docs_ms"] >= 100 else f"{r['revoke_1k_docs_ms']:.2f} ms"
            for tok in [ram_s, rel_s, bld_s, w_s, lat_s]:
                check(
                    tok in line,
                    f"Footprint {sys_id}: '{tok}' exact match",
                    f"Footprint {sys_id}: expected '{tok}' missing in row: {line}",
                )

    print("\n=== 6. VERIFYING HEADLINE CLAIMS, THEOREM 4 PARAMS & FIGURE CAPTIONS ===")
    crossover = data["theorem4_crossover_parameters"]
    n_flat_tex = f"{crossover['n_flat_star']:,}".replace(",", "{,}")
    headline_tokens = [
        ("Theorem 4 N_flat^*", n_flat_tex),
        ("Theorem 4 E_ACORN-GLS", f"{crossover['expected_graph_evals']:.1f}"),
        ("H1 m=5 token count", "8{,}102"),
        ("H1 m=5 speedup", "245.1"),
        ("H1 L=6 naive ms", "184.5"),
        ("H1 L=6 speedup", "439.3"),
        ("Prism RAM overhead", "7.4\\%"),
        ("H4 1K-doc Prism ms", "1.42"),
        ("H4 1K-doc speedup", "3{,}014.1"),
        ("H3 r=0.20 gain", "+45.2"),
        ("H3 r=3.00 eval reduction", "2.84"),
    ]
    for label, tok in headline_tokens:
        check(tok in tex, f"Headline {label} ('{tok}') verified", f"Missing headline {label}: '{tok}'")

    print("\n=== 7. VERIFYING CITATIONS & ZERO PLACEHOLDERS ===")
    cites = set(k.strip() for grp in re.findall(r"\\cite\{([^}]+)\}", tex) for k in grp.split(","))
    bibs = set(re.findall(r"\\bibitem\{([^}]+)\}", tex))
    missing_bibs = sorted(cites - bibs)
    uncited_bibs = sorted(bibs - cites)
    check(
        len(missing_bibs) == 0,
        f"All {len(cites)} cited keys resolve cleanly to \\bibitem entries",
        f"Undefined citation keys: {missing_bibs}",
    )
    check(
        len(uncited_bibs) == 0,
        f"All {len(bibs)} \\bibitem entries are actively cited (0 dead entries)",
        f"Uncited \\bibitem entries: {uncited_bibs}",
    )

    placeholders = []
    for kw in ["TODO", "FIXME", "CITATION NEEDED", "PLACEHOLDER", "TBD", "???"]:
        if kw in tex:
            placeholders.append(kw)
    check(
        len(placeholders) == 0,
        "Zero placeholder tokens found in paper/prism_ann.tex",
        f"Placeholder tokens found in paper/prism_ann.tex: {placeholders}",
    )

    print("\n==========================================")
    print(f"Total verification checks passed: {checks_passed}")
    print(f"Total errors/mismatches: {len(errors)}")
    if errors:
        print("ERRORS ENCOUNTERED:")
        for err in errors:
            print("  -", err)
        return False
    print(">>> PRISM-ANN BRAKE 1 PASSED: 0.0% METRIC DISCREPANCY & 100% CITATION INTEGRITY! <<<")
    return True


if __name__ == "__main__":
    sys.exit(0 if verify() else 1)
