"""
tests/test_verdict.py
Unit tests for evaluation/verdict.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from models.schemas import CoverageResult, ExecutionResult, Verdict
from evaluation.verdict import calculate_verdict, build_coverage_feedback


def _make_exec(
    passed=1,
    failed=0,
    error=0,
    timed_out=False,
    coverage_supported=True,
    coverage_pct=100.0,
    total_branches=4,
    covered_branches=4,
    missing_branches=None,
):
    cov = CoverageResult(
        supported=coverage_supported,
        branch_coverage_pct=coverage_pct,
        total_branches=total_branches,
        covered_branches=covered_branches,
        missing_branches=missing_branches or [],
    )
    return ExecutionResult(
        problem_id="test",
        returncode=0 if not failed and not error else 1,
        stdout="",
        stderr="",
        tests_collected=passed + failed + error,
        tests_passed=passed,
        tests_failed=failed,
        tests_error=error,
        timed_out=timed_out,
        execution_time_s=0.5,
        coverage=cov,
    )


class TestCalculateVerdict:
    def test_pass_when_all_conditions_met(self):
        exec_r = _make_exec(passed=3, coverage_pct=100.0)
        assert calculate_verdict(exec_r, target_pct=100.0) == Verdict.PASS

    def test_target_not_met_below_threshold(self):
        exec_r = _make_exec(passed=3, coverage_pct=75.0)
        assert calculate_verdict(exec_r, target_pct=100.0) == Verdict.TARGET_NOT_MET

    def test_target_met_at_exact_threshold(self):
        exec_r = _make_exec(passed=2, coverage_pct=80.0)
        assert calculate_verdict(exec_r, target_pct=80.0) == Verdict.PASS

    def test_test_failure_takes_priority_over_coverage(self):
        exec_r = _make_exec(passed=2, failed=1, coverage_pct=100.0)
        assert calculate_verdict(exec_r) == Verdict.TEST_FAILURE

    def test_execution_error_on_timeout(self):
        exec_r = _make_exec(timed_out=True, coverage_pct=0.0)
        assert calculate_verdict(exec_r) == Verdict.EXECUTION_ERROR

    def test_execution_error_on_test_error(self):
        exec_r = _make_exec(error=1)
        assert calculate_verdict(exec_r) == Verdict.EXECUTION_ERROR

    def test_coverage_unsupported(self):
        exec_r = _make_exec(coverage_supported=False, coverage_pct=None)
        assert calculate_verdict(exec_r) == Verdict.COVERAGE_UNSUPPORTED

    def test_no_coverage_object(self):
        exec_r = _make_exec()
        exec_r.coverage = None
        assert calculate_verdict(exec_r) == Verdict.EXECUTION_ERROR

    def test_custom_target_90_pct(self):
        exec_r = _make_exec(coverage_pct=95.0)
        assert calculate_verdict(exec_r, target_pct=90.0) == Verdict.PASS


class TestBuildCoverageFeedback:
    def test_includes_percentage(self):
        exec_r = _make_exec(
            passed=2, failed=1,
            coverage_pct=75.0, total_branches=4, covered_branches=3,
            missing_branches=["line 10 -> line 15"],
        )
        feedback = build_coverage_feedback(exec_r)
        assert "75.0%" in feedback
        assert "line 10 -> line 15" in feedback

    def test_unsupported_coverage(self):
        exec_r = _make_exec(coverage_supported=False, coverage_pct=None)
        feedback = build_coverage_feedback(exec_r)
        assert "not available" in feedback.lower()

    def test_no_missing_branches(self):
        exec_r = _make_exec(coverage_pct=80.0, missing_branches=[])
        feedback = build_coverage_feedback(exec_r)
        assert "No specific missing" in feedback
