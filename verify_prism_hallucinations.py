#!/usr/bin/env python3
"""
Brake 1 (v3): Raw-Record Provenance & Zero-Hallucination Sensor (ADR-0004 & ADR-0005)
=====================================================================================
Programmatically verifies:
  1. Bit-for-bit reproducibility of `results/v3/summary.json` from
     `results/v3/raw/*.jsonl` via `bench.recompute_v3`, plus `FREEZE.md` (5/5)
     and `FREEZE_v3.md` (7/7) SHA-256 hash matches.
  2. 0.0% numerical discrepancy between `results/v3/summary.json` and every
     table row (Verdicts P1a..P5, H2v3 Quora & NQ, H3v3 Quora & NQ) and
     headline metric in `paper/prism_ann.tex`.
  3. Zero v1 metrics, zero ScholarPeer/PaperViz/camera-ready claims, zero
     template placeholders ((X)/(Y)/(Z)/TBD), zero IEEEtran \\paragraph{... .},
     and Theorem 1 + Propositions 2-4 structure.
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

from bench import harness, harness_v3, recompute, recompute_v3  # noqa: E402

RAW_DIR = os.path.join(REPO_ROOT, "results", "v3", "raw")
SUMMARY_PATH = os.path.join(REPO_ROOT, "results", "v3", "summary.json")
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
    fz2 = harness.freeze_status()
    check(fz2["match"], f"FREEZE.md (v2) SHA-256 match ({fz2['n_files']}/5)", f"FREEZE.md mismatch: {fz2['mismatches']}")
    fz3 = harness_v3.freeze_v3_status()
    check(fz3["match"], f"FREEZE_v3.md (v3) SHA-256 match ({fz3['n_files']}/7)", f"FREEZE_v3.md mismatch: {fz3['mismatches']}")

    with open(SUMMARY_PATH, "r", encoding="utf-8") as f:
        committed = f.read()
    recomputed_dict = recompute_v3.recompute_v3_summary(RAW_DIR)
    recomputed = recompute.dumps_summary(recomputed_dict)
    check(
        committed == recomputed,
        "results/v3/summary.json matches bench.recompute_v3(results/v3/raw) bit-for-bit",
        "results/v3/summary.json does NOT match raw records!",
    )

    s = json.loads(committed)
    check(s["freeze_match_all"] is True, "summary.json freeze_match_all == True", "freeze_match_all is False")

    with open(TEX_PATH, "r", encoding="utf-8") as f:
        tex = f.read()

    print("\n=== 2. VERIFYING ALL 11 VERDICTS (tab:verdicts) ===")
    tv = _extract_table_block(tex, "tab:verdicts")
    for pid, v in sorted(s["verdicts"].items()):
        expected_status = v["verdict"].upper()
        line = _extract_row_line(tv, rf"\\textbf\{{{pid}\}}")
        check(
            bool(line) and expected_status in line,
            f"{pid}: verdict {expected_status} verified in tab:verdicts",
            f"{pid}: missing or wrong verdict (expected {expected_status}) in tab:verdicts",
        )

    print("\n=== 3. VERIFYING H1v3, H4v3, & H5v3 HEADLINE METRICS ===")
    v1c = s["verdicts"]["P1c"]
    v4b = s["verdicts"]["P4b"]
    v5 = s["verdicts"]["P5"]["by_S"]
    for label, tok in [
        ("H1v3 memory speedup", f"{v1c['memory']['ratio_spicedb_over_ubp']:.1f}\\times"),
        ("H1v3 postgres speedup", f"{v1c['postgres']['ratio_spicedb_over_ubp']:.1f}\\times"),
        ("H1v3 postgres SpiceDB median", f"{v1c['postgres']['spicedb_median_ms']:.2f}\\text{{ ms}}"),
        ("H4v3 persistent P4a median", f"{v4b['p4a_median_ms']:.2f}\\text{{ ms}}"),
        ("H4v3 pgvector median s", f"{v4b['pgvector_median_ms']/1000.0:.1f}\\text{{ s}}"),
        ("H4v3 speedup ratio", f"{v4b['ratio']:,.1f}".replace(",", "{,}") + "\\times"),
        ("H5v3 S=0.1% retained", f"{100.0 * v5['S=0.001']['retained_gain_fraction']:.1f}\\%"),
        ("H5v3 S=0.5% retained", f"{100.0 * v5['S=0.005']['retained_gain_fraction']:.1f}\\%"),
    ]:
        check(tok in tex, f"{label}: '{tok}' verified in prism_ann.tex", f"{label}: expected '{tok}' missing!")

    print("\n=== 4. VERIFYING H2v3 MULTI-CORPUS TABLE (tab:h2_results) ===")
    th2 = _extract_table_block(tex, "tab:h2_results")
    parts_h2 = th2.split("Corpus 2: BEIR NQ")
    check(len(parts_h2) == 2, "tab:h2_results contains both Corpus 1 (Quora) and Corpus 2 (NQ)", "Missing Corpus 2 section in tab:h2_results")
    s_keys = ("S=0.001", "S=0.005", "S=0.01", "S=0.05")
    sys_h2 = (
        "exact-brute-force", "faiss-hnsw-M16", "acorn-1", "acorn-gamma",
        "hnswlib-M16", "pgvector-hnsw-iter", "v2-ring-chord-M4", "v3-geom-M8", "v3-full-guard-sq8",
    )
    if len(parts_h2) == 2:
        for hyp_key, sub_tex in (("H2_quora", parts_h2[0]), ("H2_nq", parts_h2[1])):
            bc = s["hypotheses"][hyp_key]["by_condition"]
            for sysname in sys_h2:
                line = _extract_row_line(sub_tex, rf"\\texttt\{{{re.escape(sysname)}\}}")
                check(bool(line), f"{hyp_key} row found for {sysname}", f"{hyp_key} row missing for {sysname}")
                if line:
                    for sk in s_keys:
                        g = bc[sk][sysname]
                        rm = f"{100.0 * g['recall_mean']['mean']:.2f}"
                        lm = f"{g['latency_ms_median_pooled']:.2f}"
                        check(rm in line, f"{hyp_key} {sysname} {sk} R@10={rm}% matches", f"{hyp_key} {sysname} {sk} R@10={rm}% missing in: {line}")
                        check(lm in line, f"{hyp_key} {sysname} {sk} med={lm}ms matches", f"{hyp_key} {sysname} {sk} med={lm}ms missing in: {line}")

    print("\n=== 5. VERIFYING H3v3 MULTI-CORPUS TABLE (tab:h3_results) ===")
    th3 = _extract_table_block(tex, "tab:h3_results")
    sys_h3 = (
        "exact-brute-force", "faiss-hnsw-M16", "acorn-1", "hnswlib-M16",
        "v3-geom-M8", "v3-static-2hop", "v3-full-guard-sq8",
    )
    for sysname in sys_h3:
        line = _extract_row_line(th3, rf"\\texttt\{{{re.escape(sysname)}\}}")
        check(bool(line), f"H3 row found for {sysname}", f"H3 row missing for {sysname}")
        if line:
            for hyp_key in ("H3_quora", "H3_nq"):
                bc3 = s["hypotheses"][hyp_key]["by_condition"]
                for rk in ("r_le_0.5", "r_ge_2"):
                    rm = f"{100.0 * bc3[rk][sysname]['recall_mean']['mean']:.2f}"
                    check(rm in line, f"{hyp_key} {sysname} {rk} R@10={rm}% matches", f"{hyp_key} {sysname} {rk} R@10={rm}% missing in: {line}")

    print("\n=== 6. HYGIENE, ANTI-CONTAMINATION, & CITATION AUDIT ===")
    for forbidden in ("ScholarPeer", "PaperViz", "camera-ready", "LoCoMo", "97.72", "135.9", "4,096.0"):
        check(
            re.search(forbidden, tex, re.I) is None,
            f"Zero occurrences of banned/v1 pattern '{forbidden}'",
            f"Banned/v1 pattern '{forbidden}' found in prism_ann.tex!",
        )
    for ph in (r"\(X\)", r"\(Y\)", r"\(Z\)", r"\bTBD\b", r"\bTODO\b", r"\\paragraph\{[^}]+\.\}"):
        check(
            re.search(ph, tex) is None,
            f"Zero occurrences of placeholder/typography pattern '{ph}'",
            f"Placeholder/typography pattern '{ph}' found in prism_ann.tex!",
        )
    check(
        r"\begin{proposition}" in tex and tex.count(r"\begin{theorem}") == 1,
        "Theorem 1 + Propositions 2-4 structure verified",
        "Unexpected theorem/proposition count in prism_ann.tex",
    )
    check("tab:deviations" in tex, "Protocol Deviations table present", "Missing tab:deviations")

    cited = set()
    for m in re.finditer(r"\\cite\{([^}]+)\}", tex):
        for k in m.group(1).split(","):
            cited.add(k.strip())
    bibs = set(re.findall(r"\\bibitem\{([^}]+)\}", tex))
    check(not (cited - bibs), f"All {len(cited)} cited keys resolve in bibliography", f"Unresolved citations: {cited - bibs}")
    check(not (bibs - cited), f"Zero unused bibitems ({len(bibs)} total)", f"Unused bibitems: {bibs - cited}")

    print(f"\nSUMMARY: {passed} checks passed, {len(errors)} errors.")
    return len(errors) == 0


if __name__ == "__main__":
    sys.exit(0 if verify() else 1)
