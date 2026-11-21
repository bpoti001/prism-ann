#!/usr/bin/env python3
"""
Brake 3 (v2/v3): peer-review presence + manuscript-hash checker (ADR-0004/ADR-0005)
===================================================================================
This script does NOT review the paper and contains no scores or verdicts.

Per ADR-0004 §7 and ADR-0005, the peer review is written at review time by a fresh
reviewer agent that reads the compiled PDF. This checker verifies that
`results/<version>/review/peer_review.md` exists and records the SHA-256 of the
current compiled manuscript (`paper/prism_ann.pdf`). Recompiling the paper changes
the hash and the check fails until the new PDF is re-reviewed.

Exit 0 = review exists and references the current PDF hash; exit 1 otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from typing import List, Tuple

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_VERSION = "v3"
PDF_PATH = os.path.join(REPO_ROOT, "paper", "prism_ann.pdf")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(
    review_path: str | None = None,
    pdf_path: str = PDF_PATH,
    version: str = DEFAULT_VERSION,
) -> Tuple[bool, List[str]]:
    if review_path is None:
        review_path = os.path.join(REPO_ROOT, "results", version, "review", "peer_review.md")
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


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=("v2", "v3"), default=DEFAULT_VERSION)
    args = ap.parse_args(argv)
    ver = args.version
    print(f"Brake 3 ({ver}): peer review presence + manuscript SHA-256 check")
    if os.path.exists(PDF_PATH):
        print(f"  manuscript {os.path.relpath(PDF_PATH, REPO_ROOT)} sha256={sha256_file(PDF_PATH)}")
    ok, problems = check(version=ver)
    for p in problems:
        print(f"  [FAIL] {p}")
    print("  [PASS] peer_review.md references the current manuscript" if ok else "  Brake 3 check failed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
