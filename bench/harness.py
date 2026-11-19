#!/usr/bin/env python3
"""
Provenance harness for Prism-ANN v2 (ADR-0004, experiments/v2/PROTOCOL_v2.md)
=============================================================================
Single entrypoint that emits per-query raw JSONL records into results/v2/raw*/.

Deep Module seam (ADR-0004):
    run_condition(system, queries, k, seed, ctx) -> Iterator[RawRecord]

Every record carries: run_id, run_type, git SHA, freeze match, hypothesis, system,
seed, condition (selectivity / measured r / ...), query_id, wall_ns (perf_counter_ns),
distance computations (None when the system does not expose them), result IDs,
ground-truth IDs, and recall.  No metric is ever computed here from a formula; the
only derived per-record quantity is recall = |result ∩ gt| / |gt|.

CLI (all measurement goes through this file):
    python -m bench.harness --run-type smoke        --n-corpus 20000 ...
    python -m bench.harness --run-type confirmatory ...
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Optional, Protocol, Sequence

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FREEZE_PATH = os.path.join(REPO_ROOT, "FREEZE.md")
FROZEN_DIR = os.path.join(REPO_ROOT, "src", "modules", "prism_ann")


# ---------------------------------------------------------------------------
# Provenance helpers
# ---------------------------------------------------------------------------
def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:  # pragma: no cover - git missing
        return "unknown"


def git_dirty_paths() -> List[str]:
    """Tracked files with uncommitted modifications (untracked files ignored)."""
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=REPO_ROOT, text=True
        )
    except Exception:  # pragma: no cover
        return ["<git unavailable>"]
    return sorted(line[3:] for line in out.splitlines() if line.strip())


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_freeze_hashes(freeze_path: str = FREEZE_PATH) -> Dict[str, str]:
    """Parses `<sha256>  <relpath>` lines from FREEZE.md."""
    hashes: Dict[str, str] = {}
    with open(freeze_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2 and len(parts[0]) == 64 and parts[1].startswith("src/"):
                hashes[parts[1]] = parts[0]
    return hashes


def freeze_status(repo_root: str = REPO_ROOT, freeze_path: str = FREEZE_PATH) -> Dict[str, Any]:
    """Compares current SHA-256 of every frozen file against FREEZE.md."""
    expected = read_freeze_hashes(freeze_path)
    mismatches = {}
    for rel, exp in sorted(expected.items()):
        p = os.path.join(repo_root, rel)
        cur = sha256_file(p) if os.path.exists(p) else "<missing>"
        if cur != exp:
            mismatches[rel] = {"expected": exp, "current": cur}
    return {"match": bool(expected) and not mismatches, "n_files": len(expected), "mismatches": mismatches}


# ---------------------------------------------------------------------------
# Raw record + writer
# ---------------------------------------------------------------------------
@dataclass
class RawRecord:
    run_id: str
    run_type: str  # smoke | confirmatory | exploratory
    git_sha: str
    freeze_match: bool
    hypothesis: str
    system: str
    seed: int
    query_id: str
    wall_ns: int
    condition: Dict[str, Any] = field(default_factory=dict)
    distance_computations: Optional[int] = None
    result_ids: List[int] = field(default_factory=list)
    gt_ids: List[int] = field(default_factory=list)
    recall: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), sort_keys=True, separators=(",", ":"))


REQUIRED_FIELDS = (
    "run_id", "run_type", "git_sha", "freeze_match", "hypothesis", "system", "seed",
    "query_id", "wall_ns", "condition", "distance_computations", "result_ids", "gt_ids",
    "recall", "extra",
)


class RawWriter:
    """Append-only JSONL writer, one file per (run_id, hypothesis)."""

    def __init__(self, raw_dir: str, run_id: str):
        self.raw_dir = raw_dir
        self.run_id = run_id
        os.makedirs(raw_dir, exist_ok=True)
        self._handles: Dict[str, Any] = {}
        self.count = 0

    def path_for(self, hypothesis: str) -> str:
        return os.path.join(self.raw_dir, f"{self.run_id}__{hypothesis}.jsonl")

    def write(self, rec: RawRecord) -> None:
        h = self._handles.get(rec.hypothesis)
        if h is None:
            h = open(self.path_for(rec.hypothesis), "a", encoding="utf-8")
            self._handles[rec.hypothesis] = h
        h.write(rec.to_json() + "\n")
        self.count += 1

    def write_all(self, recs: Iterable[RawRecord]) -> int:
        n = 0
        for r in recs:
            self.write(r)
            n += 1
        return n

    def close(self) -> None:
        for h in self._handles.values():
            h.close()
        self._handles = {}


def recall_at_k(result_ids: Sequence[int], gt_ids: Sequence[int]) -> Optional[float]:
    if len(gt_ids) == 0:
        return None
    return len(set(int(x) for x in result_ids) & set(int(x) for x in gt_ids)) / float(len(gt_ids))


# ---------------------------------------------------------------------------
# run_condition seam
# ---------------------------------------------------------------------------
@dataclass
class QuerySpec:
    query_id: str
    vector: np.ndarray
    mask: np.ndarray  # bool[N] authorized set in ORIGINAL corpus id space
    gt_ids: List[int]
    condition: Dict[str, Any]
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchOutput:
    ids: List[int]
    distance_computations: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class FilteredSearchSystem(Protocol):
    name: str

    def search(self, q: QuerySpec, k: int) -> SearchOutput: ...


@dataclass
class RunContext:
    run_id: str
    run_type: str
    git_sha: str
    freeze_match: bool
    hypothesis: str


def run_condition(
    system: FilteredSearchSystem,
    queries: Sequence[QuerySpec],
    k: int,
    seed: int,
    ctx: RunContext,
) -> Iterator[RawRecord]:
    """Times each query with perf_counter_ns around system.search and yields a raw record."""
    for q in queries:
        t0 = time.perf_counter_ns()
        out = system.search(q, k)
        wall = time.perf_counter_ns() - t0
        ids = [int(x) for x in out.ids][:k]
        yield RawRecord(
            run_id=ctx.run_id,
            run_type=ctx.run_type,
            git_sha=ctx.git_sha,
            freeze_match=ctx.freeze_match,
            hypothesis=ctx.hypothesis,
            system=system.name,
            seed=int(seed),
            query_id=q.query_id,
            wall_ns=int(wall),
            condition=dict(q.condition),
            distance_computations=None if out.distance_computations is None else int(out.distance_computations),
            result_ids=ids,
            gt_ids=[int(x) for x in q.gt_ids],
            recall=recall_at_k(ids, q.gt_ids),
            extra={**q.extra, **out.extra},
        )


def make_run_id(run_type: str) -> str:
    return f"v2-{run_type}-{time.strftime('%Y%m%dT%H%M%S')}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prism-ANN v2 provenance harness (ADR-0004)")
    p.add_argument("--run-type", choices=["smoke", "confirmatory", "exploratory"], required=True)
    p.add_argument("--hypotheses", default="H1,H2,H3,H4")
    p.add_argument("--n-corpus", type=int, default=0, help="0 = full BEIR Quora corpus")
    p.add_argument("--n-queries", type=int, default=500)
    p.add_argument("--seeds", default="0,1,2")
    p.add_argument("--h1-principals", type=int, default=200, help="principals per seed for H1")
    p.add_argument("--h4-trials", type=int, default=5)
    p.add_argument("--raw-dir", default="")
    p.add_argument("--run-id", default="")
    p.add_argument("--allow-dirty", action="store_true", help="permit uncommitted tracked changes (smoke only)")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    fz = freeze_status()
    dirty = git_dirty_paths()
    if args.run_type == "confirmatory":
        if not fz["match"]:
            print(f"[harness] REFUSING confirmatory run: frozen files differ from FREEZE.md: {fz['mismatches']}")
            return 2
        if dirty:
            print(f"[harness] REFUSING confirmatory run: uncommitted tracked changes: {dirty}")
            return 2
    elif dirty and not args.allow_dirty:
        print(f"[harness] uncommitted tracked changes {dirty}; pass --allow-dirty for smoke/exploratory runs")
        return 2

    run_id = args.run_id or make_run_id(args.run_type)
    default_dir = "raw" if args.run_type == "confirmatory" else f"raw_{args.run_type}"
    raw_dir = args.raw_dir or os.path.join(REPO_ROOT, "results", "v2", default_dir)
    ctx_base = dict(run_id=run_id, run_type=args.run_type, git_sha=git_sha(), freeze_match=fz["match"])
    print(f"[harness] run_id={run_id} sha={ctx_base['git_sha']} freeze_match={fz['match']} raw_dir={raw_dir}")

    from bench import experiments  # lazy: heavy deps (faiss, torch, psycopg, authzed)

    writer = RawWriter(raw_dir, run_id)
    try:
        experiments.run_all(args, ctx_base, writer)
    finally:
        writer.close()
    print(f"[harness] wrote {writer.count} raw records to {raw_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
