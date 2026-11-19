"""
Pre-registered decision rules for PROTOCOL_v2 predictions (ADR-0004)
====================================================================
Written before any v2 measurement.  Inputs are only the aggregates produced by
bench.recompute from raw records.  Each verdict is one of:
    "supported" | "falsified" | "untestable"
with the measured quantities that drove it.

Interpretation choices fixed here (also listed in results/v2/DEVIATIONS.md):
  * Recall/dist comparisons use the across-seed mean of per-seed means; the 95% CI
    of the per-seed paired difference is reported next to it.
  * P2a/P3a compare Prism graph-only against FAISS HNSW (M=16) + IDSelector at the
    same efSearch=64 (primary).  The shared-graph FAISS M=8 baseline is secondary.
  * P2a/P2c must hold at every S <= 0.5% (S = 0.1% and 0.5%).
  * P2b must hold at every S in the sweep.
  * P1c uses pooled medians over all principals (all seeds) with >= 1,000 authorized
    docs; the stricter variant that also fetches grants from SpiceDB is reported.
  * P4b uses the median over trials of each path.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

PRISM_GRAPH = "prism-graph-only"
PRISM_FULL = "prism-full"
PRISM_STATIC = "prism-static-2hop"
FAISS_PRIMARY = "faiss-hnsw-M16"
FAISS_ACORN1 = "acorn-1"

H1_UBP = "UBP+bitmap"
H1_SPICEDB = "SpiceDB-LookupResources+leaf-bitmap"
H1_UBP_STRICT = "SpiceDB-ReadRelationships+UBP+bitmap"
H4_PRISM = "P4a-path(SpiceDB-Delete+mirror+UBP+bitmap)"
H4_PG = "pgvector-UPDATE-acl"

LOW_S = ("S=0.001", "S=0.005")


def _m(block: Optional[Dict[str, Any]], key: str) -> Optional[float]:
    if not block or key not in block or block[key] is None:
        return None
    return block[key].get("mean")


def _paired_diff(a: Dict[str, Any], b: Dict[str, Any], key: str) -> Dict[str, Any]:
    """Per-seed paired difference a-b with a 95% t-interval (seeds present in both)."""
    from scipy.stats import t as student_t

    seeds = sorted(set(a["per_seed"]) & set(b["per_seed"]))
    diffs = []
    for s in seeds:
        va, vb = a["per_seed"][s].get(key), b["per_seed"][s].get(key)
        if va is not None and vb is not None:
            diffs.append(va - vb)
    if not diffs:
        return {"mean": None, "ci95": None, "n_seeds": 0}
    m = math.fsum(diffs) / len(diffs)
    if len(diffs) > 1:
        sd = math.sqrt(math.fsum((d - m) ** 2 for d in diffs) / (len(diffs) - 1))
        half = float(student_t.ppf(0.975, len(diffs) - 1)) * sd / math.sqrt(len(diffs))
    else:
        half = None
    return {"mean": m, "ci95": half, "n_seeds": len(diffs), "per_seed": diffs}


def _untestable(reason: str) -> Dict[str, Any]:
    return {"verdict": "untestable", "reason": reason}


# ---------------------------------------------------------------------------
def eval_h1(h1: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not h1:
        return {p: _untestable("H1 not run") for p in ("P1a", "P1b", "P1c")}
    out: Dict[str, Any] = {}
    n = h1["n_principals"]
    mism = h1["mismatch_docs_total"] + h1["mismatch_chunks_total"]
    if n < 200:
        out["P1a"] = {"verdict": "untestable", "reason": f"only {n} principals (<200)", "mismatches": mism}
    else:
        out["P1a"] = {"verdict": "supported" if mism == 0 else "falsified", "n_principals": n,
                      "mismatch_docs_total": h1["mismatch_docs_total"],
                      "mismatch_chunks_total": h1["mismatch_chunks_total"],
                      "principals_with_any_mismatch": h1["principals_with_any_mismatch"]}
    frac = h1["within_bound_fraction"]
    out["P1b"] = _untestable("no principals") if frac is None else {
        "verdict": "supported" if frac == 1.0 else "falsified", "within_bound_fraction": frac,
        "tokens_pos_max": h1["tokens_pos_max"]}
    t = h1["timing"].get("auth_docs_ge_1000", {})
    ubp, sp, strict = t.get(H1_UBP), t.get(H1_SPICEDB), t.get(H1_UBP_STRICT)
    if not ubp or not sp or not ubp["n"] or not sp["n"]:
        out["P1c"] = _untestable("no principals with >= 1,000 authorized docs")
    else:
        ratio = sp["latency_ms_median_pooled"] / ubp["latency_ms_median_pooled"]
        strict_ratio = None
        if strict and strict["n"]:
            strict_ratio = sp["latency_ms_median_pooled"] / strict["latency_ms_median_pooled"]
        out["P1c"] = {"verdict": "supported" if ratio >= 10.0 else "falsified",
                      "n_principals": ubp["n"], "ratio_spicedb_over_ubp": ratio,
                      "ubp_median_ms": ubp["latency_ms_median_pooled"],
                      "spicedb_median_ms": sp["latency_ms_median_pooled"],
                      "strict_ratio_including_grant_fetch": strict_ratio,
                      "strict_verdict": (None if strict_ratio is None else
                                         ("supported" if strict_ratio >= 10.0 else "falsified"))}
    return out


def eval_h2(h2: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not h2:
        return {p: _untestable("H2 not run") for p in ("P2a", "P2b", "P2c")}
    bc = h2["by_condition"]
    out: Dict[str, Any] = {}
    # P2a
    rows, ok = {}, True
    for s in LOW_S:
        g = bc.get(s, {})
        if PRISM_GRAPH not in g or FAISS_PRIMARY not in g:
            ok = None
            rows[s] = "missing"
            continue
        d = _paired_diff(g[PRISM_GRAPH], g[FAISS_PRIMARY], "recall_mean")
        diff = _m(g[PRISM_GRAPH], "recall_mean") - _m(g[FAISS_PRIMARY], "recall_mean")
        rows[s] = {"prism_recall": _m(g[PRISM_GRAPH], "recall_mean"),
                   "faiss_recall": _m(g[FAISS_PRIMARY], "recall_mean"),
                   "diff": diff, "paired_diff": d, "threshold": 0.10}
        ok = ok and diff >= 0.10
    out["P2a"] = (_untestable(f"missing systems: {rows}") if ok is None else
                  {"verdict": "supported" if ok else "falsified", "by_S": rows})
    # P2b
    conds = sorted(bc)
    if not any(FAISS_ACORN1 in bc[c] for c in conds):
        out["P2b"] = _untestable("ACORN-1 not available as a measured baseline")
    else:
        rows, ok = {}, True
        for c in conds:
            g = bc[c]
            if FAISS_ACORN1 not in g or PRISM_GRAPH not in g:
                rows[c] = "missing"
                ok = False
                continue
            pr, ar = _m(g[PRISM_GRAPH], "recall_mean"), _m(g[FAISS_ACORN1], "recall_mean")
            pdist, adist = _m(g[PRISM_GRAPH], "dist_mean"), _m(g[FAISS_ACORN1], "dist_mean")
            cond_ok = (pr >= ar - 0.02) and (pdist is not None and adist is not None and pdist <= adist)
            rows[c] = {"prism_recall": pr, "acorn_recall": ar, "prism_dist": pdist, "acorn_dist": adist,
                       "dist_ratio": (pdist / adist) if (pdist and adist) else None, "holds": cond_ok}
            ok = ok and cond_ok
        out["P2b"] = {"verdict": "supported" if ok else "falsified", "by_S": rows}
    # P2c
    rows, ok = {}, True
    for s in LOW_S:
        g = bc.get(s, {})
        if PRISM_FULL not in g:
            ok = None
            break
        r = _m(g[PRISM_FULL], "recall_mean")
        rows[s] = {"prism_full_recall": r, "threshold": 0.99}
        ok = ok and r >= 0.99
    out["P2c"] = (_untestable("prism-full missing") if ok is None else
                  {"verdict": "supported" if ok else "falsified", "by_S": rows})
    return out


def eval_h3(h3: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not h3:
        return {p: _untestable("H3 not run") for p in ("P3a", "P3b")}
    bc = h3["by_condition"]
    out: Dict[str, Any] = {}
    g = bc.get("r_le_0.5", {})
    if PRISM_GRAPH in g and FAISS_PRIMARY in g:
        diff = _m(g[PRISM_GRAPH], "recall_mean") - _m(g[FAISS_PRIMARY], "recall_mean")
        out["P3a"] = {"verdict": "supported" if diff >= 0.10 else "falsified",
                      "prism_recall": _m(g[PRISM_GRAPH], "recall_mean"),
                      "faiss_recall": _m(g[FAISS_PRIMARY], "recall_mean"), "diff": diff,
                      "paired_diff": _paired_diff(g[PRISM_GRAPH], g[FAISS_PRIMARY], "recall_mean"),
                      "n_queries_x_seeds": g[PRISM_GRAPH]["n_total"]}
    else:
        out["P3a"] = _untestable("no queries with measured r <= 0.5")
    g = bc.get("r_ge_2", {})
    if PRISM_GRAPH in g and PRISM_STATIC in g:
        pd_, sd_ = _m(g[PRISM_GRAPH], "dist_mean"), _m(g[PRISM_STATIC], "dist_mean")
        pr, sr = _m(g[PRISM_GRAPH], "recall_mean"), _m(g[PRISM_STATIC], "recall_mean")
        ratio = pd_ / sd_ if sd_ else None
        ok = ratio is not None and ratio <= 0.8 and pr >= sr - 0.01
        out["P3b"] = {"verdict": "supported" if ok else "falsified", "dist_ratio": ratio,
                      "prism_dist": pd_, "static_dist": sd_, "prism_recall": pr, "static_recall": sr,
                      "n_queries_x_seeds": g[PRISM_GRAPH]["n_total"]}
    else:
        out["P3b"] = _untestable("no queries with measured r >= 2")
    return out


def eval_h4(h4: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not h4:
        return {p: _untestable("H4 not run") for p in ("P4a", "P4b")}
    s = h4["systems"]
    out: Dict[str, Any] = {}
    pa = s.get(H4_PRISM)
    if not pa:
        out["P4a"] = _untestable("P4a path not measured")
    else:
        out["P4a"] = {"verdict": "supported" if pa["vector_writes_max"] == 0 else "falsified",
                      "vector_writes_max": pa["vector_writes_max"], "latency_ms_median": pa["latency_ms_median"]}
    pg = s.get(H4_PG)
    if not pa or not pg:
        out["P4b"] = _untestable("pgvector UPDATE path not measured")
    else:
        ratio = pg["latency_ms_median"] / pa["latency_ms_median"]
        out["P4b"] = {"verdict": "supported" if ratio >= 100.0 else "falsified", "ratio": ratio,
                      "pgvector_median_ms": pg["latency_ms_median"], "p4a_median_ms": pa["latency_ms_median"],
                      "rows_updated_median": pg["rows_affected_median"]}
    return out


def evaluate(summary: Dict[str, Any]) -> Dict[str, Any]:
    h = summary.get("hypotheses", {})
    out: Dict[str, Any] = {}
    out.update(eval_h1(h.get("H1")))
    out.update(eval_h2(h.get("H2")))
    out.update(eval_h3(h.get("H3")))
    out.update(eval_h4(h.get("H4")))
    return out
