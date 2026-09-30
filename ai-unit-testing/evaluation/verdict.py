"""
evaluation/verdict.py
Calculates the final PASS/FAIL verdict from an ExecutionResult.

The verdict is always based on measured execution results.
The LLM's claimed coverage is never used here.
"""

from __future__ import annotations

import logging
from typing import Optional

from models.schemas import ExecutionResult, Verdict

logger = logging.getLogger(__name__)


def calculate_verdict(
    execution: ExecutionResult,
    target_pct: float = 100.0,
) -> Verdict:
    """
    Determine the pipeline verdict from an ExecutionResult.

    Decision tree
    ─────────────
    1.  Timeout             → EXECUTION_ERROR
    2.  Tests errored       → EXECUTION_ERROR
    3.  Tests failed        → TEST_FAILURE
    4.  No coverage object  → EXECUTION_ERROR
    5.  Coverage unsupported→ COVERAGE_UNSUPPORTED
    6.  Coverage < target   → TARGET_NOT_MET
    7.  Coverage >= target  → PASS
    """
    if execution.timed_out:
        logger.debug("[%s] Verdict: EXECUTION_ERROR (timeout)", execution.problem_id)
        return Verdict.EXECUTION_ERROR

    if execution.tests_error > 0:
        logger.debug("[%s] Verdict: EXECUTION_ERROR (%d errors)", execution.problem_id, execution.tests_error)
        return Verdict.EXECUTION_ERROR

    if execution.tests_failed > 0:
        logger.debug("[%s] Verdict: TEST_FAILURE (%d failed)", execution.problem_id, execution.tests_failed)
        return Verdict.TEST_FAILURE

    if execution.coverage is None:
        logger.debug("[%s] Verdict: EXECUTION_ERROR (no coverage result)", execution.problem_id)
        return Verdict.EXECUTION_ERROR

    if not execution.coverage.supported:
        logger.debug("[%s] Verdict: COVERAGE_UNSUPPORTED", execution.problem_id)
        return Verdict.COVERAGE_UNSUPPORTED

    achieved = execution.coverage.branch_coverage_pct or 0.0
    if achieved < target_pct:
        logger.debug(
            "[%s] Verdict: TARGET_NOT_MET (%.1f%% < %.1f%%)",
            execution.problem_id, achieved, target_pct,
        )
        return Verdict.TARGET_NOT_MET

    logger.debug("[%s] Verdict: PASS (%.1f%%)", execution.problem_id, achieved)
    return Verdict.PASS


def build_coverage_feedback(execution: ExecutionResult) -> str:
    """
    Build a structured human-readable feedback string to send back to the
    Test Generator Agent when coverage is insufficient.
    """
    cov = execution.coverage
    if cov is None or not cov.supported:
        return (
            "Coverage measurement was not available. "
            "Ensure your tests actually import and call the function under test."
        )

    lines = [
        f"Previous test run achieved {cov.branch_coverage_pct:.1f}% branch coverage "
        f"({cov.covered_branches}/{cov.total_branches} branches covered).",
    ]
    if cov.missing_branches:
        lines.append("Missing branches (not yet covered):")
        for b in cov.missing_branches[:20]:  # cap at 20 to keep prompt size reasonable
            lines.append(f"  - {b}")
    else:
        lines.append("No specific missing branch information available.")

    if execution.tests_failed:
        lines.append(f"Additionally, {execution.tests_failed} test(s) failed.")
        lines.append("Fix any failing tests before adding new ones.")

    lines.append(
        "\nPlease generate an improved test suite that covers the missing branches listed above."
    )
    return "\n".join(lines)
