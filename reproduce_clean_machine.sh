#!/usr/bin/env bash
# ==============================================================================
# Prism-ANN Clean-Machine Independent Reproduction & Verification Runner
# ==============================================================================
# Usage:
#   ./reproduce_clean_machine.sh --verify
#       Runs all fast deterministic verification gates (~15s, no external DB
#       daemons required):
#         1. FREEZE.md (5/5), FREEZE_v3.md (7/7), FREEZE_v3_1.md (8/8), FREEZE_v3_3.md (9/9) SHA-256
#         2. Bit-for-bit raw JSONL recomputation across all 5 campaigns:
#              - v2-confirmatory-002   ( 62,410 raw records)
#              - v3-confirmatory-001   (169,810 raw records)
#              - v3.1-reviewer-audit   ( 22,533 raw records)
#              - v3.2-reviewer-audit   (  6,821 raw records)
#              - v3.3-reviewer-audit   (  8,521 raw records)
#         3. 376-scenario Blast-Radius live UBP fuzzer (0 FP, 0 FN)
#         4. Full pytest suite (unit, C++ NEON kernel parity, provenance,
#            Theorem 2 dynamic multi-parent diamond DAG & ZedToken snapshot tests)
#         5. 3-Brake Academic & Governance Audit
#
#   ./reproduce_clean_machine.sh --rerun-audits
#       Compiles the C++17 / ARM NEON kernels from source, re-executes the
#       standalone reviewer audits (R1-R11) on the clean machine, and verifies
#       deterministic recomputation.
# ==============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

# Locate Python interpreter (.venv-bench in parent or local dir, else python3)
if [[ -x "$REPO_DIR/.venv-bench/bin/python" ]]; then
    PY="$REPO_DIR/.venv-bench/bin/python"
    PYTEST="$REPO_DIR/.venv-bench/bin/pytest"
elif [[ -x "$REPO_DIR/../.venv-bench/bin/python" ]]; then
    PY="$REPO_DIR/../.venv-bench/bin/python"
    PYTEST="$REPO_DIR/../.venv-bench/bin/pytest"
else
    PY="$(command -v python3)"
    PYTEST="$PY -m pytest"
fi

MODE="${1:---verify}"

echo "=================================================================="
echo "  Prism-ANN Clean-Machine Reproduction Suite (mode: $MODE)"
echo "  Working Directory: $REPO_DIR"
echo "  Python Interpreter: $PY"
echo "=================================================================="

# Ensure C++17 shared libraries exist (compile if missing on a fresh clone)
mkdir -p bench/_build
if [[ ! -f "bench/_build/libprism_ckernel.dylib" && ! -f "bench/_build/libprism_ckernel.so" ]]; then
    echo ">>> Compiling bench/prism_ckernel.cpp..."
    c++ -O3 -std=c++17 -shared -fPIC bench/prism_ckernel.cpp -o bench/_build/libprism_ckernel.dylib
fi
if [[ ! -f "bench/_build/libprism_audit_kernel.dylib" && ! -f "bench/_build/libprism_audit_kernel.so" ]]; then
    echo ">>> Compiling bench/prism_audit_kernel.cpp..."
    c++ -O3 -std=c++17 -shared -fPIC bench/prism_audit_kernel.cpp -o bench/_build/libprism_audit_kernel.dylib
fi

echo ""
echo ">>> [1/4] Running Full Pytest Suite (Unit, C++ Kernel Parity, Theorem 2 & Provenance)..."
$PYTEST -q

echo ""
echo ">>> [2/4] Verifying GSD Roadmap (22/22 Phases = 100%) & ADR-0000..0006 Governance..."
$PY research_factory.py verify-governance

echo ""
echo ">>> [3/4] Running Deterministic Raw-Record Recomputers & 3-Brake Academic Audit..."
$PY research_factory.py audit-paper

if [[ "$MODE" == "--rerun-audits" ]]; then
    echo ""
    echo ">>> [4/4] Re-Executing Standalone Reviewer Audits (v3.1 R1-R5, v3.2 R6-R8, & v3.3 R9-R11)..."
    $PY -m bench.run_reviewer_audit_v3_1
    $PY -m bench.recompute_v3_1 --check results/v3/reviewer_audit_v3_1.json
    $PY -m bench.run_reviewer_audit_v3_2
    $PY -m bench.recompute_v3_2 --check results/v3/reviewer_audit_v3_2.json
    $PY -m bench.run_reviewer_audit_v3_3
    $PY -m bench.recompute_v3_3 --check results/v3/reviewer_audit_v3_3.json
else
    echo ""
    echo ">>> [4/4] Verification complete (pass --rerun-audits to re-execute R1-R11 benchmark runs)."
fi

echo ""
echo "=================================================================="
echo "  Prism-ANN Clean-Machine Reproduction: ALL GATES PASSED (EXIT 0)"
echo "=================================================================="
