#!/usr/bin/env python3
"""
Brake 2 (v2): figure-review presence + artifact-hash checker (ADR-0004)
=======================================================================
This script does NOT evaluate figures and contains no scores or verdicts.

Per ADR-0004 §7, the figure review is written at review time by a fresh reviewer
agent that opens the compiled PNG/PDF figures.  This checker only verifies that
`results/v2/review/figure_review.md` exists and records the SHA-256 of every current
v2 figure artifact (`paper/figures/v2_*.png` and `paper/figures/v2_*.pdf`).  If any
figure is regenerated after the review, its hash changes and this check fails until
the figures are re-reviewed.

The v1 (Milestone 3) version of this script printed hardcoded scores; it was removed
in Phase 13 (see docs/adr/0004 and the session retrospective).

Exit 0 = review exists and covers the current artifacts; exit 1 otherwise.
"""

from __future__ import annotations

import glob
import hashlib
import os
import sys
from typing import List, Tuple

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
REVIEW_PATH = os.path.join(REPO_ROOT, "results", "v2", "review", "figure_review.md")
FIGURE_GLOBS = ("paper/figures/v2_*.png", "paper/figures/v2_*.pdf")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def current_artifacts(repo_root: str = REPO_ROOT) -> List[Tuple[str, str]]:
    paths: List[str] = []
    for g in FIGURE_GLOBS:
        paths.extend(glob.glob(os.path.join(repo_root, g)))
    return [(os.path.relpath(p, repo_root), sha256_file(p)) for p in sorted(paths)]


def check(repo_root: str = REPO_ROOT, review_path: str = REVIEW_PATH) -> Tuple[bool, List[str]]:
    problems: List[str] = []
    arts = current_artifacts(repo_root)
    if not arts:
        problems.append("no v2 figure artifacts found (paper/figures/v2_*.png|pdf)")
    if not os.path.exists(review_path):
        problems.append(f"missing review file: {os.path.relpath(review_path, repo_root)}")
        return False, problems
    with open(review_path, "r", encoding="utf-8") as f:
        review = f.read()
    for rel, digest in arts:
        if digest not in review:
            problems.append(f"review does not reference current SHA-256 of {rel} ({digest[:12]}...)")
    return not problems, problems


def main() -> int:
    print("Brake 2 (v2): figure review presence + artifact SHA-256 check")
    ok, problems = check()
    for rel, digest in current_artifacts():
        print(f"  artifact {rel}  sha256={digest}")
    for p in problems:
        print(f"  [FAIL] {p}")
    print("  [PASS] figure_review.md covers all current figure artifacts" if ok else "  Brake 2 check failed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
