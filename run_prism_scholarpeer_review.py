#!/usr/bin/env python3
"""
Brake 3 (v2): peer-review presence + manuscript-hash checker (ADR-0004)
======================================================================
This script does NOT review the paper and contains no scores or verdicts.

Per ADR-0004 §7, the peer review is written at review time by a fresh reviewer agent
that reads the compiled PDF.  This checker only verifies that
`results/v2/review/peer_review.md` exists and records the SHA-256 of the current
compiled manuscript (`paper/prism_ann.pdf`).  Recompiling the paper changes the hash
and the check fails until the new PDF is re-reviewed.

The v1 (Milestone 3) version of this script emitted a hardcoded recommendation and
meta-score; it was removed in Phase 13 (see docs/adr/0004 and the session retrospective).

Exit 0 = review exists and references the current PDF hash; exit 1 otherwise.
"""

from __future__ import annotations

import hashlib
import os
import sys
from typing import List, Tuple

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
REVIEW_PATH = os.path.join(REPO_ROOT, "results", "v2", "review", "peer_review.md")
PDF_PATH = os.path.join(REPO_ROOT, "paper", "prism_ann.pdf")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(review_path: str = REVIEW_PATH, pdf_path: str = PDF_PATH) -> Tuple[bool, List[str]]:
    problems: List[str] = []
    if not os.path.exists(pdf_path):
        problems.append(f"missing compiled manuscript: {pdf_path}")
        return False, problems
    digest = sha256_file(pdf_path)
    if not os.path.exists(review_path):
        problems.append(f"missing review file: {review_path}")
        return False, problems
    with open(review_path, "r", encoding="utf-8") as f:
        review = f.read()
    if digest not in review:
        problems.append(f"peer_review.md does not reference current PDF SHA-256 {digest}")
    return not problems, problems


def main() -> int:
    print("Brake 3 (v2): peer review presence + manuscript SHA-256 check")
    if os.path.exists(PDF_PATH):
        print(f"  manuscript {os.path.relpath(PDF_PATH, REPO_ROOT)} sha256={sha256_file(PDF_PATH)}")
    ok, problems = check()
    for p in problems:
        print(f"  [FAIL] {p}")
    print("  [PASS] peer_review.md references the current manuscript" if ok else "  Brake 3 check failed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
