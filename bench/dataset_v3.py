#!/usr/bin/env python3
"""
Multi-Corpus Dataset Loader & MiniLM Encoder for Prism-ANN v3 (ADR-0005)
========================================================================
Supports two distinct-domain real public corpora:
  1. `quora` — Full BEIR Quora (522,931 passages, all-MiniLM-L6-v2 384-d).
     Test queries strictly restricted to indices [500..9,984] (9,485 queries),
     100% disjoint from Phase 17 dev queries [0..499] and from corpus.
  2. `nq`    — BEIR Natural Questions Wikipedia (first 250,000 passages,
     all-MiniLM-L6-v2 384-d) with strictly disjoint BEIR NQ test queries
     (0 ID overlap, 0 exact text overlap).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from typing import Dict, List, Tuple

import numpy as np

from bench.dataset import MODEL_NAME, QUORA_DIR, load_quora_embeddings

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NQ_DIR = os.path.join(REPO_ROOT, "data", "beir", "nq")
QUORA_DEV_RESERVED = 500  # Indices [0..499] used in Phase 17 dev split!


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def encode_and_cache_nq(
    data_dir: str = NQ_DIR, n_corpus: int = 250_000, batch_size: int = 512
) -> Dict[str, object]:
    """Encodes first `n_corpus` BeIR/nq Wikipedia passages & strictly disjoint test queries."""
    import pyarrow.parquet as pq
    import torch
    from sentence_transformers import SentenceTransformer

    corpus_npy = os.path.join(data_dir, f"corpus_minilm_{n_corpus}.npy")
    queries_npy = os.path.join(data_dir, "queries_minilm.npy")
    qids_json = os.path.join(data_dir, "query_ids_disjoint.json")
    meta_path = os.path.join(data_dir, "minilm_meta.json")
    if (
        os.path.exists(corpus_npy)
        and os.path.exists(queries_npy)
        and os.path.exists(qids_json)
        and os.path.exists(meta_path)
    ):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        print(
            f"[dataset_v3] using cached BEIR NQ MiniLM: corpus={meta['n_corpus']} queries={meta['n_queries']}"
        )
        return meta

    t0 = time.perf_counter()
    c_path = os.path.join(data_dir, "corpus.parquet")
    q_path = os.path.join(data_dir, "queries.parquet")

    # Read only first n_corpus rows from parquet cleanly via row batches
    pf = pq.ParquetFile(c_path)
    c_ids: List[str] = []
    c_texts: List[str] = []
    for batch in pf.iter_batches(batch_size=32768, columns=["_id", "title", "text"]):
        ids_b = batch.column("_id").to_pylist()
        titles_b = batch.column("title").to_pylist()
        texts_b = batch.column("text").to_pylist()
        for cid, t, x in zip(ids_b, titles_b, texts_b):
            c_ids.append(str(cid))
            t_s = t.strip() if t else ""
            x_s = x.strip() if x else ""
            c_texts.append(f"{t_s} {x_s}".strip() if t_s else x_s)
            if len(c_ids) >= n_corpus:
                break
        if len(c_ids) >= n_corpus:
            break

    assert len(c_ids) == n_corpus, f"Expected {n_corpus} NQ passages, got {len(c_ids)}"
    c_id_set = set(c_ids)
    c_text_set = set(c_texts)

    q_tbl = pq.read_table(q_path)
    q_ids_raw = q_tbl["_id"].to_pylist()
    q_texts_raw = q_tbl["text"].to_pylist()

    kept_q_ids: List[str] = []
    kept_q_texts: List[str] = []
    n_drop_id = 0
    n_drop_text = 0
    for qid, qtxt in zip(q_ids_raw, q_texts_raw):
        qid_s = str(qid)
        txt_s = (qtxt or "").strip()
        if not txt_s:
            continue
        if qid_s in c_id_set:
            n_drop_id += 1
            continue
        if txt_s in c_text_set:
            n_drop_text += 1
            continue
        kept_q_ids.append(qid_s)
        kept_q_texts.append(txt_s)

    assert len(set(kept_q_ids) & c_id_set) == 0, "NQ query IDs overlap corpus!"
    assert len(set(kept_q_texts) & c_text_set) == 0, "NQ query texts overlap corpus!"
    assert len(kept_q_ids) >= 2000, f"Too few disjoint NQ queries: {len(kept_q_ids)}"

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(
        f"[dataset_v3] encoding {len(c_texts)} BEIR NQ Wikipedia passages & "
        f"{len(kept_q_texts)} disjoint test queries with {MODEL_NAME} on {device} (batch_size={batch_size})",
        flush=True,
    )
    model = SentenceTransformer(MODEL_NAME, device=device, local_files_only=True)

    q_emb = model.encode(
        kept_q_texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype(np.float32)
    print(f"[dataset_v3] encoded {len(q_emb)} queries in {time.perf_counter()-t0:.1f}s", flush=True)

    # Encode corpus in 10,000-passage chunks with MPS cache clearing to prevent Metal OOM/swap
    dim = int(q_emb.shape[1])
    c_emb = np.empty((len(c_texts), dim), dtype=np.float32)
    chunk_sz = 10_000
    t_enc0 = time.perf_counter()
    for start in range(0, len(c_texts), chunk_sz):
        end = min(len(c_texts), start + chunk_sz)
        # Pre-truncate overly long strings (MiniLM max_seq_length is 256 tokens ~= 1,500 chars)
        sub_texts = [s[:1600] for s in c_texts[start:end]]
        emb_chunk = model.encode(
            sub_texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype(np.float32)
        c_emb[start:end] = emb_chunk
        if device == "mps":
            torch.mps.empty_cache()
        elapsed = time.perf_counter() - t_enc0
        rate = end / max(elapsed, 1e-6)
        eta = (len(c_texts) - end) / max(rate, 1e-6)
        print(
            f"[dataset_v3] encoded {end}/{len(c_texts)} ({100.0*end/len(c_texts):.1f}%) "
            f"| {rate:.0f} doc/s | elapsed {elapsed:.1f}s | ETA {eta:.1f}s",
            flush=True,
        )

    c_emb /= np.clip(np.linalg.norm(c_emb, axis=1, keepdims=True), 1e-9, None)
    q_emb /= np.clip(np.linalg.norm(q_emb, axis=1, keepdims=True), 1e-9, None)

    np.save(corpus_npy, c_emb)
    np.save(queries_npy, q_emb)
    with open(qids_json, "w", encoding="utf-8") as f:
        json.dump(kept_q_ids, f)

    meta = {
        "corpus": "BeIR/nq",
        "model": MODEL_NAME,
        "device": device,
        "n_corpus": int(c_emb.shape[0]),
        "n_queries": int(q_emb.shape[0]),
        "dim": int(c_emb.shape[1]),
        "n_dropped_id_overlap": int(n_drop_id),
        "n_dropped_text_overlap": int(n_drop_text),
        "id_overlap_after_filter": 0,
        "text_overlap_after_filter": 0,
        "encode_wall_sec": round(time.perf_counter() - t0, 2),
        "corpus_npy": os.path.basename(corpus_npy),
        "corpus_npy_sha256": _sha256(corpus_npy),
        "queries_npy_sha256": _sha256(queries_npy),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, sort_keys=True)
    print(f"[dataset_v3] NQ done in {meta['encode_wall_sec']}s -> {corpus_npy}")
    return meta


def load_corpus_v3(
    corpus_name: str, n_corpus: int = 0
) -> Tuple[np.ndarray, np.ndarray, List[str], Dict[str, object]]:
    """
    Loads confirmatory corpus + strictly held-out test queries:
      - 'quora': N=522,931 passages, queries strictly from [500..9,984] (dev [0..499] excluded!)
      - 'nq':    N=250,000 Wikipedia passages, all strictly disjoint BEIR NQ test queries
    """
    if corpus_name == "quora":
        X, Q_all, qids_all = load_quora_embeddings(n_corpus=n_corpus, data_dir=QUORA_DIR)
        # Strictly exclude Phase 17 dev queries [0..499]
        Q = np.ascontiguousarray(Q_all[QUORA_DEV_RESERVED:], dtype=np.float32)
        qids = list(qids_all[QUORA_DEV_RESERVED:])
        with open(os.path.join(QUORA_DIR, "minilm_meta.json"), "r", encoding="utf-8") as f:
            meta = json.load(f)
        meta["confirmatory_query_slice"] = f"{QUORA_DEV_RESERVED}..{len(qids_all) - 1}"
        meta["n_confirmatory_queries"] = len(qids)
        return X, Q, qids, meta
    elif corpus_name == "nq":
        with open(os.path.join(NQ_DIR, "minilm_meta.json"), "r", encoding="utf-8") as f:
            meta = json.load(f)
        corpus_mmap = np.load(os.path.join(NQ_DIR, str(meta["corpus_npy"])), mmap_mode="r")
        X = (
            np.array(corpus_mmap[:n_corpus], dtype=np.float32, copy=True)
            if (n_corpus > 0 and n_corpus < corpus_mmap.shape[0])
            else np.array(corpus_mmap, dtype=np.float32, copy=True)
        )
        Q = np.ascontiguousarray(np.load(os.path.join(NQ_DIR, "queries_minilm.npy")), dtype=np.float32)
        with open(os.path.join(NQ_DIR, "query_ids_disjoint.json"), "r", encoding="utf-8") as f:
            qids = json.load(f)
        return X, Q, qids, meta
    else:
        raise ValueError(f"Unknown corpus_name: {corpus_name}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Encode & cache BEIR NQ 250k with MiniLM")
    ap.add_argument("--n-corpus", type=int, default=250_000)
    ap.add_argument("--batch-size", type=int, default=512)
    args = ap.parse_args()
    encode_and_cache_nq(n_corpus=args.n_corpus, batch_size=args.batch_size)
