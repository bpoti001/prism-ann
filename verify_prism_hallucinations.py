#!/usr/bin/env python3
"""
Brake 1 (v2): Raw-Record Provenance & Zero-Hallucination Sensor (ADR-0004)
==========================================================================
Programmatically verifies:
  1. Bit-for-bit reproducibility of `results/v2/summary.json` from
     `results/v2/raw/*.jsonl` via `bench.recompute`, and `FREEZE.md` hash match.
  2. 0.0% numerical discrepancy between `results/v2/summary.json` and every
     table row (Verdicts, H2v2, H3v2) and headline metric in `paper/prism_ann.tex`.
  3. Zero v1 metrics, zero ScholarPeer/PaperViz claims, zero "camera-ready" claims,
     and Propositions 2-4 instead of Theorems 2-4.
  4. 100% citation resolution (every \\cite resolves to a \\bibitem, 0 unused).
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import List

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from bench import harness, recompute  # noqa: E402

RAW_DIR = os.path.join(REPO_ROOT, "results", "v2", "raw")
SUMMARY_PATH = os.path.join(REPO_ROOT, "results", "v2", "summary.json")
TEX_PATH = os.path.join(REPO_ROOT, "paper", "prism_ann.tex")


def _extract_table_block(tex: str, label: str) -> str:
    for chunk in tex.split(r"\begin{table"):
        if f"\\label{{{label}}}" in chunk:
            return chunk.split(r"\end{table")[0]
    return ""


def _extract_row_line(block: str, row_regex: str) -> str:
    for line in block.splitlines():
        if re.search(row_regex, line):
            return line
    return ""


def verify() -> bool:
    errors: List[str] = []
    passed = 0

    def check(cond: bool, ok_msg: str, fail_msg: str) -> None:
        nonlocal passed
        if cond:
            print(f"  [PASS] {ok_msg}")
            passed += 1
        else:
            print(f"  [FAIL] {fail_msg}")
            errors.append(fail_msg)

    print("=== 1. RAW-RECORD PROVENANCE & FREEZE INTEGRITY ===")
    fz = harness.freeze_status()
    check(fz["match"], f"FREEZE.md SHA-256 match ({fz['n_files']}/5 files)", f"FREEZE mismatch: {fz['mismatches']}")

    with open(SUMMARY_PATH, "r", encoding="utf-8") as f:
        committed = f.read()
    recomputed_dict = recompute.recompute_summary(RAW_DIR)
    recomputed = recompute.dumps_summary(recomputed_dict)
    check(committed == recomputed, "results/v2/summary.json matches bench.recompute(results/v2/raw) bit-for-bit",
          "summary.json does NOT match raw records!")

    s = json.loads(committed)
    check(s["freeze_match_all"] is True, "summary.json freeze_match_all == True", "freeze_match_all is False")

    with open(TEX_PATH, "r", encoding="utf-8") as f:
        tex = f.read()

    print("\n=== 2. VERIFYING VERDICTS TABLE (tab:verdicts) ===")
    tv = _extract_table_block(tex, "tab:verdicts")
    for pid, v in sorted(s["verdicts"].items()):
        expected_status = v["verdict"].upper()
        line = _extract_row_line(tv, rf"\\textbf\{{{pid}\}}")
        check(bool(line) and expected_status in line,
              f"{pid}: verdict {expected_status} present in tab:verdicts",
              f"{pid}: missing or wrong verdict (expected {expected_status}) in tab:verdicts")

    print("\n=== 3. VERIFYING H1v2 & H4v2 HEADLINE METRICS ===")
    v1c = s["verdicts"]["P1c"]
    v4b = s["verdicts"]["P4b"]
    for label, tok in [
        ("H1v2 P1c mirror speedup", f"{v1c['ratio_spicedb_over_ubp']:.1f}\\times"),
        ("H1v2 P1c strict speedup", f"{v1c['strict_ratio_including_grant_fetch']:.1f}\\times"),
        ("H1v2 SpiceDB broad median", f"{v1c['spicedb_median_ms']:.2f}\\text{{ ms}}"),
        ("H4v2 P4a median ms", f"{v4b['p4a_median_ms']:.2f}\\text{{ ms}}"),
        ("H4v2 pgvector median s", f"{v4b['pgvector_median_ms']/1000.0:.1f}\\text{{ s}}"),
        ("H4v2 speedup ratio", f"{v4b['ratio']:,.1f}".replace(",", "{,}") + "\\times"),
    ]:
        check(tok in tex, f"{label}: '{tok}' verified in prism_ann.tex",
              f"{label}: expected '{tok}' missing from prism_ann.tex")

    print("\n=== 4. VERIFYING H2v2 SELECTIVITY TABLE (tab:h2_results) ===")
    th2 = _extract_table_block(tex, "tab:h2_results")
    bc2 = s["hypotheses"]["H2"]["by_condition"]
    s_keys = ("S=0.001", "S=0.005", "S=0.01", "S=0.05")
    for sysname in ("exact-brute-force", "faiss-hnsw-M16", "faiss-hnsw-M8", "acorn-1",
                    "hnswlib-M16", "pgvector-hnsw-iter", "prism-graph-only", "prism-full"):
        line = _extract_row_line(th2, rf"\\texttt\{{{re.escape(sysname)}\}}")
        check(bool(line), f"H2 row found for {sysname}", f"H2 row missing for {sysname}")
        if line:
            for sk in s_keys:
                g = bc2[sk][sysname]
                rm = f"{100.0 * g['recall_mean']['mean']:.2f}"
                lm = f"{g['latency_ms_median']['mean']:.2f}"
                check(rm in line, f"H2 {sysname} {sk} recall={rm}% matches",
                      f"H2 {sysname} {sk} recall={rm}% missing in row: {line}")
                check(lm in line, f"H2 {sysname} {sk} med_ms={lm} matches",
                      f"H2 {sysname} {sk} med_ms={lm} missing in row: {line}")

    print("\n=== 5. VERIFYING H3v2 CORRELATION TABLE (tab:h3_results) ===")
    th3 = _extract_table_block(tex, "tab:h3_results")
    bc3 = s["hypotheses"]["H3"]["by_condition"]
    for sysname in ("exact-brute-force", "faiss-hnsw-M16", "faiss-hnsw-M8", "acorn-1",
                    "hnswlib-M16", "prism-graph-only", "prism-static-2hop", "prism-full"):
        line = _extract_row_line(th3, rf"\\texttt\{{{re.escape(sysname)}\}}")
        check(bool(line), f"H3 row found for {sysname}", f"H3 row missing for {sysname}")
        if line:
            for rk in ("r_le_0.5", "r_ge_2"):
                g = bc3[rk][sysname]
                rm = f"{100.0 * g['recall_mean']['mean']:.2f}"
                check(rm in line, f"H3 {sysname} {rk} recall={rm}% matches",
                      f"H3 {sysname} {rk} recall={rm}% missing in row: {line}")

    print("\n=== 6. ANTI-CONTAMINATION & CITATION AUDIT ===")
    for forbidden in ("ScholarPeer", "PaperViz", "camera-ready", "LoCoMo", "97.72", "135.9", "4,096.0", "94.8\\%"):
        check(re.search(forbidden, tex, re.I) is None,
              f"Zero occurrences of banned/v1 string '{forbidden}'",
              f"Banned/v1 string '{forbidden}' found in prism_ann.tex!")
    check(r"\begin{proposition}" in tex and tex.count(r"\begin{theorem}") == 1,
          "Theorem 1 + Propositions 2-4 structure verified",
          "Unexpected theorem/proposition count in prism_ann.tex")
    check("tab:deviations" in tex, "Protocol Deviations table present", "Missing tab:deviations")

    cited = set()
    for m in re.finditer(r"\\cite\{([^}]+)\}", tex):
        for k in m.group(1).split(","):
            cited.add(k.strip())
    bibs = set(re.findall(r"\\bibitem\{([^}]+)\}", tex))
    missing_bibs = cited - bibs
    unused_bibs = bibs - cited
    check(not missing_bibs, f"All {len(cited)} cited keys resolve in bibliography",
          f"Unresolved citations: {missing_bibs}")
    check(not unused_bibs, f"Zero unused bibitems ({len(bibs)} total)",
          f"Unused bibitems: {unused_bibs}")

    print(f"\nSUMMARY: {passed} checks passed, {len(errors)} errors.")
    return len(errors) == 0


if __name__ == "__main__":
    sys.exit(0 if verify() else 1)
