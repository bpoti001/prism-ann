# ADR-0000: ADR-to-arXiv Research & Software Factory Governance Gate

- **Status**: `accepted`
- **Date**: 2026-11-19
- **Scope**: All Research Modules, Benchmarks, Figures, and LaTeX Manuscripts
- **Mapped Paper Section**: Methodology & Reproducibility Protocol

## Context
Academic research codebases frequently suffer from undocumented architectural choices, post-hoc hypothesis rationalization (HARKing), and metric drift between benchmark outputs (`results/*.json`) and LaTeX manuscript tables (`paper/main.tex`). Conversely, enterprise software factories enforce strict ADR governance and Deep Module TDD but lack two-loop scientific hypothesis synthesis and peer-review verification.

## Decision
We unify the **ADR-Governed Software Factory** with the **Autonomous Two-Loop arXiv Research Pipeline**:
1. Every architectural innovation must be minted as an **ADR** (`docs/adr/NNNN-*.md`) using **Design-It-Twice**, where rejected alternatives map directly to experimental baselines and the chosen invariant maps to a formal mathematical theorem.
2. Every experimental run must pre-register its hypothesis and metric prediction in `experiments/<H-slug>/protocol.md` prior to benchmark execution.
3. Three deterministic brakes (`verify-governance` + `verify_hallucinations.py`, `PaperVizAgent`, and `ScholarPeer`) must pass before compiling the arXiv release bundle.

## Alternatives Considered (Design-It-Twice)
1. **Ad-hoc Notebook Prototyping**: Fast initial exploration, but causes irreproducible scripts and disconnect between paper proofs and code. Rejected.
2. **Rigid Enterprise Factory Without Two-Loop Synthesis**: Enforces code quality but lacks outer-loop scientific reflection (`findings.md` -> `DEEPEN / BROADEN / PIVOT / CONCLUDE`). Rejected.

## Mapped Paper Theorem & Bound
Enforces deterministic traceability: $0.0\%$ metric discrepancy between `results/*.json` and `paper/*.tex` and $\ge 95.0/100$ visual faithfulness across all figures.

## Deep Module Seam
`research_factory.py` (`classify_size`, `verify_governance`, `audit_paper`).

## Consequences
- **Positive**: Every ADR directly writes a section of the paper; zero hallucinated citations or numbers.
- **Negative**: Requires upfront protocol pre-registration before running sweeps.
- **Reversibility**: `Two-Way Door`.
