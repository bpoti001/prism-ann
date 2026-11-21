#!/usr/bin/env python3
"""
Phase 17-03 Exploratory Dev-Split Evaluation (E1 + E2 + E3 + tau_high sweep)
============================================================================
Governing ADRs: ADR-0004, ADR-0005.
Runs STRICTLY on the held-out dev split:
  - Corpus: 100k BEIR Quora passages (indices [0..99,999])
  - Queries: Dev query slice [0..499] ONLY (reserving [500..9,984] for Phase 19!)
Every query emits a raw provenance record to `results/v3_dev/raw/*.jsonl`,
and `results/v3_dev/summary_dev.json` is derived solely from those raw records.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import time
from collections import defaultdict
from typing import Any, Dict, List, Sequence, Tuple

import faiss
import numpy as np

from bench.dataset import build_overlay, load_quora_embeddings
from bench.experiments import H2_SELECTIVITIES, _exact_top_k
from bench.harness import (
    QuerySpec,
    RawWriter,
    RunContext,
    SearchOutput,
    freeze_status,
    git_sha,
    run_condition,
)
from bench.systems import (
    Acorn1System,
    ExactBruteForceSystem,
    FaissHNSWSystem,
    HnswlibSystem,
    _check_no_leak,
)
from src.modules.prism_ann.trimodal_planner import RoaringRunBitmap, ZOrderedCorpus
from src.modules.prism_ann_v3.ckernel_bridge import (
    mode3_scan_ranges_f32,
    mode3_scan_ranges_sq8,
)
from src.modules.prism_ann_v3.geometric_hhnsw import (
    GeometricBridgeConfig,
    GeometricHHNSW,
)
from src.modules.prism_ann_v3.trimodal_v3 import (
    TriModalPlannerV3,
    runs_to_range_arrays,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# UBP token -> Z-order CRoaring range helper (zero np.flatnonzero!)
# ---------------------------------------------------------------------------
def _compile_ranges_from_tokens(
    z_corpus: ZOrderedCorpus, tokens: Sequence[str]
) -> Tuple[np.ndarray, np.ndarray, int]:
    bms = [z_corpus.token_bitmaps[t] for t in tokens if t in z_corpus.token_bitmaps]
    rbm = RoaringRunBitmap.union_all(bms, z_corpus.N)
    return runs_to_range_arrays(rbm)


# ---------------------------------------------------------------------------
# System Adapters for E1 / E2 / E3 (all return original corpus IDs)
# ---------------------------------------------------------------------------
class CppMode3System:
    """Native C++ ARM NEON Mode 3 scan over UBP CRoaring [start, end) ranges."""

    def __init__(self, z_corpus: ZOrderedCorpus, precision: str = "sq8", name: str = "cpp-mode3-sq8"):
        self.name = name
        self.z_corpus = z_corpus
        self.precision = precision

    def search(self, q: QuerySpec, k: int) -> SearchOutput:
        starts, ends, n_cand = _compile_ranges_from_tokens(self.z_corpus, q.extra["ubp_tokens"])
        if n_cand == 0:
            return SearchOutput(ids=[], distance_computations=0)
        qv = np.ascontiguousarray(q.vector, dtype=np.float32)
        if self.precision == "f32":
            z_ids, _, evals = mode3_scan_ranges_f32(self.z_corpus.vectors, qv, starts, ends, k=k)
        else:
            q_sq8 = np.ascontiguousarray(np.clip(np.round(qv * 127.0), -127, 127).astype(np.int8))
            z_ids, _, evals = mode3_scan_ranges_sq8(
                self.z_corpus.sq8_vectors,
                self.z_corpus.vectors,
                q_sq8,
                qv,
                starts,
                ends,
                k=k,
                rerank_k=max(4 * k, 64),
            )
        ids = [int(self.z_corpus.z_to_orig[zi]) for zi in z_ids]
        _check_no_leak(ids, q.mask, self.name)
        return SearchOutput(ids=ids, distance_computations=int(evals), extra={"n_ranges": int(len(starts))})


class HHNSWV3GraphSystem:
    """Native C++ H-HNSW v2 graph-only adapter (supports E1, E2, tau_high sweeps)."""

    def __init__(
        self,
        z_corpus: ZOrderedCorpus,
        hhnsw: GeometricHHNSW,
        name: str,
        ef_search: int = 64,
        tau_high: float = 0.55,
        tau_low: float = 0.02,
        use_express_bridges: bool = True,
        use_portals: bool = True,
        max_portals: int = 4,
        use_gls_adaptive: bool = True,
        faiss_style_1hop: bool = False,
    ):
        self.name = name
        self.z_corpus = z_corpus
        self.hhnsw = hhnsw
        self.ef_search = ef_search
        self.tau_high = tau_high
        self.tau_low = tau_low
        self.use_express_bridges = use_express_bridges
        self.use_portals = use_portals
        self.max_portals = max_portals
        self.use_gls_adaptive = use_gls_adaptive
        self.faiss_style_1hop = faiss_style_1hop

    def search(self, q: QuerySpec, k: int) -> SearchOutput:
        starts, ends, n_cand = _compile_ranges_from_tokens(self.z_corpus, q.extra["ubp_tokens"])
        if n_cand == 0:
            return SearchOutput(ids=[], distance_computations=0)
        res = self.hhnsw.search_ranges(
            query_vec=q.vector,
            starts=starts,
            ends=ends,
            k=k,
            ef_search=self.ef_search,
            tau_high=self.tau_high,
            tau_low=self.tau_low,
            use_express_bridges=self.use_express_bridges,
            use_portals=self.use_portals,
            max_portals=self.max_portals,
            use_gls_adaptive=self.use_gls_adaptive,
            faiss_style_1hop=self.faiss_style_1hop,
            tau_stall=0.0,
        )
        ids = [int(self.z_corpus.z_to_orig[zi]) for zi in res.top_k_ids]
        _check_no_leak(ids, q.mask, self.name)
        return SearchOutput(
            ids=ids,
            distance_computations=int(res.distance_evaluations),
            extra={
                "hops_1hop": int(res.hops_1hop),
                "hops_2hop": int(res.hops_2hop),
                "hops_teleport": int(res.hops_teleport),
                "mean_s_loc_hat": float(res.mean_s_loc_hat),
                "n_ranges": int(len(starts)),
            },
        )


class PrismV3FullSystem:
    """Native C++ TriModalPlannerV3 (UBP CRoaring + H-HNSW v2 + Local-Stall Guard + NEON Mode 3)."""

    def __init__(self, z_corpus: ZOrderedCorpus, planner: TriModalPlannerV3, name: str):
        self.name = name
        self.z_corpus = z_corpus
        self.planner = planner

    def search(self, q: QuerySpec, k: int) -> SearchOutput:
        starts, ends, n_cand = _compile_ranges_from_tokens(self.z_corpus, q.extra["ubp_tokens"])
        res = self.planner.query_with_ranges(
            query_vec=q.vector, starts=starts, ends=ends, n_cand=n_cand, k=k
        )
        ids = [int(self.z_corpus.z_to_orig[zi]) for zi in res.top_k_ids]
        _check_no_leak(ids, q.mask, self.name)
        return SearchOutput(
            ids=ids,
            distance_computations=int(res.distance_evaluations),
            extra={
                "execution_mode": res.execution_mode,
                "stalled_escalated": bool(res.stalled_escalated),
                "candidate_count": int(res.candidate_count),
                "n_ranges": int(res.n_ranges),
            },
        )


# ---------------------------------------------------------------------------
# Dev workload builders (strictly dev query indices [0..499])
# ---------------------------------------------------------------------------
def _sample_h2_tokens_and_docs(
    S_target: float, rng: np.random.Generator, b: int = 8, L: int = 4
) -> Tuple[List[int], List[str]]:
    n_docs = b ** L
    n_folders = b ** (L - 1)
    target_docs = max(1, int(round(S_target * n_docs)))
    n_full_folders = target_docs // b
    rem = target_docs % b
    n_pick_folders = n_full_folders + (1 if rem > 0 else 0)
    chosen_folders = rng.choice(n_folders, size=n_pick_folders, replace=False)

    docs: List[int] = []
    ubp_tokens: List[str] = []
    for fi in chosen_folders[:n_full_folders]:
        fi_int = int(fi)
        ubp_tokens.append(f"node_L3_{fi_int}")
        base = fi_int * b
        docs.extend(range(base, base + b))
    if rem > 0:
        base = int(chosen_folders[-1]) * b
        kept = rng.choice(np.arange(base, base + b), size=rem, replace=False)
        for di in kept:
            di_int = int(di)
            docs.append(di_int)
            ubp_tokens.append(f"doc_L4_{di_int}")
    docs.sort()
    return docs, ubp_tokens


def _build_shared_faiss_and_v3_indices(
    overlay, X: np.ndarray, seed: int, ef_construction: int = 64
) -> Tuple[ZOrderedCorpus, FaissHNSWSystem, Dict[str, GeometricHHNSW], Dict[str, float]]:
    t0 = time.perf_counter()
    z_corpus = ZOrderedCorpus(X, overlay.ancestor_lineages, overlay.meaning_magnet_ids)
    t_z = time.perf_counter() - t0
    l2_ids = [lin[-3] if len(lin) >= 3 else lin[-1] for lin in z_corpus.ancestor_lineages]

    # Build ONE shared FAISS IndexHNSWFlat(d, 16) on z_corpus.vectors so E1 & E2 share the EXACT base graph!
    faiss_m16 = FaissHNSWSystem(
        z_corpus.vectors,
        M=16,
        ef_construction=ef_construction,
        ef_search=64,
        seed=seed,
        name="faiss-hnsw-M16",
        ext_id_map=z_corpus.z_to_orig,
    )
    prebuilt = (faiss_m16.index, faiss_m16.perm)

    idx_ring_m4 = GeometricHHNSW(
        z_corpus.vectors,
        z_corpus.primary_containers,
        l2_ids,
        z_corpus.meaning_magnet_ids,
        bridge_config=GeometricBridgeConfig.for_m_bridge(4, "ring_chord"),
        M=16,
        seed=seed,
        prebuilt_faiss=prebuilt,
    )
    idx_geom_m4 = GeometricHHNSW(
        z_corpus.vectors,
        z_corpus.primary_containers,
        l2_ids,
        z_corpus.meaning_magnet_ids,
        bridge_config=GeometricBridgeConfig.for_m_bridge(4, "geometric"),
        M=16,
        seed=seed,
        prebuilt_faiss=prebuilt,
    )
    idx_geom_m8 = GeometricHHNSW(
        z_corpus.vectors,
        z_corpus.primary_containers,
        l2_ids,
        z_corpus.meaning_magnet_ids,
        bridge_config=GeometricBridgeConfig.for_m_bridge(8, "geometric"),
        M=16,
        seed=seed,
        prebuilt_faiss=prebuilt,
    )
    timings = {
        "z_order_sec": t_z,
        "faiss_m16_sec": faiss_m16.build_sec,
        "ring_m4_bridge_sec": idx_ring_m4.bridge_build_sec,
        "geom_m4_bridge_sec": idx_geom_m4.bridge_build_sec,
        "geom_m8_bridge_sec": idx_geom_m8.bridge_build_sec,
        "geom_m8_ram_mb": idx_geom_m8.memory_footprint_bytes()["total_bytes"] / (1024 ** 2),
        "geom_m8_bridge_ram_pct": 100.0
        * idx_geom_m8.memory_footprint_bytes()["bridges_bytes"]
        / max(1, idx_geom_m8.memory_footprint_bytes()["vectors_bytes"] + idx_geom_m8.memory_footprint_bytes()["base_hnsw_bytes"]),
    }
    return (
        z_corpus,
        faiss_m16,
        {"ring_m4": idx_ring_m4, "geom_m4": idx_geom_m4, "geom_m8": idx_geom_m8},
        timings,
    )


# ---------------------------------------------------------------------------
# Summary aggregation strictly from raw JSONL files
# ---------------------------------------------------------------------------
def summarize_raw_dir(raw_dir: str, run_id: str = "") -> Dict[str, Any]:
    groups_h2: Dict[Tuple[str, float], List[Dict[str, Any]]] = defaultdict(list)
    groups_h3: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    total_records = 0

    for fname in sorted(os.listdir(raw_dir)):
        if not fname.endswith(".jsonl"):
            continue
        if run_id and not fname.startswith(run_id + "__"):
            continue
        with open(os.path.join(raw_dir, fname), "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                total_records += 1
                hyp = rec["hypothesis"]
                if hyp == "H2_DEV":
                    groups_h2[(rec["system"], float(rec["condition"]["S_target"]))].append(rec)
                elif hyp == "H3_DEV":
                    r_m = float(rec["condition"]["r_measured"])
                    if r_m <= 0.5:
                        groups_h3[(rec["system"], "r_le_0.5")].append(rec)
                    elif r_m >= 2.0:
                        groups_h3[(rec["system"], "r_ge_2.0")].append(rec)
                    groups_h3[(rec["system"], "all")].append(rec)

    def _agg(recs: List[Dict[str, Any]]) -> Dict[str, Any]:
        recalls = [float(r["recall"]) * 100.0 for r in recs if r["recall"] is not None]
        lats = [float(r["wall_ns"]) / 1e6 for r in recs]
        dists = [float(r["distance_computations"]) for r in recs if r["distance_computations"] is not None]
        esc = sum(1 for r in recs if r.get("extra", {}).get("stalled_escalated"))
        return {
            "n": len(recs),
            "recall_pct": round(float(np.mean(recalls)), 2) if recalls else None,
            "dist_mean": round(float(np.mean(dists)), 1) if dists else None,
            "lat_med_ms": round(float(np.median(lats)), 3) if lats else None,
            "lat_p95_ms": round(float(np.percentile(lats, 95)), 3) if lats else None,
            "lat_p99_ms": round(float(np.percentile(lats, 99)), 3) if lats else None,
            "stall_escalated_n": esc,
        }

    h2_out: Dict[str, Dict[str, Any]] = {}
    for (sys_name, s_val), recs in sorted(groups_h2.items()):
        h2_out.setdefault(sys_name, {})[str(s_val)] = _agg(recs)

    h3_out: Dict[str, Dict[str, Any]] = {}
    for (sys_name, bucket), recs in sorted(groups_h3.items()):
        h3_out.setdefault(sys_name, {})[bucket] = _agg(recs)

    return {"total_records": total_records, "H2_DEV": h2_out, "H3_DEV": h3_out}


def main() -> int:
    ap = argparse.ArgumentParser(description="Prism-ANN v3 Phase 17-03 Exploratory Dev Split (E1-E3)")
    ap.add_argument("--n-corpus", type=int, default=100_000)
    ap.add_argument("--n-dev-queries", type=int, default=500, help="Strictly within dev slice [0..499]")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tau-stall", type=float, default=0.04)
    ap.add_argument("--run-id", default="v3-dev-exploratory-002")
    ap.add_argument("--out-dir", default=os.path.join(REPO_ROOT, "results", "v3_dev"))
    args = ap.parse_args()

    assert args.n_dev_queries <= 500, "Dev queries MUST stay strictly within [0..499]!"
    raw_dir = os.path.join(args.out_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    # Clean any stale files with the same run_id before writing fresh
    for fn in os.listdir(raw_dir):
        if fn.startswith(args.run_id + "__") and fn.endswith(".jsonl"):
            os.unlink(os.path.join(raw_dir, fn))

    t_all = time.perf_counter()
    X, Q_all, qids_all = load_quora_embeddings(n_corpus=args.n_corpus)
    # Strictly dev queries [0..499] (reserving [500..9,984] for Phase 19 confirmatory test!)
    Q_dev = np.ascontiguousarray(Q_all[: args.n_dev_queries], dtype=np.float32)
    qids_dev = qids_all[: args.n_dev_queries]
    N, d = X.shape
    fz = freeze_status()
    sha = git_sha()
    ctx_base = dict(run_id=args.run_id, run_type="exploratory", git_sha=sha, freeze_match=fz["match"])
    print(f"[v3-dev] run_id={args.run_id} N={N} Q_dev={len(Q_dev)} (indices 0..{len(Q_dev)-1}) sha={sha[:10]} v2_freeze={fz['match']}")

    writer = RawWriter(raw_dir, args.run_id)
    build_meta: Dict[str, Any] = {}

    try:
        # ===================================================================
        # PART 1: H2_DEV (Random assignment, S in {0.1%, 0.5%, 1%, 5%})
        # Covers E1 (ring vs geom M4 vs geom M8 + guard), E2 (4-way portals),
        # and E3 (C++ NEON Mode 3 f32/sq8 vs BLAS, FAISS, ACORN-1, hnswlib)
        # ===================================================================
        rng_h2 = np.random.default_rng(17_200 + args.seed * 101)
        ov_h2 = build_overlay(X, mode="random", seed=args.seed, b=8, L=4)
        workloads_h2: Dict[float, List[QuerySpec]] = {}
        for S_target in H2_SELECTIVITIES:
            specs: List[QuerySpec] = []
            for qi in range(len(Q_dev)):
                allowed_docs, ubp_tokens = _sample_h2_tokens_and_docs(S_target, rng_h2)
                mask = np.zeros(N, dtype=np.bool_)
                for di in allowed_docs:
                    mask[ov_h2.doc_to_chunks[f"doc_L4_{di}"]] = True
                qv = Q_dev[qi]
                gt = _exact_top_k(X, qv, mask, k=10)
                specs.append(
                    QuerySpec(
                        query_id=f"DEV_H2_S{S_target}_{qids_dev[qi]}",
                        vector=qv,
                        mask=mask,
                        gt_ids=gt,
                        condition={"S_target": float(S_target), "S_actual": float(mask.mean())},
                        extra={"allowed_doc_ints": allowed_docs, "ubp_tokens": ubp_tokens},
                    )
                )
            workloads_h2[S_target] = specs

        z_h2, faiss_m16_h2, hhnsw_h2, timings_h2 = _build_shared_faiss_and_v3_indices(ov_h2, X, seed=args.seed)
        build_meta["H2_DEV"] = timings_h2
        print(f"[v3-dev] H2_DEV build timings: {json.dumps({k: round(v, 3) for k, v in timings_h2.items()})}")

        ctx_h2 = RunContext(hypothesis="H2_DEV", **ctx_base)

        def _eval_h2(sys_obj) -> None:
            for S_target in H2_SELECTIVITIES:
                t_s = time.perf_counter()
                n_w = writer.write_all(run_condition(sys_obj, workloads_h2[S_target], k=10, seed=args.seed, ctx=ctx_h2))
                print(f"  [H2_DEV] S={S_target:<5} {sys_obj.name:<30}: {n_w} recs in {time.perf_counter()-t_s:.2f}s")

        # E3 baselines + E2(a)
        _eval_h2(ExactBruteForceSystem(X))
        _eval_h2(CppMode3System(z_h2, precision="f32", name="cpp-mode3-f32"))
        _eval_h2(CppMode3System(z_h2, precision="sq8", name="cpp-mode3-sq8"))
        _eval_h2(faiss_m16_h2)

        # E2(a_cpp) sanity check + E2(b) FAISS M16 + 4 Portals
        _eval_h2(HHNSWV3GraphSystem(z_h2, hhnsw_h2["geom_m8"], "faiss-M16-cpp-0portal", use_express_bridges=False, use_portals=False, faiss_style_1hop=True))
        _eval_h2(HHNSWV3GraphSystem(z_h2, hhnsw_h2["geom_m8"], "faiss-M16+4portals", use_express_bridges=False, use_portals=True, max_portals=4, faiss_style_1hop=True))

        # E1 + E2(c) + E2(d)
        _eval_h2(HHNSWV3GraphSystem(z_h2, hhnsw_h2["ring_m4"], "v2-ring-chord-M4", tau_high=0.55, use_express_bridges=True, use_portals=True))
        _eval_h2(HHNSWV3GraphSystem(z_h2, hhnsw_h2["geom_m4"], "v3-geom-M4", tau_high=0.55, use_express_bridges=True, use_portals=True))
        _eval_h2(HHNSWV3GraphSystem(z_h2, hhnsw_h2["geom_m8"], "hhnsw-v2-geom-M8-noportal", tau_high=0.55, use_express_bridges=True, use_portals=False))
        _eval_h2(HHNSWV3GraphSystem(z_h2, hhnsw_h2["geom_m8"], "v3-geom-M8", tau_high=0.55, use_express_bridges=True, use_portals=True))

        # Full TriModalPlannerV3 with Local-Stall Guard (sq8 & f32)
        planner_sq8_h2 = TriModalPlannerV3(
            ov_h2.auth_graph, z_h2, hhnsw_h2["geom_m8"], ef_search=64,
            tau_high=0.55, tau_low=0.02, tau_stall=args.tau_stall, n_guard=25_000, mode3_precision="sq8",
        )
        planner_f32_h2 = TriModalPlannerV3(
            ov_h2.auth_graph, z_h2, hhnsw_h2["geom_m8"], ef_search=64,
            tau_high=0.55, tau_low=0.02, tau_stall=args.tau_stall, n_guard=25_000, mode3_precision="f32",
        )
        _eval_h2(PrismV3FullSystem(z_h2, planner_sq8_h2, "v3-full-guard-sq8"))
        _eval_h2(PrismV3FullSystem(z_h2, planner_f32_h2, "v3-full-guard-f32"))

        del z_h2, faiss_m16_h2, hhnsw_h2, planner_sq8_h2, planner_f32_h2
        gc.collect()

        # Real external C++ baselines for E3: upstream ACORN-1 & hnswlib-M16
        if Acorn1System.available():
            acorn_h2 = Acorn1System(X, M=16, ef_construction=64, ef_search=64, seed=args.seed, name="acorn-1")
            try:
                _eval_h2(acorn_h2)
            finally:
                acorn_h2.close()
                del acorn_h2
                gc.collect()

        hnsw_h2 = HnswlibSystem(X, M=16, ef_construction=64, ef_search=64, seed=args.seed, name="hnswlib-M16")
        _eval_h2(hnsw_h2)
        del hnsw_h2, workloads_h2, ov_h2
        gc.collect()

        # ===================================================================
        # PART 2: H3_DEV (Cluster-aligned, S=2%, r <= 0.5 & r >= 2.0)
        # Covers E1 (ring vs geom + Local-Stall Guard), E2 (4-way portals),
        # E3 (latency vs baselines), and tau_high calibration {0.25,0.40,0.55,0.70}
        # ===================================================================
        rng_h3 = np.random.default_rng(17_300 + args.seed * 107)
        ov_h3 = build_overlay(X, mode="cluster", seed=args.seed, b=8, L=4)
        flat_ip = faiss.IndexFlatIP(d)
        flat_ip.add(np.ascontiguousarray(X, dtype=np.float32))
        _, top100_unf = flat_ip.search(Q_dev, 100)
        del flat_ip

        centroid_sims = Q_dev @ ov_h3.folder_centroids.T
        n_half = len(Q_dev) // 2
        n_folders_target = 10  # 10 / 512 ~= 1.95% (~2% target selectivity)

        specs_h3: List[QuerySpec] = []
        for qi in range(len(Q_dev)):
            order_f = np.argsort(-centroid_sims[qi])
            if qi < n_half:
                regime = "near"
                chosen_f = order_f[:n_folders_target].tolist()
            else:
                regime = "far"
                chosen_f = rng_h3.choice(order_f[64:], size=n_folders_target, replace=False).tolist()

            mask = np.zeros(N, dtype=np.bool_)
            ubp_tokens: List[str] = []
            for fi in chosen_f:
                fid = ov_h3.folder_list[int(fi)]
                ubp_tokens.append(fid)
                mask[ov_h3.folder_to_chunks[fid]] = True

            s_actual = float(mask.mean())
            s_loc_100 = float(np.mean(mask[top100_unf[qi]]))
            r_measured = (s_loc_100 / s_actual) if s_actual > 0.0 else 0.0
            qv = Q_dev[qi]
            gt = _exact_top_k(X, qv, mask, k=10)
            specs_h3.append(
                QuerySpec(
                    query_id=f"DEV_H3_{regime}_{qids_dev[qi]}",
                    vector=qv,
                    mask=mask,
                    gt_ids=gt,
                    condition={
                        "S_target": 0.02,
                        "S_actual": s_actual,
                        "r_measured": float(r_measured),
                        "regime": regime,
                    },
                    extra={"s_loc_100": s_loc_100, "ubp_tokens": ubp_tokens},
                )
            )
        n_le05 = sum(1 for s in specs_h3 if s.condition["r_measured"] <= 0.5)
        n_ge20 = sum(1 for s in specs_h3 if s.condition["r_measured"] >= 2.0)
        print(f"[v3-dev] H3_DEV built: total={len(specs_h3)} (r<=0.5: {n_le05}, r>=2.0: {n_ge20})")

        z_h3, faiss_m16_h3, hhnsw_h3, timings_h3 = _build_shared_faiss_and_v3_indices(ov_h3, X, seed=args.seed)
        build_meta["H3_DEV"] = timings_h3
        ctx_h3 = RunContext(hypothesis="H3_DEV", **ctx_base)

        def _eval_h3(sys_obj) -> None:
            t_s = time.perf_counter()
            n_w = writer.write_all(run_condition(sys_obj, specs_h3, k=10, seed=args.seed, ctx=ctx_h3))
            print(f"  [H3_DEV] {sys_obj.name:<30}: {n_w} recs in {time.perf_counter()-t_s:.2f}s")

        _eval_h3(ExactBruteForceSystem(X))
        _eval_h3(CppMode3System(z_h3, precision="f32", name="cpp-mode3-f32"))
        _eval_h3(CppMode3System(z_h3, precision="sq8", name="cpp-mode3-sq8"))
        _eval_h3(faiss_m16_h3)

        # E2 4-way ablation on H3
        _eval_h3(HHNSWV3GraphSystem(z_h3, hhnsw_h3["geom_m8"], "faiss-M16-cpp-0portal", use_express_bridges=False, use_portals=False, faiss_style_1hop=True))
        _eval_h3(HHNSWV3GraphSystem(z_h3, hhnsw_h3["geom_m8"], "faiss-M16+4portals", use_express_bridges=False, use_portals=True, max_portals=4, faiss_style_1hop=True))
        _eval_h3(HHNSWV3GraphSystem(z_h3, hhnsw_h3["ring_m4"], "v2-ring-chord-M4", tau_high=0.55, use_express_bridges=True, use_portals=True))
        _eval_h3(HHNSWV3GraphSystem(z_h3, hhnsw_h3["geom_m4"], "v3-geom-M4", tau_high=0.55, use_express_bridges=True, use_portals=True))
        _eval_h3(HHNSWV3GraphSystem(z_h3, hhnsw_h3["geom_m8"], "hhnsw-v2-geom-M8-noportal", tau_high=0.55, use_express_bridges=True, use_portals=False))

        # P3b tau_high calibration sweep vs static 2-hop
        _eval_h3(HHNSWV3GraphSystem(z_h3, hhnsw_h3["geom_m8"], "v3-geom-M8-static2hop", use_express_bridges=True, use_portals=True, use_gls_adaptive=False))
        for th in (0.25, 0.40, 0.55, 0.70):
            _eval_h3(HHNSWV3GraphSystem(z_h3, hhnsw_h3["geom_m8"], f"v3-geom-M8-tau{th:.2f}", tau_high=th, use_express_bridges=True, use_portals=True, use_gls_adaptive=True))

        # Local-Stall Mode-3 Guard (sq8 & f32)
        planner_sq8_h3 = TriModalPlannerV3(
            ov_h3.auth_graph, z_h3, hhnsw_h3["geom_m8"], ef_search=64,
            tau_high=0.55, tau_low=0.02, tau_stall=args.tau_stall, n_guard=25_000, mode3_precision="sq8",
        )
        planner_f32_h3 = TriModalPlannerV3(
            ov_h3.auth_graph, z_h3, hhnsw_h3["geom_m8"], ef_search=64,
            tau_high=0.55, tau_low=0.02, tau_stall=args.tau_stall, n_guard=25_000, mode3_precision="f32",
        )
        _eval_h3(PrismV3FullSystem(z_h3, planner_sq8_h3, "v3-full-guard-sq8"))
        _eval_h3(PrismV3FullSystem(z_h3, planner_f32_h3, "v3-full-guard-f32"))

        del z_h3, faiss_m16_h3, hhnsw_h3, planner_sq8_h3, planner_f32_h3
        gc.collect()

        if Acorn1System.available():
            acorn_h3 = Acorn1System(X, M=16, ef_construction=64, ef_search=64, seed=args.seed, name="acorn-1")
            try:
                _eval_h3(acorn_h3)
            finally:
                acorn_h3.close()
                del acorn_h3
                gc.collect()

        hnsw_h3 = HnswlibSystem(X, M=16, ef_construction=64, ef_search=64, seed=args.seed, name="hnswlib-M16")
        _eval_h3(hnsw_h3)
        del hnsw_h3
        gc.collect()
    finally:
        writer.close()

    summary = summarize_raw_dir(raw_dir, run_id=args.run_id)
    summary["run_id"] = args.run_id
    summary["run_type"] = "exploratory"
    summary["tau_stall"] = args.tau_stall
    summary["git_sha"] = sha
    summary["v2_freeze_match"] = fz["match"]
    summary["n_corpus"] = N
    summary["dev_query_indices"] = f"0..{len(Q_dev)-1}"
    summary["reserved_test_query_indices"] = f"{len(Q_dev)}..{len(Q_all)-1}"
    summary["build_meta"] = build_meta
    summary["total_wall_sec"] = round(time.perf_counter() - t_all, 2)

    out_json = os.path.join(args.out_dir, "summary_dev.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    print(f"[v3-dev] DONE in {summary['total_wall_sec']}s | wrote {writer.count} raw recs -> {raw_dir} | summary -> {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
