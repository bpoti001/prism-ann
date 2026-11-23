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

    print("\n[7/7] Checking v3.1 External Reviewer Audit provenance & paper/report consistency...")
    import json as _json
    from pathlib import Path as _Path
    from bench.recompute import dumps_summary as _dumps_summary
    from bench.recompute_v3_1 import recompute_v3_1_summary as _recompute_v3_1, freeze_v3_1_status as _freeze_v3_1

    f31 = _freeze_v3_1()
    check(f31.get("match") is True and f31.get("n_files") == 8,
          f"FREEZE_v3_1.md {f31.get('n_files')}/8 SHA-256 intact",
          f"FREEZE_v3_1 mismatch: {f31}")

    audit_path = _Path("results/v3/reviewer_audit_v3_1.json")
    raw_v31_path = _Path("results/v3_1_audit/raw/v3_1_reviewer_audit.jsonl")
    report_path = _Path("REVIEWER_AUDIT_REPORT.md")
    check(audit_path.exists() and raw_v31_path.exists() and report_path.exists(),
          "v3.1 reviewer audit JSON, raw JSONL, and REVIEWER_AUDIT_REPORT.md exist",
          "Missing v3.1 reviewer audit artifact")

    if audit_path.exists() and raw_v31_path.exists() and report_path.exists():
        audit_text = audit_path.read_text(encoding="utf-8")
        audit = _json.loads(audit_text)
        recomp_v31 = _recompute_v3_1(str(raw_v31_path))
        check(_dumps_summary(recomp_v31) == audit_text,
              "results/v3/reviewer_audit_v3_1.json matches deterministic recompute_v3_1.py bit-for-bit",
              "reviewer_audit_v3_1.json differs from recompute_v3_1.py")

        n_rec = audit.get("raw_records_total", 0)
        check(n_rec == 22533, f"v3.1 raw JSONL total == {n_rec}", f"Expected 22533 raw records, got {n_rec}")
        check(audit.get("git_dirty") is False,
              "v3.1 audit ran on clean git tree (git_dirty == False)",
              f"git_dirty is {audit.get('git_dirty')}")

        verdicts = audit.get("verdicts", {})
        for pr in ("PR1", "PR2", "PR3", "PR4", "PR5"):
            st = verdicts.get(pr, {}).get("verdict")
            check(st == "supported", f"v3.1 {pr} verdict == {st}", f"v3.1 {pr} verdict is {st}")

        r2_blk = audit["R2_s001_ultra_low_selectivity"]
        check(
            r2_blk["quora"].get("leaks_total") == 0 and r2_blk["nq"].get("leaks_total") == 0,
            "v3.1 R2 leaks_total == 0 on both Quora and NQ",
            f"Non-zero leaks in R2: quora={r2_blk['quora'].get('leaks_total')}, nq={r2_blk['nq'].get('leaks_total')}",
        )

        report_txt = report_path.read_text(encoding="utf-8")
        readme_txt = _Path("README.md").read_text(encoding="utf-8")
        r1 = audit["R1_property_fuzzing"]
        pr2 = verdicts["PR2"]
        pr3_attr = verdicts["PR3"]["cold_S0.01_attribution"]
        pr3_warm_attr = audit["R3_mode3_component_isolation"]["S=0.01"]["warm_attribution"]
        pr3_sq8_scalar_ms = verdicts["PR3"]["cold_S0.01_sq8_scalar_ms"]
        r4 = audit["R4_revocation_scaling_and_concurrent_zedtoken"]
        r4_sc = r4["scaling_postgres_spicedb"]
        r4a_min = min(float(row["median_ms"]) for row in r4_sc)
        r4a_max = max(float(row["median_ms"]) for row in r4_sc)
        r4b = r4["concurrent_zedtoken_race"]
        max_chunks = r4_sc[-1]["chunks_revoked"]
        r5_batches = audit["R5_dynamic_ingestion_and_zorder_compaction"]["batches"]
        r5_min_us = min(float(b["delta_append_us_per_vec"]) for b in r5_batches)
        r5_max_us = max(float(b["delta_append_us_per_vec"]) for b in r5_batches)
        r5_max_csr = max(float(b["cpp_csr_remap_only_ms"]) for b in r5_batches)

        fmt_checks = [
            ("total records", f"{n_rec:,}", f"{n_rec:,}".replace(",", "{,}")),
            ("R1 total trials", f"{r1['total_trials']:,}", f"{r1['total_trials']:,}".replace(",", "{,}")),
            ("R2 Quora v3-geom R@10", f"{pr2['quora']['v3_geom_recall_pct']:.2f}%", f"{pr2['quora']['v3_geom_recall_pct']:.2f}\\%"),
            ("R2 NQ v3-geom R@10", f"{pr2['nq']['v3_geom_recall_pct']:.2f}%", f"{pr2['nq']['v3_geom_recall_pct']:.2f}\\%"),
            ("R2 Quora v3-full med ms", f"{pr2['quora']['v3_full_med_ms']:.3f}", f"{pr2['quora']['v3_full_med_ms']:.3f}"),
            ("R2 NQ v3-full med ms", f"{pr2['nq']['v3_full_med_ms']:.3f}", f"{pr2['nq']['v3_full_med_ms']:.3f}"),
            ("R3 cold total speedup", f"{pr3_attr['total_gain_over_scattered_scalar_f32']:.2f}", f"{pr3_attr['total_gain_over_scattered_scalar_f32']:.2f}"),
            ("R3 warm total speedup", f"{pr3_warm_attr['total_gain_over_scattered_scalar_f32']:.2f}", f"{pr3_warm_attr['total_gain_over_scattered_scalar_f32']:.2f}"),
            ("R3 cold zorder gain", f"{pr3_attr['zorder_gain_on_neon_f32']:.2f}", f"{pr3_attr['zorder_gain_on_neon_f32']:.2f}"),
            ("R3 cold sq8 gain", f"{pr3_attr['sq8_gain_on_scalar']:.2f}", f"{pr3_attr['sq8_gain_on_scalar']:.2f}"),
            ("R3 cold neon gain", f"{pr3_attr['neon_gain_on_sq8']:.2f}", f"{pr3_attr['neon_gain_on_sq8']:.2f}"),
            ("R3 cold scalar SQ8 ms", f"{pr3_sq8_scalar_ms:.4f}", f"{pr3_sq8_scalar_ms:.3f}"),
            ("R4a max chunks revoked", f"{max_chunks:,}", f"{max_chunks:,}".replace(",", "{,}")),
            ("R4a min median ms", f"{r4a_min:.2f}", f"{r4a_min:.2f}"),
            ("R4a max median ms", f"{r4a_max:.2f}", f"{r4a_max:.2f}"),
            ("R4b concurrent queries", f"{r4b['total_concurrent_queries']:,}", f"{r4b['total_concurrent_queries']:,}".replace(",", "{,}")),
            ("R4b post-zeta queries", f"{r4b['post_revoke_zeta2_queries']:,}", f"{r4b['post_revoke_zeta2_queries']:,}".replace(",", "{,}")),
            ("R4b PG17 commit ms", f"{r4b['spicedb_commit_ms']:.2f}", f"{r4b['spicedb_commit_ms']:.2f}"),
            ("R4b atomic swap ms", f"{r4b['atomic_snapshot_compile_and_swap_ms']:.3f}", f"{r4b['atomic_snapshot_compile_and_swap_ms']:.3f}"),
            ("R5 min append us/vec", f"{r5_min_us:.2f}", f"{r5_min_us:.1f}"),
            ("R5 max append us/vec", f"{r5_max_us:.2f}", f"{r5_max_us:.1f}"),
            ("R5 max CSR remap ms", f"{r5_max_csr:.2f}", f"{r5_max_csr:.1f}"),
        ]
        for label, md_tok, tex_tok in fmt_checks:
            check(md_tok in report_txt, f"REVIEWER_AUDIT_REPORT.md contains {label} ({md_tok})",
                  f"REVIEWER_AUDIT_REPORT.md missing {label}: {md_tok}")
            check(tex_tok in tex, f"paper/prism_ann.tex contains {label} ({tex_tok})",
                  f"paper/prism_ann.tex missing {label}: {tex_tok}")
        conc_str = f"{r4b['total_concurrent_queries']:,}"
        check(conc_str in readme_txt, f"README.md contains R4b concurrent queries ({conc_str})",
              f"README.md missing R4b concurrent queries: {conc_str}")

    print(f"\nSUMMARY: {passed} checks passed, {len(errors)} errors.")
    return len(errors) == 0


if __name__ == "__main__":
    sys.exit(0 if verify() else 1)
