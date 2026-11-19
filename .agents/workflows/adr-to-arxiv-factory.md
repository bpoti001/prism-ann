---
description: ADR-to-arXiv Research & Software Factory workflow combining ADR governance, Deep Module TDD, Two-Loop Autoresearch, academic-plotting, PaperVizAgent, ScholarPeer, and systems/ML paper writing.
---

# `/adr-to-arxiv-factory` Workflow

Follow the unified 6-Gate workflow defined in `/Users/tejap/.gemini/config/skills/adr-to-arxiv-factory/SKILL.md` and orchestrated via `python3 research_factory.py`:

1. **Step 1 — Check T-Shirt Size (`[S]` | `[M]` | `[L]`)**:
   - Run `python3 research_factory.py size "<task description>"` or check explicit `[S]`, `[M]`, `[L]` override.
   - If `[S]` (typo, plot style, constant tweak): apply surgical edit and run `python3 research_factory.py verify-governance`.
2. **Step 2 — Gate 1 & Gate 2 (Literature Recon, `GLOSSARY.md`, & ADR-to-Theorem Mapping)**:
   - For `[L]` tasks, update `literature/survey.md` and `GLOSSARY.md`, mint an ADR in `docs/adr/NNNN-*.md` using **Design-It-Twice** (mapping the architectural trade-off directly to a formal theorem and baseline comparison), and register it in `CONTEXT.md`.
3. **Step 3 — Gate 3 (`/show-me` Seam Design & Pre-Registered Protocol)**:
   - Design the Deep Module public seam (`src/modules/<domain>/index.py`) and lock `experiments/<H-slug>/protocol.md` before running benchmarks.
4. **Step 4 — Gate 4 (Tracer-Bullet Seam TDD & Inner-Loop Execution)**:
   - Write seam unit/property tests first (`tests/`), implement the module, run benchmark comparisons against `baselines/`, and save metrics to `results/*.json`.
5. **Step 5 — Gate 5 (Outer-Loop Synthesis & `PaperVizAgent` Plots)**:
   - Update `findings.md` and `research-state.yaml`, generate vector PDF plots from `results/*.json`, and verify figure quality via `PaperVizAgent`.
6. **Step 6 — Gate 6 (3-Brake Audit & arXiv Packaging)**:
   - Run `python3 research_factory.py audit-paper` (executing `verify-governance`, `verify_hallucinations.py`, `PaperVizAgent`, and `ScholarPeer`) and compile `paper/main.tex` into a submission-ready PDF and arXiv `.tar.gz` bundle.
