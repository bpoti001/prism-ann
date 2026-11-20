#!/usr/bin/env python3
"""
BEIR Quora dataset loader, MiniLM encoder/cache, and hierarchy overlays (ADR-0004).
===================================================================================
Encodes the real BEIR Quora corpus (522,931 passages) and strictly disjoint held-out
test queries (9,985 queries with 0 ID overlap and 0 exact text overlap) using the
locally cached `sentence-transformers/all-MiniLM-L6-v2` (384-d, L2-normalized).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

import faiss
import numpy as np

from src.modules.prism_ann.ubp_resolver import ZanzibarAuthGraph

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUORA_DIR = os.path.join(REPO_ROOT, "data", "beir", "quora")
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def encode_and_cache_quora(data_dir: str = QUORA_DIR, batch_size: int = 512) -> Dict[str, object]:
    """Encodes BEIR Quora corpus & strictly disjoint test queries via cached MiniLM."""
    import pyarrow.parquet as pq
    import torch
    from sentence_transformers import SentenceTransformer

    corpus_npy = os.path.join(data_dir, "corpus_minilm.npy")
    queries_npy = os.path.join(data_dir, "queries_minilm.npy")
    meta_path = os.path.join(data_dir, "minilm_meta.json")
    if os.path.exists(corpus_npy) and os.path.exists(queries_npy) and os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        print(f"[dataset] using cached MiniLM embeddings: corpus={meta['n_corpus']} queries={meta['n_queries']}")
        return meta

    t0 = time.perf_counter()
    c_tbl = pq.read_table(os.path.join(data_dir, "corpus.parquet"))
    q_tbl = pq.read_table(os.path.join(data_dir, "queries.parquet"))

    with open(os.path.join(data_dir, "qrels_test.tsv"), "r", encoding="utf-8") as f:
        test_qids = {row["query-id"] for row in csv.DictReader(f, delimiter="\t")}

    c_ids: List[str] = c_tbl["_id"].to_pylist()
    c_titles: List[str] = c_tbl["title"].to_pylist()
    c_texts_raw: List[str] = c_tbl["text"].to_pylist()
    c_texts = [
        f"{t.strip()} {x.strip()}".strip() if (t and t.strip()) else x.strip()
        for t, x in zip(c_titles, c_texts_raw)
    ]

    c_id_set = set(c_ids)
    c_text_set = set(c_texts)

    q_ids_all: List[str] = q_tbl["_id"].to_pylist()
    q_texts_all: List[str] = q_tbl["text"].to_pylist()

    kept_q_ids: List[str] = []
    kept_q_texts: List[str] = []
    n_test_total = 0
    n_dropped_id = 0
    n_dropped_text = 0
    for qid, qtxt in zip(q_ids_all, q_texts_all):
        if qid not in test_qids:
            continue
        n_test_total += 1
        txt = qtxt.strip()
        if qid in c_id_set:
            n_dropped_id += 1
            continue
        if txt in c_text_set:
            n_dropped_text += 1
            continue
        kept_q_ids.append(qid)
        kept_q_texts.append(txt)

    # Strict zero-overlap assertions
    assert len(set(kept_q_ids) & c_id_set) == 0, "Query IDs overlap with corpus IDs!"
    assert len(set(kept_q_texts) & c_text_set) == 0, "Query texts overlap with corpus texts!"
    assert len(kept_q_ids) >= 9000, f"Too few disjoint test queries: {len(kept_q_ids)}"

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(
        f"[dataset] encoding {len(c_texts)} corpus passages and {len(kept_q_texts)} held-out "
        f"test queries with {MODEL_NAME} on {device} (dropped {n_dropped_id} ID / {n_dropped_text} text overlaps)"
    )
    model = SentenceTransformer(MODEL_NAME, device=device, local_files_only=True)

    q_emb = model.encode(
        kept_q_texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype(np.float32)

    c_emb = model.encode(
        c_texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype(np.float32)

    # Enforce exact unit L2 norm
    c_emb /= np.clip(np.linalg.norm(c_emb, axis=1, keepdims=True), 1e-9, None)
    q_emb /= np.clip(np.linalg.norm(q_emb, axis=1, keepdims=True), 1e-9, None)

    np.save(corpus_npy, c_emb)
    np.save(queries_npy, q_emb)
    with open(os.path.join(data_dir, "query_ids_disjoint.json"), "w", encoding="utf-8") as f:
        json.dump(kept_q_ids, f)

    meta = {
        "model": MODEL_NAME,
        "device": device,
        "n_corpus": int(c_emb.shape[0]),
        "n_queries": int(q_emb.shape[0]),
        "dim": int(c_emb.shape[1]),
        "n_test_queries_raw": int(n_test_total),
        "n_dropped_id_overlap": int(n_dropped_id),
        "n_dropped_text_overlap": int(n_dropped_text),
        "id_overlap_after_filter": 0,
        "text_overlap_after_filter": 0,
        "encode_wall_sec": round(time.perf_counter() - t0, 2),
        "corpus_npy_sha256": _sha256(corpus_npy),
        "queries_npy_sha256": _sha256(queries_npy),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, sort_keys=True)
    print(f"[dataset] done in {meta['encode_wall_sec']}s: {corpus_npy} & {queries_npy}")
    return meta


def load_quora_embeddings(
    n_corpus: int = 0, seed: int = 0, data_dir: str = QUORA_DIR
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Loads cached MiniLM embeddings; if n_corpus > 0, takes a deterministic prefix/slice."""
    corpus = np.load(os.path.join(data_dir, "corpus_minilm.npy"), mmap_mode="r")
    queries = np.load(os.path.join(data_dir, "queries_minilm.npy"))
    with open(os.path.join(data_dir, "query_ids_disjoint.json"), "r", encoding="utf-8") as f:
        qids = json.load(f)

    if n_corpus > 0 and n_corpus < corpus.shape[0]:
        # Deterministic corpus subset (fixed prefix so all seeds/systems share identical corpus N)
        X = np.array(corpus[:n_corpus], dtype=np.float32, copy=True)
    else:
        X = np.array(corpus, dtype=np.float32, copy=True)
    Q = np.ascontiguousarray(queries, dtype=np.float32)
    return X, Q, qids


@dataclass
class HierarchyOverlay:
    auth_graph: ZanzibarAuthGraph
    ancestor_lineages: List[List[str]]
    meaning_magnet_ids: List[str]
    leaf_doc_ids: List[str]
    folder_ids: List[str]
    doc_to_chunks: Dict[str, np.ndarray]
    folder_to_chunks: Dict[str, np.ndarray]
    folder_centroids: np.ndarray  # shape (n_folders, d)
    folder_list: List[str]        # ordered node_L3_0 .. node_L3_{F-1}


def _faiss_kmeans(X: np.ndarray, k: int, seed: int, niter: int = 15) -> Tuple[np.ndarray, np.ndarray]:
    """Fast spherical k-means via FAISS returning (centroids [k, d], labels [N])."""
    N, d = X.shape
    k_eff = min(k, N)
    km = faiss.Kmeans(d, k_eff, niter=niter, verbose=False, spherical=True, seed=100 + seed)
    # Subsample training points if N > 120k for speed while preserving cluster geometry
    if N > 120_000:
        rng = np.random.default_rng(100 + seed)
        train_idx = rng.choice(N, size=120_000, replace=False)
        km.train(np.ascontiguousarray(X[train_idx]))
    else:
        km.train(np.ascontiguousarray(X))
    _, I = km.index.search(np.ascontiguousarray(X), 1)
    labels = I[:, 0].astype(np.int32)
    centroids = np.ascontiguousarray(km.centroids, dtype=np.float32)
    centroids /= np.clip(np.linalg.norm(centroids, axis=1, keepdims=True), 1e-9, None)
    return centroids, labels


def build_overlay(
    X: np.ndarray,
    mode: str,
    seed: int = 0,
    b: int = 8,
    L: int = 4,
    n_magnets: int = 64,
) -> HierarchyOverlay:
    """
    Constructs a Zanzibar tree (org -> L1 -> L2 -> folder -> doc, L=4, b=8;
    512 folders, 4,096 leaf docs) and attaches all N corpus passages to leaf docs.

    mode == 'random': docs placed into folders uniformly at random (r ~ 1).
    mode == 'cluster': passages clustered via spherical k-means into the 512 folders
                       so folders align tightly with embedding-space neighborhoods.
    """
    N, d = X.shape
    graph = ZanzibarAuthGraph.build_balanced_hierarchy(branching_factor=b, depth=L)
    n_folders = b ** (L - 1)  # 512
    n_docs = b ** L           # 4,096
    folder_list = [f"node_L{L-1}_{f}" for f in range(n_folders)]
    doc_list = [f"doc_L{L}_{i}" for i in range(n_docs)]

    # Precompute ancestor lineages for each leaf doc
    doc_lineage = {doc_id: graph.get_ancestor_lineage(doc_id) for doc_id in doc_list}

    # Meaning Magnets: 64 semantic clusters across corpus
    _, mag_labels = _faiss_kmeans(X, k=n_magnets, seed=seed + 777, niter=12)
    meaning_magnet_ids = [f"magnet_{int(m)}" for m in mag_labels]

    rng = np.random.default_rng(seed * 1009 + (1 if mode == "random" else 2))
    if mode == "random":
        # Group passages randomly into 4,096 leaf docs (so docs sit uniformly in folders)
        perm = rng.permutation(N)
        chunk_doc_idx = np.empty(N, dtype=np.int32)
        chunk_doc_idx[perm] = np.arange(N, dtype=np.int32) % n_docs
    elif mode == "cluster":
        # Cluster passages into 512 semantic folders via spherical k-means, then assign
        # within each folder to its b=8 leaf documents.
        _, f_labels = _faiss_kmeans(X, k=n_folders, seed=seed + 333, niter=15)
        chunk_doc_idx = np.empty(N, dtype=np.int32)
        for f in range(n_folders):
            members = np.flatnonzero(f_labels == f)
            if len(members) == 0:
                continue
            sub = rng.permutation(len(members)) % b
            chunk_doc_idx[members] = f * b + sub
    else:
        raise ValueError(f"unknown overlay mode: {mode}")

    ancestor_lineages: List[List[str]] = [doc_lineage[doc_list[int(di)]] for di in chunk_doc_idx]
    leaf_doc_ids = [doc_list[int(di)] for di in chunk_doc_idx]
    folder_ids = [folder_list[int(di) // b] for di in chunk_doc_idx]

    doc_buckets: Dict[str, List[int]] = {doc_id: [] for doc_id in doc_list}
    folder_buckets: Dict[str, List[int]] = {fid: [] for fid in folder_list}
    for idx, di in enumerate(chunk_doc_idx):
        di_int = int(di)
        doc_buckets[doc_list[di_int]].append(idx)
        folder_buckets[folder_list[di_int // b]].append(idx)

    doc_to_chunks = {k: np.array(v, dtype=np.int32) for k, v in doc_buckets.items()}
    folder_to_chunks = {k: np.array(v, dtype=np.int32) for k, v in folder_buckets.items()}

    folder_centroids = np.zeros((n_folders, d), dtype=np.float32)
    for fi, fid in enumerate(folder_list):
        ids = folder_to_chunks[fid]
        if len(ids) > 0:
            c = X[ids].mean(axis=0)
            nrm = float(np.linalg.norm(c))
            folder_centroids[fi] = c / nrm if nrm > 1e-9 else c

    return HierarchyOverlay(
        auth_graph=graph,
        ancestor_lineages=ancestor_lineages,
        meaning_magnet_ids=meaning_magnet_ids,
        leaf_doc_ids=leaf_doc_ids,
        folder_ids=folder_ids,
        doc_to_chunks=doc_to_chunks,
        folder_to_chunks=folder_to_chunks,
        folder_centroids=folder_centroids,
        folder_list=folder_list,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Encode & cache BEIR Quora with MiniLM")
    p.add_argument("--batch-size", type=int, default=512)
    args = p.parse_args()
    encode_and_cache_quora(batch_size=args.batch_size)
