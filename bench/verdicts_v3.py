"""
Pre-registered decision rules for PROTOCOL_v3 predictions P1a..P5 (ADR-0005)
============================================================================
Inputs are strictly the deterministic aggregates produced by `bench.recompute_v3`
from `results/v3/raw/*.jsonl`.  Every verdict is `"supported"`, `"falsified"`,
or `"untestable"` with all driving quantities exposed transparently.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

S_ALL = ("S=0.001", "S=0.005", "S=0.01", "S=0.05")
S_LOW3 = ("S=0.001", "S=0.005", "S=0.01")
S_MID2 = ("S=0.005", "S=0.01")


def _m(block: Optional[Dict[str, Any]], key: str) -> Optional[float]:
    if not block or key not in block or block[key] is None:
        return None
    return block[key].get("mean")


def _pooled_med(block: Optional[Dict[str, Any]]) -> Optional[float]:
    if not block:
        return None
    return block.get("latency_ms_median_pooled")


def _paired_diff(a: Dict[str, Any], b: Dict[str, Any], key: str) -> Dict[str, Any]:
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


def eval_h1(h1_mem: Optional[Dict[str, Any]], h1_pg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not h1_mem:
        return {p: _untestable("H1_memory not run") for p in ("P1a", "P1b", "P1c")}
    out: Dict[str, Any] = {}

    mism_mem = h1_mem["mismatch_docs_total"] + h1_mem["mismatch_chunks_total"]
    mism_pg = (
        (h1_pg["mismatch_docs_total"] + h1_pg["mismatch_chunks_total"]) if h1_pg else None
    )
    ok_a = (mism_mem == 0) and (mism_pg == 0 if mism_pg is not None else True)
    out["P1a"] = {
        "verdict": "supported" if (h1_mem["n_principals"] >= 200 and ok_a) else "falsified",
        "memory_n_principals": h1_mem["n_principals"],
        "memory_mismatches": mism_mem,
        "postgres_n_principals": h1_pg["n_principals"] if h1_pg else 0,
        "postgres_mismatches": mism_pg,
    }

    frac_mem = h1_mem["within_bound_fraction"]
    frac_pg = h1_pg["within_bound_fraction"] if h1_pg else 1.0
    out["P1b"] = {
        "verdict": "supported" if (frac_mem == 1.0 and frac_pg == 1.0) else "falsified",
        "memory_within_bound_fraction": frac_mem,
        "postgres_within_bound_fraction": frac_pg if h1_pg else None,
        "memory_tokens_pos_max": h1_mem["tokens_pos_max"],
    }

    def _ratio_block(h1: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not h1:
            return None
        t = h1["timing"].get("auth_docs_ge_1000", {})
        ubp = t.get("UBP+bitmap")
        sp = t.get("SpiceDB-LookupResources+leaf-bitmap")
        strict = t.get("SpiceDB-ReadRelationships+UBP+bitmap")
        if not ubp or not sp or not ubp["n"] or not sp["n"]:
            return None
        r_local = sp["latency_ms_median_pooled"] / ubp["latency_ms_median_pooled"]
        r_strict = (
            sp["latency_ms_median_pooled"] / strict["latency_ms_median_pooled"]
            if (strict and strict["n"])
            else None
        )
        return {
            "n": ubp["n"],
            "ubp_median_ms": ubp["latency_ms_median_pooled"],
            "strict_median_ms": strict["latency_ms_median_pooled"] if strict else None,
            "spicedb_median_ms": sp["latency_ms_median_pooled"],
            "ratio_spicedb_over_ubp": r_local,
            "strict_ratio": r_strict,
        }

    b_mem = _ratio_block(h1_mem)
    b_pg = _ratio_block(h1_pg)
    if not b_mem or not b_pg:
        out["P1c"] = _untestable("Missing broad-principal timing on memory or postgres SpiceDB")
    else:
        ok_c = (b_mem["ratio_spicedb_over_ubp"] >= 10.0) and (b_pg["ratio_spicedb_over_ubp"] >= 10.0)
        out["P1c"] = {
            "verdict": "supported" if ok_c else "falsified",
            "memory": b_mem,
            "postgres": b_pg,
        }
    return out


def eval_h2(
    h2_quora: Optional[Dict[str, Any]],
    h2_nq: Optional[Dict[str, Any]],
    ram_meta: Dict[str, Any],
) -> Dict[str, Any]:
    if not h2_quora:
        return {p: _untestable("H2_quora not run") for p in ("P2a", "P2b", "P2c")}
    out: Dict[str, Any] = {}

    # P2a: Quora v3-geom-M8 >= 75% at S in {0.5%, 1.0%}, beats faiss-hnsw-M16 by >= +40 pts,
    # and beats v2-ring-chord-M4 by >= +20 pts at S = 0.5%.
    bc_q = h2_quora["by_condition"]
    p2a_rows: Dict[str, Any] = {}
    ok_a = True
    for s in S_MID2:
        g = bc_q.get(s, {})
        if not all(k in g for k in ("v3-geom-M8", "faiss-hnsw-M16", "v2-ring-chord-M4")):
            ok_a = None
            break
        r_v3 = _m(g["v3-geom-M8"], "recall_mean")
        r_f = _m(g["faiss-hnsw-M16"], "recall_mean")
        r_rc = _m(g["v2-ring-chord-M4"], "recall_mean")
        d_f = r_v3 - r_f
        d_rc = r_v3 - r_rc
        p2a_rows[s] = {
            "v3_recall": r_v3,
            "faiss_recall": r_f,
            "ring_chord_recall": r_rc,
            "diff_vs_faiss": d_f,
            "paired_diff_vs_faiss": _paired_diff(g["v3-geom-M8"], g["faiss-hnsw-M16"], "recall_mean"),
            "diff_vs_ring_chord": d_rc,
            "paired_diff_vs_ring_chord": _paired_diff(g["v3-geom-M8"], g["v2-ring-chord-M4"], "recall_mean"),
        }
        cond = (r_v3 >= 0.75) and (d_f >= 0.40)
        if s == "S=0.005":
            cond = cond and (d_rc >= 0.20)
        ok_a = ok_a and cond
    out["P2a"] = (
        _untestable("Missing systems for P2a")
        if ok_a is None
        else {"verdict": "supported" if ok_a else "falsified", "by_S": p2a_rows}
    )

    # P2b: v3-geom-M8 beats acorn-1 across all S on both corpora, uses <= 0.5x extra RAM of acorn-gamma,
    # and stays within -5 pts Recall@10 of acorn-gamma across all S on both corpora.
    corpora = [("quora", h2_quora)]
    if h2_nq:
        corpora.append(("nq", h2_nq))
    p2b_detail: Dict[str, Any] = {}
    ok_b: Optional[bool] = True
    for cname, h2 in corpora:
        bc = h2["by_condition"]
        p2b_detail[cname] = {}
        for s in S_ALL:
            g = bc.get(s, {})
            if "v3-geom-M8" not in g or "acorn-1" not in g:
                ok_b = None
                break
            r_v3 = _m(g["v3-geom-M8"], "recall_mean")
            r_a1 = _m(g["acorn-1"], "recall_mean")
            r_ag = _m(g["acorn-gamma"], "recall_mean") if "acorn-gamma" in g else None
            beats_a1 = r_v3 > r_a1
            within_ag = (r_v3 >= r_ag - 0.05) if r_ag is not None else True
            p2b_detail[cname][s] = {
                "v3_recall": r_v3,
                "acorn1_recall": r_a1,
                "acorn_gamma_recall": r_ag,
                "beats_acorn1": beats_a1,
                "within_5pt_acorn_gamma": within_ag,
            }
            if ok_b is not None:
                ok_b = ok_b and beats_a1 and within_ag
    # Extra index RAM comparison: v3-geom-M8 (32 B/node) vs acorn-gamma (M_beta + 1.5*M - 2*M = 56 edges * 4 B = 224 B/node + upper)
    v3_extra_b = ram_meta.get("v3_geom_m8_extra_bytes_per_node", 32.0)
    ag_extra_b = ram_meta.get("acorn_gamma_extra_bytes_per_node", 224.0)
    ram_ratio = v3_extra_b / ag_extra_b if ag_extra_b > 0 else None
    ram_ok = ram_ratio is not None and ram_ratio <= 0.5
    if ok_b is not None:
        ok_b = ok_b and ram_ok
    out["P2b"] = (
        _untestable("Missing acorn-1 / v3-geom-M8")
        if ok_b is None
        else {
            "verdict": "supported" if ok_b else "falsified",
            "extra_ram_ratio_v3_over_acorn_gamma": ram_ratio,
            "v3_extra_bytes_per_node": v3_extra_b,
            "acorn_gamma_extra_bytes_per_node": ag_extra_b,
            "by_corpus": p2b_detail,
        }
    )

    # P2c: v3-full-guard-sq8 >= 99.0% at S <= 1% on both corpora, >= 2.0x faster than exact-brute-force
    # at S in {0.5%, 1.0%}, and >= 25x faster than hnswlib-M16 & pgvector-hnsw-iter at S=0.1%.
    p2c_detail: Dict[str, Any] = {}
    ok_c: Optional[bool] = True
    for cname, h2 in corpora:
        bc = h2["by_condition"]
        p2c_detail[cname] = {}
        for s in S_LOW3:
            g = bc.get(s, {})
            if "v3-full-guard-sq8" not in g or "exact-brute-force" not in g:
                ok_c = None
                break
            r_full = _m(g["v3-full-guard-sq8"], "recall_mean")
            lat_full = _pooled_med(g["v3-full-guard-sq8"])
            lat_bf = _pooled_med(g["exact-brute-force"])
            ratio_bf = (lat_bf / lat_full) if (lat_bf and lat_full) else None
            entry: Dict[str, Any] = {
                "recall": r_full,
                "v3_full_med_ms": lat_full,
                "brute_force_med_ms": lat_bf,
                "speedup_vs_bf": ratio_bf,
            }
            cond_s = (r_full >= 0.99)
            if s in S_MID2:
                cond_s = cond_s and (ratio_bf is not None and ratio_bf >= 2.0)
            if s == "S=0.001":
                if "hnswlib-M16" in g:
                    lat_h = _pooled_med(g["hnswlib-M16"])
                    r_h = lat_h / lat_full if (lat_h and lat_full) else None
                    entry["hnswlib_med_ms"] = lat_h
                    entry["speedup_vs_hnswlib"] = r_h
                    cond_s = cond_s and (r_h is not None and r_h >= 25.0)
                if "pgvector-hnsw-iter" in g:
                    lat_pg = _pooled_med(g["pgvector-hnsw-iter"])
                    r_pg = lat_pg / lat_full if (lat_pg and lat_full) else None
                    entry["pgvector_med_ms"] = lat_pg
                    entry["speedup_vs_pgvector"] = r_pg
                    cond_s = cond_s and (r_pg is not None and r_pg >= 25.0)
            entry["holds"] = cond_s
            p2c_detail[cname][s] = entry
            if ok_c is not None:
                ok_c = ok_c and cond_s
    out["P2c"] = (
        _untestable("Missing v3-full-guard-sq8 or exact-brute-force")
        if ok_c is None
        else {"verdict": "supported" if ok_c else "falsified", "by_corpus": p2c_detail}
    )
    return out


def eval_h3(h3_quora: Optional[Dict[str, Any]], h3_nq: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not h3_quora:
        return {p: _untestable("H3_quora not run") for p in ("P3a", "P3b")}
    out: Dict[str, Any] = {}
    corpora = [("quora", h3_quora)]
    if h3_nq:
        corpora.append(("nq", h3_nq))

    # P3a: r <= 0.5: v3-geom-M8 beats faiss-hnsw-M16 by >= +40 pts, AND v3-full-guard-sq8 >= 95% at <= 1.5ms med
    p3a_by: Dict[str, Any] = {}
    ok_a: Optional[bool] = True
    for cname, h3 in corpora:
        g = h3["by_condition"].get("r_le_0.5", {})
        if not all(k in g for k in ("v3-geom-M8", "faiss-hnsw-M16", "v3-full-guard-sq8")):
            ok_a = None
            break
        r_v3 = _m(g["v3-geom-M8"], "recall_mean")
        r_f = _m(g["faiss-hnsw-M16"], "recall_mean")
        r_full = _m(g["v3-full-guard-sq8"], "recall_mean")
        lat_full = _pooled_med(g["v3-full-guard-sq8"])
        cond = ((r_v3 - r_f) >= 0.40) and (r_full >= 0.95) and (lat_full is not None and lat_full <= 1.5)
        p3a_by[cname] = {
            "v3_graph_recall": r_v3,
            "faiss_recall": r_f,
            "diff_vs_faiss": r_v3 - r_f,
            "paired_diff_vs_faiss": _paired_diff(g["v3-geom-M8"], g["faiss-hnsw-M16"], "recall_mean"),
            "v3_full_recall": r_full,
            "v3_full_med_ms": lat_full,
            "holds": cond,
        }
        if ok_a is not None:
            ok_a = ok_a and cond
    out["P3a"] = (
        _untestable("Missing H3 r<=0.5 systems")
        if ok_a is None
        else {"verdict": "supported" if ok_a else "falsified", "by_corpus": p3a_by}
    )

    # P3b: r >= 2.0: v3-geom-M8 (tau_high=0.55) uses <= 0.65x dist evals of v3-static-2hop & within -1.0 pt Recall@10
    p3b_by: Dict[str, Any] = {}
    ok_b: Optional[bool] = True
    for cname, h3 in corpora:
        g = h3["by_condition"].get("r_ge_2", {})
        if not all(k in g for k in ("v3-geom-M8", "v3-static-2hop")):
            ok_b = None
            break
        pd_ = _m(g["v3-geom-M8"], "dist_mean")
        sd_ = _m(g["v3-static-2hop"], "dist_mean")
        pr = _m(g["v3-geom-M8"], "recall_mean")
        sr = _m(g["v3-static-2hop"], "recall_mean")
        ratio = pd_ / sd_ if sd_ else None
        cond = (ratio is not None and ratio <= 0.65) and (pr >= sr - 0.01)
        p3b_by[cname] = {
            "v3_dist": pd_,
            "static_dist": sd_,
            "dist_ratio": ratio,
            "eval_savings_x": (sd_ / pd_) if pd_ else None,
            "v3_recall": pr,
            "static_recall": sr,
            "recall_diff": pr - sr,
            "holds": cond,
        }
        if ok_b is not None:
            ok_b = ok_b and cond
    out["P3b"] = (
        _untestable("Missing H3 r>=2.0 systems")
        if ok_b is None
        else {"verdict": "supported" if ok_b else "falsified", "by_corpus": p3b_by}
    )
    return out


def eval_h4(h4: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not h4:
        return {p: _untestable("H4 not run") for p in ("P4a", "P4b")}
    s = h4["systems"]
    out: Dict[str, Any] = {}
    pa = s.get("P4a-path(SpiceDB-Postgres-Delete+mirror+UBP+bitmap)")
    pg = s.get("pgvector-UPDATE-acl")
    if not pa:
        out["P4a"] = _untestable("P4a Postgres SpiceDB path not measured")
    else:
        out["P4a"] = {
            "verdict": "supported" if pa["vector_writes_max"] == 0 else "falsified",
            "vector_writes_max": pa["vector_writes_max"],
            "latency_ms_median": pa["latency_ms_median"],
        }
    if not pa or not pg:
        out["P4b"] = _untestable("Missing P4a or pgvector UPDATE path")
    else:
        ratio = pg["latency_ms_median"] / pa["latency_ms_median"]
        out["P4b"] = {
            "verdict": "supported" if ratio >= 100.0 else "falsified",
            "ratio": ratio,
            "pgvector_median_ms": pg["latency_ms_median"],
            "p4a_median_ms": pa["latency_ms_median"],
            "rows_updated_median": pg["rows_affected_median"],
        }
    return out


def eval_h5(h5: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not h5:
        return {"P5": _untestable("H5_quora not run")}
    bc = h5["by_condition"]
    rows: Dict[str, Any] = {}
    ok: Optional[bool] = True
    for s in S_LOW3:
        g = bc.get(s, {})
        req = ("faiss-hnsw-M16", "faiss-M16+4portals", "hhnsw-v2-geom-M8-noportal", "v3-geom-M8")
        if not all(k in g for k in req):
            ok = None
            break
        r_f = _m(g["faiss-hnsw-M16"], "recall_mean")
        r_fp = _m(g["faiss-M16+4portals"], "recall_mean")
        r_np = _m(g["hhnsw-v2-geom-M8-noportal"], "recall_mean")
        r_full = _m(g["v3-geom-M8"], "recall_mean")
        gain_full = r_full - r_f
        gain_np = r_np - r_f
        retained = (gain_np / gain_full) if gain_full > 1e-9 else None
        holds = retained is not None and retained >= 0.85
        rows[s] = {
            "faiss_recall": r_f,
            "faiss_4portals_recall": r_fp,
            "portal_only_lift": r_fp - r_f,
            "noportal_bridges_recall": r_np,
            "full_bridges_4portals_recall": r_full,
            "retained_gain_fraction": retained,
            "holds": holds,
        }
        if ok is not None:
            ok = ok and holds
    return {
        "P5": (
            _untestable("Missing H5 systems")
            if ok is None
            else {"verdict": "supported" if ok else "falsified", "by_S": rows}
        )
    }


def evaluate_v3(summary: Dict[str, Any]) -> Dict[str, Any]:
    h = summary.get("hypotheses", {})
    ram_meta = summary.get("ram_meta", {})
    out: Dict[str, Any] = {}
    out.update(eval_h1(h.get("H1_memory"), h.get("H1_postgres")))
    out.update(eval_h2(h.get("H2_quora"), h.get("H2_nq"), ram_meta))
    out.update(eval_h3(h.get("H3_quora"), h.get("H3_nq")))
    out.update(eval_h4(h.get("H4_postgres")))
    out.update(eval_h5(h.get("H5_quora")))
    return out
