"""
execution/runner.py
Parses raw sandbox output into structured ExecutionResult and CoverageResult.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from models.schemas import CoverageResult, ExecutionResult

logger = logging.getLogger(__name__)


def _parse_pytest_json(report_path: Optional[Path]) -> dict:
    """Parse the pytest-json-report output file."""
    if not report_path or not report_path.exists():
        return {}
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not parse pytest JSON report: %s", exc)
        return {}


def _parse_coverage_json(cov_path: Optional[Path]) -> Optional[CoverageResult]:
    """
    Parse coverage.json produced by `coverage json`.
    Returns None if the file is missing or malformed.
    """
    if not cov_path or not cov_path.exists():
        return CoverageResult(
            supported=False,
            branch_coverage_pct=None,
            total_branches=None,
            covered_branches=None,
            missing_branches=[],
        )

    try:
        with open(cov_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not parse coverage.json: %s", exc)
        return CoverageResult(
            supported=False,
            branch_coverage_pct=None,
            total_branches=None,
            covered_branches=None,
            missing_branches=[],
        )

    # coverage.py JSON structure: {"totals": {...}, "files": {...}}
    totals = data.get("totals", {})
    covered = totals.get("covered_branches", None)
    total = totals.get("num_branches", None)

    if total is None or covered is None:
        # Branch coverage data unavailable (e.g. coverage run without --branch)
        return CoverageResult(
            supported=False,
            branch_coverage_pct=None,
            total_branches=None,
            covered_branches=None,
            missing_branches=[],
        )

    pct = round((covered / total * 100), 2) if total > 0 else 100.0

    # Collect missing branch descriptions from per-file data
    missing_branches: list[str] = []
    for file_name, file_data in data.get("files", {}).items():
        if "generated_tests" in file_name:
            continue  # skip the test file itself
        for branch in file_data.get("missing_branches", []):
            missing_branches.append(f"{file_name}: {branch}")

    return CoverageResult(
        supported=True,
        branch_coverage_pct=pct,
        total_branches=total,
        covered_branches=covered,
        missing_branches=missing_branches,
        raw_json=data,
    )


def parse_sandbox_output(problem_id: str, sandbox_result: dict) -> ExecutionResult:
    """
    Convert the raw dict returned by SandboxRunner.execute() into a
    fully structured ExecutionResult.
    """
    report = _parse_pytest_json(sandbox_result.get("pytest_json_path"))
    coverage = _parse_coverage_json(sandbox_result.get("coverage_json_path"))

    # Extract test counts from the pytest JSON report
    summary = report.get("summary", {})
    collected = summary.get("collected", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    error = summary.get("error", 0)

    # If pytest JSON report is missing, fall back to returncode heuristic
    if not report:
        rc = sandbox_result.get("returncode", -1)
        if rc == 0:
            passed = 1   # at least something ran
        else:
            failed = 1

    timed_out = sandbox_result.get("timed_out", False)
    error_message: Optional[str] = None
    if timed_out:
        error_message = "Subprocess timed out."
    elif sandbox_result.get("returncode", 0) == -2:
        error_message = "Subprocess launch failed: " + sandbox_result.get("stderr", "")

    return ExecutionResult(
        problem_id=problem_id,
        returncode=sandbox_result.get("returncode"),
        stdout=sandbox_result.get("stdout", ""),
        stderr=sandbox_result.get("stderr", ""),
        tests_collected=collected,
        tests_passed=passed,
        tests_failed=failed,
        tests_error=error,
        timed_out=timed_out,
        execution_time_s=sandbox_result.get("elapsed_s", 0.0),
        coverage=coverage,
        error_message=error_message,
    )
