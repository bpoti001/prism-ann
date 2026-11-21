---
description: End-to-end ADR-to-arXiv Research & Software Factory workflow: Wayfinder + Grill-Me HITL Discovery -> ADR/Spec & GSD Roadmap -> Two-Stage Frozen Confirmatory Build -> Fresh Independent pro Review & 3-Brake SHA-256 Audit.
---

# `/adr-to-arxiv-factory` Workflow (v2.0)

Follow the unified 7-Gate workflow defined in `/Users/tejap/.gemini/config/skills/adr-to-arxiv-factory/SKILL.md`:

1. **Gate 0 — Adaptive T-Shirt Sizing (`[S]` | `[M]` | `[L]`)**:
   - Classify the task (`python3 research_factory.py size "<task>"` or explicit `[S]`/`[M]`/`[L]`).
   - If `[S]`: apply the surgical edit directly and verify governance/tests.
2. **Gate 0.5 — `Wayfinder` & `Grill-Me` HITL Discovery (for `[L]` / Open Ideas)**:
   - Use **`wayfinder`** (`docs/wayfinder/MAP-*.md`) + **`/grill-me`** (`grilling`, `grill-with-docs`, `domain-modeling`) to resolve fog-of-war decisions interactively with the user, then graduate into **`to-spec`** / **`to-tickets`**.
   - Once decisions are locked, switch to full autonomous GSD execution without further interruptions.
3. **Gate 1 & Gate 2 — Literature Recon, `GLOSSARY.md`, ADR-to-Theorem Mapping & GSD Roadmap**:
   - Update `literature/survey.md` and `GLOSSARY.md`, mint `docs/adr/NNNN-*.md` via **Design-It-Twice** (mapping trade-offs to formal Theorems/Propositions), register in `CONTEXT.md`, and add GSD phases to `.planning/ROADMAP.md` (`gsd-tools.cjs`).
4. **Gate 3 — `/show-me` Seam, Exploratory Dev Split & Cryptographic Freeze**:
   - Implement the Deep Module seam (`src/modules/<domain>/index.py`), calibrate strictly on a disjoint dev split, then commit `FREEZE*.md` (SHA-256 hashes) and `experiments/{v}/PROTOCOL*.md` **before** any confirmatory run.
5. **Gate 4 — Autonomous GSD Build & Single Frozen Confirmatory Run**:
   - Run seam TDD (`tests/`), execute live native engines (zero mocks/formulas), write raw per-query JSONL (`results/{v}/raw/*.jsonl`), and recompute `results/{v}/summary.json` deterministically via `bench/recompute*.py --check`.
6. **Gate 5 — Academic Plotting & Manuscript Compilation**:
   - Render 300-DPI vector PDF/PNG figures strictly from `summary.json`, author `paper/*.tex` with a complete `DEVIATIONS.md` + Protocol Deviations table, and compile the PDF + arXiv `.tar.gz`.
7. **Gate 6 — Fresh Independent `pro` Review & 3-Brake SHA-256 Sign-Off**:
   - Launch a brand-new `pro` reviewer subagent (zero prior builder context) to trace raw JSONL provenance, audit timing/RAM fairness, visually inspect every PNG figure, read the compiled PDF, write runtime `results/{v}/review/{figure_review,peer_review,REVIEW_SUMMARY}.md` bound to exact SHA-256 hashes (Brakes 1–3), run Software Factory Node sensors, and log sensor learnings via `retro`.
