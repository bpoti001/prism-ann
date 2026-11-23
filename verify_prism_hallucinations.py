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
    n_thms = tex.count(r"\begin{theorem}")
    check(
        r"\begin{proposition}" in tex and n_thms in (1, 2),
        f"Theorems 1..{n_thms} + Propositions 2-4 structure verified",
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

    print("\n[8/8] Checking v3.2 Second-Round Audit provenance, R6-R8 metrics, citations & 3-tier docs...")
    from bench.recompute_v3_2 import recompute_v3_2_summary as _recompute_v3_2

    audit32_path = _Path("results/v3/reviewer_audit_v3_2.json")
    raw_v32_path = _Path("results/v3_2_audit/raw/v3_2_reviewer_audit.jsonl")
    nov_path = _Path("docs/RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md")
    onb_path = _Path("docs/ONBOARDING_NEW_GRAD.md")
    arch_path = _Path("docs/ARCHITECTURE_SENIOR_ENGINEER.md")
    check(
        audit32_path.exists() and raw_v32_path.exists() and nov_path.exists() and onb_path.exists() and arch_path.exists(),
        "v3.2 audit JSON/JSONL and all 3 audience docs exist",
        "Missing v3.2 audit JSON/JSONL or one of the 3 audience docs",
    )
    if audit32_path.exists() and raw_v32_path.exists() and nov_path.exists():
        audit32_txt = audit32_path.read_text(encoding="utf-8")
        a32 = _json.loads(audit32_txt)
        recomp_v32 = _recompute_v3_2(str(raw_v32_path))
        check(
            _dumps_summary(recomp_v32) == audit32_txt,
            "results/v3/reviewer_audit_v3_2.json matches deterministic recompute_v3_2.py bit-for-bit",
            "reviewer_audit_v3_2.json differs from recompute_v3_2.py",
        )
        check(a32.get("raw_records_total") == 6821, "v3.2 raw JSONL total == 6821", f"Expected 6821 raw records, got {a32.get('raw_records_total')}")
        check(a32.get("git_dirty") is False, "v3.2 audit ran on clean git tree (git_dirty == False)", f"v3.2 git_dirty is {a32.get('git_dirty')}")
        check(a32.get("freeze_v3_1_match") is True and a32.get("freeze_v3_1_files") == 8,
              "v3.2 FREEZE_v3_1 match 8/8",
              f"v3.2 freeze mismatch: {a32.get('freeze_v3_1_match')} ({a32.get('freeze_v3_1_files')})")
        v32 = a32["verdicts"]
        check(
            v32["PR6"]["verdict"] == "supported" and v32["PR7"]["verdict"] == "falsified" and v32["PR8"]["verdict"] == "falsified",
            "v3.2 verdicts verified transparent (PR6=supported, PR7=falsified, PR8=falsified)",
            f"Unexpected v3.2 verdicts: {v32}",
        )
        r6 = a32["R6_multiparent_dag_fuzzing"]
        r7 = a32["R7_two_track_fair_benchmark"]
        r8 = a32["R8_exact_vs_empirical_recall_audit"]
        check(r6["total_dag_trials"] == 5000 and r6["total_mismatches"] == 0,
              "v3.2 R6: 0/5000 multi-parent DAG mismatches",
              f"R6 mismatch: {r6['total_mismatches']}/{r6['total_dag_trials']}")
        check(r7["total_queries"] == 1500 and r7["total_leaks"] == 0,
              "v3.2 R7: 0/1500 leaks across Two-Track benchmark",
              f"R7 leaks={r7['total_leaks']}, q={r7['total_queries']}")
        check(r8["by_selectivity"]["0.0001"]["exact_guarantee_coverage_m64_pct"] == 100.0,
              "v3.2 R8: 100.0% M=64 mathematical guarantee coverage at S=0.01%",
              "Unexpected R8 M=64 guarantee coverage")

        nov_txt = nov_path.read_text(encoding="utf-8")
        check("kim2026racorn" in cited and "li2026ema" in cited,
              "RACORN (kim2026racorn) and EMA (li2026ema) cited in prism_ann.tex",
              "Missing RACORN/EMA citation in prism_ann.tex")
        r7_s01 = r7["by_selectivity"]["0.0001"]["systems"]
        r7_10 = r7["by_selectivity"]["0.01"]["systems"]
        for tok in (
            f"{r6['mean_secondary_edges_per_dag']:,.1f}",
            f"{r7_s01['v3-geom-M8']['recall_pct']:.1f}%",
            f"{r7_s01['v3-full-guard-f32']['track1_cpp_med_ms']:.4f}",
            f"{r7_s01['v3-full-guard-sq8']['track1_cpp_med_ms']:.4f}",
            f"{r7_10['v3-full-guard-sq8']['track1_cpp_med_ms']:.4f}",
            f"{r8['by_selectivity']['0.01']['exact_f32_med_ms']:.4f}",
        ):
            check(tok in nov_txt, f"RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md contains {tok}", f"RESEARCH_AUDIT missing {tok}")

        r7_by_s = r7["by_selectivity"]
        r8_by_s = r8["by_selectivity"]
        v32_tex_checks = [
            ("Theorem 1 label", r"\label{thm:ubp_bound}"),
            ("Theorem 2 multi-parent DAG label", r"\label{thm:ubp_dag_exactness}"),
            ("R6 0/5,000 multi-parent DAG mismatches", f"{r6['total_mismatches']}/{r6['total_dag_trials']:,}".replace(",", "{,}")),
            ("R6 mean secondary edges/DAG", f"{r6['mean_secondary_edges_per_dag']:,.1f}".replace(",", "{,}")),
            ("R7 S=0.01% v3-geom-M8 R@10", f"{r7_by_s['0.0001']['systems']['v3-geom-M8']['recall_pct']:.1f}\\%"),
            ("R7 S=0.1% v3-geom-M8 R@10", f"{r7_by_s['0.001']['systems']['v3-geom-M8']['recall_pct']:.1f}\\%"),
            ("R7 S=0.5% v3-geom-M8 R@10", f"{r7_by_s['0.005']['systems']['v3-geom-M8']['recall_pct']:.1f}\\%"),
            ("R7 S=1.0% v3-geom-M8 R@10", f"{r7_by_s['0.01']['systems']['v3-geom-M8']['recall_pct']:.1f}\\%"),
            ("R7 S=5.0% v3-geom-M8 R@10", f"{r7_by_s['0.05']['systems']['v3-geom-M8']['recall_pct']:.1f}\\%"),
            ("R7 S=0.01% PG E2E speedup vs FAISS", f"{r7_by_s['0.0001']['systems']['v3-full-guard-f32']['speedup_e2e_pg_vs_faiss']:.2f}\\times"),
            ("R7 S=0.01% mirror E2E speedup vs FAISS", f"{r7_by_s['0.0001']['systems']['v3-full-guard-f32']['speedup_e2e_mirror_vs_faiss']:.2f}\\times"),
            ("R8 S=0.01% exact FP32 Mode-3 ms", f"{r8_by_s['0.0001']['exact_f32_med_ms']:.4f}"),
            ("R8 S=0.1% exact FP32 Mode-3 ms", f"{r8_by_s['0.001']['exact_f32_med_ms']:.4f}"),
            ("R8 S=1.0% exact FP32 Mode-3 ms", f"{r8_by_s['0.01']['exact_f32_med_ms']:.4f}"),
        ]
        for label, tex_tok in v32_tex_checks:
            check(tex_tok in tex, f"paper/prism_ann.tex contains v3.2 {label} ({tex_tok})",
                  f"paper/prism_ann.tex missing v3.2 {label}: {tex_tok}")

    print("\n[9/9] Checking v3.3 Dynamic DAGs, Direct E2E Timing, Opaque ZedToken Concurrency, & Cross-Doc Parity...")
    from bench.recompute_v3_3 import (
        recompute_v3_3_summary as _recompute_v3_3,
        freeze_v3_3_status as _freeze_v3_3,
    )

    f33 = _freeze_v3_3()
    check(
        f33.get("match") is True and f33.get("n_files") == 9,
        f"FREEZE_v3_3.md {f33.get('n_files')}/9 SHA-256 intact (incl. dynamic_dag_ubp.py)",
        f"FREEZE_v3_3 mismatch: {f33}",
    )

    audit33_path = _Path("results/v3/reviewer_audit_v3_3.json")
    raw_v33_path = _Path("results/v3_3_audit/raw/v3_3_reviewer_audit.jsonl")
    check(
        audit33_path.exists() and raw_v33_path.exists(),
        "v3.3 reviewer audit JSON and raw JSONL exist",
        "Missing v3.3 reviewer audit JSON or JSONL",
    )
    if audit33_path.exists() and raw_v33_path.exists():
        audit33_txt = audit33_path.read_text(encoding="utf-8")
        a33 = _json.loads(audit33_txt)
        recomp_v33 = _recompute_v3_3(str(raw_v33_path))
        check(
            _dumps_summary(recomp_v33) == audit33_txt,
            "results/v3/reviewer_audit_v3_3.json matches deterministic recompute_v3_3.py bit-for-bit",
            "reviewer_audit_v3_3.json differs from recompute_v3_3.py",
        )
        check(a33.get("raw_records_total") == 8524, "v3.3 raw JSONL total == 8524", f"Expected 8524, got {a33.get('raw_records_total')}")
        check(a33.get("git_dirty") is False, "v3.3 audit ran on clean git tree (git_dirty == False)", f"v3.3 git_dirty={a33.get('git_dirty')}")
        check(a33.get("freeze_v3_3_match") is True and a33.get("freeze_v3_3_files") == 9,
              "v3.3 FREEZE_v3_3 match 9/9", f"v3.3 freeze mismatch: {a33.get('freeze_v3_3_match')}")

        v33 = a33["verdicts"]
        check(
            v33["PR9a"]["verdict"] == "supported"
            and v33["PR9b"]["verdict"] == "supported"
            and v33["PR10"]["verdict"] == "falsified"
            and v33["PR11"]["verdict"] == "supported",
            "v3.3 verdicts verified transparent (PR9a=supported, PR9b=supported, PR10=falsified, PR11=supported)",
            f"Unexpected v3.3 verdicts: {v33}",
        )

        r9a = a33["R9a_independent_dag_dynamic_mutations"]
        r9b = a33["R9b_live_spicedb_mutation_matrix"]
        r10 = a33["R10_direct_e2e_and_ef_sweep"]
        r11 = a33["R11_live_spicedb_zedtoken_concurrency"]
        check(
            r9a["independent_dags"] == 1000
            and r9a["total_mutation_checkpoints"] == 5000
            and r9a["false_positives"] == 0
            and r9a["false_negatives"] == 0
            and r9a["search_hit_leaks"] == 0,
            "v3.3 R9a: 0 FP / 0 FN / 0 leaks across 1,000 independent DAGs & 5,000 dynamic mutations",
            f"R9a failure: {r9a}",
        )
        check(
            r9b["scenarios_total"] == 13
            and r9b.get("fail_closed_refusals_verified", 0) >= 1
            and r9b["mask_mismatches"] == 0
            and r9b["search_mismatches"] == 0
            and r9b["check_permission_mismatches"] == 0,
            "v3.3 R9b: 13/13 live SpiceDB dynamic mutation & fail-closed expiration scenarios matched",
            f"R9b failure: {r9b}",
        )
        check(
            r11["concurrent_reads_total"] == 1760
            and r11["oracle_mismatches"] == 0
            and r11["post_revocation_leaks"] == 0
            and r11["snapshot_stale_reads_after_post_pin"] == 0,
            "v3.3 R11: 0/1,760 8-thread live SpiceDB opaque-ZedToken leaks",
            f"R11 failure: {r11}",
        )

        report_txt = _Path("REVIEWER_AUDIT_REPORT.md").read_text(encoding="utf-8")
        nov_txt = _Path("docs/RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md").read_text(encoding="utf-8")
        survey_txt = _Path("literature/survey.md").read_text(encoding="utf-8")
        for cite_key, arxiv_id in (("amanbayev2026gls", "2602.11443"), ("veda2026", "2605.01342")):
            check(
                cite_key in cited and arxiv_id in tex and cite_key in survey_txt and arxiv_id in survey_txt,
                f"Citation parity verified for {cite_key} (arXiv:{arxiv_id}) in prism_ann.tex and survey.md",
                f"Missing {cite_key} / arXiv:{arxiv_id} parity",
            )

        r10_s0001_sq8 = r10["direct_e2e_by_S"]["0.0001"]["systems"]["v3-full-guard-sq8"]
        r10_s05_sq8 = r10["direct_e2e_by_S"]["0.05"]["systems"]["v3-full-guard-sq8"]
        r10_s0001_f32 = r10["direct_e2e_by_S"]["0.0001"]["systems"]["v3-full-guard-f32"]
        r10_s01_sq8 = r10["direct_e2e_by_S"]["0.01"]["systems"]["v3-full-guard-sq8"]
        v33_checks = [
            ("v3.3 total records", "8,524", "8{,}524"),
            ("R9a 1,000 DAGs", "1,000", "1{,}000"),
            ("R9a 5,000 mutations", "5,000", "5{,}000"),
            ("R9b 13/13 scenarios", "13 / 13", "13/13"),
            ("R7 Track 2 composed estimate disclosure", "composed request-latency estimate", "composed request-latency estimate"),
            ("R10 live-RPC S=0.01% f32 speedup", f"{r10_s0001_f32['speedup_live_rpc_vs_faiss']:.2f}", f"{r10_s0001_f32['speedup_live_rpc_vs_faiss']:.2f}"),
            ("R10 live-RPC S=5.0% sq8 speedup", f"{r10_s05_sq8['speedup_live_rpc_vs_faiss']:.2f}", f"{r10_s05_sq8['speedup_live_rpc_vs_faiss']:.2f}"),
            ("R10 mirror S=0.01% sq8 speedup", f"{r10_s0001_sq8['speedup_mirror_vs_faiss']:.2f}", f"{r10_s0001_sq8['speedup_mirror_vs_faiss']:.2f}"),
            ("R10 mirror S=1.0% sq8 speedup", f"{r10_s01_sq8['speedup_mirror_vs_faiss']:.2f}", f"{r10_s01_sq8['speedup_mirror_vs_faiss']:.2f}"),
            ("R10 mirror S=5.0% sq8 speedup", f"{r10_s05_sq8['speedup_mirror_vs_faiss']:.2f}", f"{r10_s05_sq8['speedup_mirror_vs_faiss']:.2f}"),
            ("R11 total reads", "1,760", "1{,}760"),
            ("R11 SpiceDB med rpc", f"{r11['spicedb_median_rpc_ms']:.3f}", f"{r11['spicedb_median_rpc_ms']:.3f}"),
            ("R11 index med search", f"{r11['index_median_search_ms']:.3f}", f"{r11['index_median_search_ms']:.3f}"),
        ]
        for label, md_tok, tex_tok in v33_checks:
            check(md_tok in report_txt, f"REVIEWER_AUDIT_REPORT.md contains v3.3 {label} ({md_tok})",
                  f"REVIEWER_AUDIT_REPORT.md missing v3.3 {label}: {md_tok}")
            check(md_tok in nov_txt, f"RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md contains v3.3 {label} ({md_tok})",
                  f"RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md missing v3.3 {label}: {md_tok}")
            check(tex_tok in tex, f"paper/prism_ann.tex contains v3.3 {label} ({tex_tok})",
                  f"paper/prism_ann.tex missing v3.3 {label}: {tex_tok}")

        check(
            "github.com/naver/racorn" in tex and "github.com/naver/racorn" in nov_txt,
            "Upstream naver/racorn repository inspection cited in prism_ann.tex and RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md",
            "Missing github.com/naver/racorn citation in prism_ann.tex or RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md",
        )

        stale_patterns = ("23.62", "36,881", "36{,}881", "0/18,412", "0 / 18,412", "98.17%", "8,521", "8{,}521", "207,685", "207,688", "207{,}688")
        cross_docs = [
            ".planning/STATE.md",
            "findings.md",
            "research-state.yaml",
            "README.md",
            "REVIEWER_AUDIT_REPORT.md",
            "docs/RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md",
            "docs/adr/0006-external-reviewer-audit-multiparent-dag-and-two-track-fairness.md",
            "paper/prism_ann.tex",
        ]
        for dp in cross_docs:
            dtxt = _Path(dp).read_text(encoding="utf-8")
            for bad in stale_patterns:
                check(bad not in dtxt, f"Zero stale drifted token '{bad}' in {dp}", f"Stale token '{bad}' found in {dp}!")

    print("\n[10/10] Checking v3.4 Atomic Snapshot Race Closure, Unsynced Live SpiceDB Mirror (R12), & Prototype Scope...")
    from bench.recompute_v3_4 import (
        recompute_v3_4_summary as _recompute_v3_4,
        freeze_v3_4_status as _freeze_v3_4,
    )

    f34 = _freeze_v3_4()
    check(
        f34.get("match") is True and f34.get("n_files") == 10,
        f"FREEZE_v3_4.md {f34.get('n_files')}/10 SHA-256 intact (incl. consistent_snapshot_index.py)",
        f"FREEZE_v3_4 mismatch: {f34}",
    )

    audit34_path = _Path("results/v3/reviewer_audit_v3_4.json")
    raw_v34_path = _Path("results/v3_4_audit/raw/v3_4_reviewer_audit.jsonl")
    check(
        audit34_path.exists() and raw_v34_path.exists(),
        "v3.4 reviewer audit JSON and raw JSONL exist",
        "Missing v3.4 reviewer audit JSON or JSONL",
    )
    if audit34_path.exists() and raw_v34_path.exists():
        audit34_txt = audit34_path.read_text(encoding="utf-8")
        a34 = _json.loads(audit34_txt)
        recomp_v34 = _recompute_v3_4(str(raw_v34_path))
        check(
            _dumps_summary(recomp_v34) == audit34_txt,
            "results/v3/reviewer_audit_v3_4.json matches deterministic recompute_v3_4.py bit-for-bit",
            "reviewer_audit_v3_4.json differs from recompute_v3_4.py",
        )
        check(a34.get("raw_records_total") == 1615, "v3.4 raw JSONL total == 1615", f"Expected 1615, got {a34.get('raw_records_total')}")
        check(a34.get("git_dirty") is False, "v3.4 audit ran on clean git tree (git_dirty == False)", f"v3.4 git_dirty={a34.get('git_dirty')}")
        check(a34.get("freeze_v3_4_match") is True and a34.get("freeze_v3_4_files") == 10,
              "v3.4 FREEZE_v3_4 match 10/10", f"v3.4 freeze mismatch: {a34.get('freeze_v3_4_match')}")

        v34 = a34["verdicts"]
        check(
            v34["PR12a"]["verdict"] == "supported"
            and v34["PR12b"]["verdict"] == "supported"
            and v34["PR12c"]["verdict"] == "supported",
            "v3.4 verdicts verified (PR12a=supported, PR12b=supported, PR12c=supported)",
            f"Unexpected v3.4 verdicts: {v34}",
        )

        r12a = a34["R12a_snapshot_race_injection"]
        r12b = a34["R12b_live_spicedb_unsynced_mirror"]
        r12c = a34["R12c_multithreaded_atomic_search_stress"]
        check(
            r12a["v3_3_control_torn_snapshots"] == 100
            and r12a["v3_4_trials_total"] == 200
            and r12a["v3_4_torn_snapshots"] == 0
            and r12a["v3_4_ordering_regressions"] == 0
            and r12a["v3_4_search_leaks"] == 0,
            "v3.4 R12a: reproduced 100/100 torn snapshots on frozen v3.3 control vs 0/200 on v3.4 atomic fix",
            f"R12a failure: {r12a}",
        )
        check(
            r12b["scenarios_total"] == 13
            and r12b["mask_mismatches"] == 0
            and r12b["search_mismatches"] == 0
            and r12b["check_permission_mismatches"] == 0
            and r12b["fail_closed_refusals_verified"] == 5
            and r12b["spicedb_fallbacks_verified"] == 4,
            "v3.4 R12b: 13/13 live SpiceDB unsynced-mirror checks (5 fail_closed, 4 live SpiceDB fallbacks, 0 mismatches)",
            f"R12b failure: {r12b}",
        )
        check(
            r12c["concurrent_reads_total"] == 1200
            and r12c["published_snapshots_verified"] == 101
            and r12c["torn_snapshots"] == 0
            and r12c["ordering_regressions"] == 0
            and r12c["oracle_mismatches"] == 0
            and r12c["search_leaks"] == 0,
            "v3.4 R12c: 0/1,200 multi-threaded public search() leaks across 101 audited atomic snapshots",
            f"R12c failure: {r12c}",
        )

        report_txt = _Path("REVIEWER_AUDIT_REPORT.md").read_text(encoding="utf-8")
        nov_txt = _Path("docs/RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md").read_text(encoding="utf-8")
        readme_txt = _Path("README.md").read_text(encoding="utf-8")
        cs_src = _Path("src/modules/prism_ann_v3/consistent_snapshot_index.py").read_text(encoding="utf-8")
        v34_checks = [
            ("v3.4 total records", "1,615", "1{,}615"),
            ("R12a v3.3 torn control", "100", "100/100"),
            ("R12a v3.4 zero torn", "200", "0/200"),
            ("R12c concurrent reads", "1,200", "1{,}200"),
            ("R12c audited snapshots", "101", "101"),
            ("research prototype scope", "research prototype", "research prototype"),
        ]
        for label, md_tok, tex_tok in v34_checks:
            check(md_tok in report_txt, f"REVIEWER_AUDIT_REPORT.md contains v3.4 {label} ({md_tok})",
                  f"REVIEWER_AUDIT_REPORT.md missing v3.4 {label}: {md_tok}")
            check(md_tok in nov_txt, f"RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md contains v3.4 {label} ({md_tok})",
                  f"RESEARCH_AUDIT_AND_NOVELTY_MATRIX.md missing v3.4 {label}: {md_tok}")
            check(tex_tok in tex, f"paper/prism_ann.tex contains v3.4 {label} ({tex_tok})",
                  f"paper/prism_ann.tex missing v3.4 {label}: {tex_tok}")

        for label, txt_body in (
            ("paper/prism_ann.tex", tex),
            ("README.md", readme_txt),
            ("REVIEWER_AUDIT_REPORT.md", report_txt),
            ("src/modules/prism_ann_v3/consistent_snapshot_index.py", cs_src),
        ):
            check(
                "production-safe" not in txt_body.lower(),
                f"Zero overstated 'production-safe' claim in {label}",
                f"Overstated 'production-safe' found in {label}",
            )

    print(f"\nSUMMARY: {passed} checks passed, {len(errors)} errors.")
    return len(errors) == 0


if __name__ == "__main__":
    sys.exit(0 if verify() else 1)
