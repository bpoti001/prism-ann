#!/usr/bin/env python3
"""
Brake 2 (v2/v3): figure-review presence + artifact-hash checker (ADR-0004/ADR-0005)
===================================================================================
This script does NOT evaluate figures and contains no scores or verdicts.

Per ADR-0004 §7 and ADR-0005, the figure review is written at review time by a fresh
reviewer agent that opens the compiled PNG/PDF figures. This checker verifies that
`results/<version>/review/figure_review.md` exists and records the SHA-256 of every
current figure artifact (`paper/figures/<version>_*.png` and `paper/figures/<version>_*.pdf`).
If any figure is regenerated after the review, its hash changes and this check fails
until the figures are re-reviewed.

Exit 0 = review exists and covers the current artifacts; exit 1 otherwise.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import os
import sys
from typing import List, Tuple

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_VERSION = "v3"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def current_artifacts(repo_root: str = REPO_ROOT, version: str = DEFAULT_VERSION) -> List[Tuple[str, str]]:
    globs = (f"paper/figures/{version}_*.png", f"paper/figures/{version}_*.pdf")
    paths: List[str] = []
    for g in globs:
        paths.extend(glob.glob(os.path.join(repo_root, g)))
    return [(os.path.relpath(p, repo_root), sha256_file(p)) for p in sorted(paths)]


def check(
    repo_root: str = REPO_ROOT,
    review_path: str | None = None,
    version: str = DEFAULT_VERSION,
) -> Tuple[bool, List[str]]:
    if review_path is None:
        review_path = os.path.join(repo_root, "results", version, "review", "figure_review.md")
    problems: List[str] = []
    arts = current_artifacts(repo_root, version=version)
    if not arts:
        problems.append(f"no {version} figure artifacts found (paper/figures/{version}_*.png|pdf)")
    if not os.path.exists(review_path):
        problems.append(f"missing review file: {os.path.relpath(review_path, repo_root)}")
        return False, problems
    with open(review_path, "r", encoding="utf-8") as f:
        review = f.read()
    for rel, digest in arts:
        if digest not in review:
            problems.append(f"review does not reference current SHA-256 of {rel} ({digest[:12]}...)")
    return not problems, problems


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=("v2", "v3"), default=DEFAULT_VERSION)
    args = ap.parse_args(argv)
    ver = args.version
    print(f"Brake 2 ({ver}): figure review presence + artifact SHA-256 check")
    ok, problems = check(version=ver)
    for rel, digest in current_artifacts(version=ver):
        print(f"  artifact {rel}  sha256={digest}")
    for p in problems:
        print(f"  [FAIL] {p}")
    print("  [PASS] figure_review.md covers all current figure artifacts" if ok else "  Brake 2 check failed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
