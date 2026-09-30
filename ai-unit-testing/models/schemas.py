"""
models/schemas.py
Unified internal data model for the AI-Assisted Unit Testing pipeline.
All agents and components share these types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Verdict(str, Enum):
    PASS = "PASS"
    TARGET_NOT_MET = "TARGET_NOT_MET"
    TEST_FAILURE = "TEST_FAILURE"
    CODE_GENERATION_FAILURE = "CODE_GENERATION_FAILURE"
    TEST_GENERATION_FAILURE = "TEST_GENERATION_FAILURE"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    COVERAGE_UNSUPPORTED = "COVERAGE_UNSUPPORTED"
    PENDING = "PENDING"


class DatasetName(str, Enum):
    HUMANEVAL = "HumanEval"
    MBPP = "MBPP"
    MOCK = "MOCK"


# ---------------------------------------------------------------------------
# Dataset layer
# ---------------------------------------------------------------------------

@dataclass
class Problem:
    """
    Normalised representation of a benchmark problem.
    Both HumanEval and MBPP are converted to this schema.
    """
    problem_id: str
    prompt: str                          # Problem description / docstring
    entry_point: str                     # Function name expected
    canonical_solution: Optional[str]    # Reference solution (may be None)
    dataset: DatasetName
    raw: Dict[str, Any] = field(default_factory=dict)   # Original record

    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "prompt": self.prompt,
            "entry_point": self.entry_point,
            "canonical_solution": self.canonical_solution,
            "dataset": self.dataset.value,
        }


# ---------------------------------------------------------------------------
# Agent outputs
# ---------------------------------------------------------------------------

@dataclass
class GeneratedCode:
    """Output contract of the Code Generator Agent."""
    problem_id: str
    code: str                        # Raw Python source
    function_name: str               # Extracted function name
    is_valid: bool = False           # Set after syntax validation
    parse_error: Optional[str] = None
    raw_response: Optional[str] = None   # Full LLM response

    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "function_name": self.function_name,
            "is_valid": self.is_valid,
            "parse_error": self.parse_error,
        }


@dataclass
class CoverageTarget:
    """Machine-readable metadata from the Test Generator Agent."""
    criterion: str                       # e.g. "decision_coverage"
    target_percentage: float             # e.g. 100.0
    intended_branches: List[str] = field(default_factory=list)
    edge_cases: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criterion": self.criterion,
            "target_percentage": self.target_percentage,
            "intended_branches": self.intended_branches,
            "edge_cases": self.edge_cases,
        }


@dataclass
class GeneratedTests:
    """Output contract of the Test Case Generator Agent."""
    problem_id: str
    test_code: str                       # Executable pytest source
    coverage_target: Optional[CoverageTarget]
    iteration: int = 1                   # Which feedback iteration
    is_valid: bool = False
    parse_error: Optional[str] = None
    raw_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "iteration": self.iteration,
            "is_valid": self.is_valid,
            "parse_error": self.parse_error,
            "coverage_target": self.coverage_target.to_dict() if self.coverage_target else None,
        }


# ---------------------------------------------------------------------------
# Execution / Coverage results
# ---------------------------------------------------------------------------

@dataclass
class CoverageResult:
    """Branch coverage data collected from coverage.py."""
    supported: bool                          # False → COVERAGE_UNSUPPORTED
    branch_coverage_pct: Optional[float]     # 0–100
    total_branches: Optional[int]
    covered_branches: Optional[int]
    missing_branches: List[str] = field(default_factory=list)
    raw_json: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "supported": self.supported,
            "branch_coverage_pct": self.branch_coverage_pct,
            "total_branches": self.total_branches,
            "covered_branches": self.covered_branches,
            "missing_branches": self.missing_branches,
        }


@dataclass
class ExecutionResult:
    """Full output of the Test Case Executor Agent."""
    problem_id: str
    returncode: Optional[int]
    stdout: str
    stderr: str
    tests_collected: int
    tests_passed: int
    tests_failed: int
    tests_error: int
    timed_out: bool
    execution_time_s: float
    coverage: Optional[CoverageResult]
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "returncode": self.returncode,
            "tests_collected": self.tests_collected,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "tests_error": self.tests_error,
            "timed_out": self.timed_out,
            "execution_time_s": round(self.execution_time_s, 3),
            "coverage": self.coverage.to_dict() if self.coverage else None,
            "error_message": self.error_message,
        }


# ---------------------------------------------------------------------------
# Final pipeline result
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """One complete run of the pipeline for a single problem."""
    problem_id: str
    dataset: str
    testing_goal: str
    target_coverage: float

    # Iteration tracking
    iterations: int = 0

    # From generated code
    generated_code: Optional[str] = None
    code_valid: bool = False

    # From generated tests (last iteration)
    generated_tests: Optional[str] = None
    tests_valid: bool = False
    tests_generated: int = 0

    # From execution
    tests_passed: int = 0
    tests_failed: int = 0
    branch_coverage: Optional[float] = None
    total_branches: Optional[int] = None
    covered_branches: Optional[int] = None
    missing_branches: List[str] = field(default_factory=list)

    # Timing
    execution_time_s: float = 0.0
    total_time_s: float = 0.0

    # Final answer
    verdict: Verdict = Verdict.PENDING
    error_detail: Optional[str] = None

    # Model info for reproducibility
    model: Optional[str] = None
    provider_url: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "dataset": self.dataset,
            "testing_goal": self.testing_goal,
            "target_coverage": self.target_coverage,
            "iterations": self.iterations,
            "code_valid": self.code_valid,
            "tests_valid": self.tests_valid,
            "tests_generated": self.tests_generated,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "branch_coverage": self.branch_coverage,
            "total_branches": self.total_branches,
            "covered_branches": self.covered_branches,
            "missing_branches": self.missing_branches,
            "execution_time_s": round(self.execution_time_s, 3),
            "total_time_s": round(self.total_time_s, 3),
            "verdict": self.verdict.value,
            "error_detail": self.error_detail,
            "model": self.model,
            "provider_url": self.provider_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timestamp": self.timestamp,
        }


@dataclass
class ExperimentSummary:
    """Aggregate summary across all problems in an experiment."""
    timestamp: str
    dataset: str
    total_problems: int = 0
    attempted: int = 0
    passed: int = 0
    target_not_met: int = 0
    test_failures: int = 0
    code_gen_failures: int = 0
    test_gen_failures: int = 0
    execution_errors: int = 0
    coverage_unsupported: int = 0
    avg_branch_coverage: Optional[float] = None
    median_branch_coverage: Optional[float] = None
    avg_tests_generated: Optional[float] = None
    avg_feedback_iterations: Optional[float] = None
    avg_execution_time_s: Optional[float] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    target_coverage: float = 100.0
    problem_results: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "dataset": self.dataset,
            "model": self.model,
            "temperature": self.temperature,
            "target_coverage": self.target_coverage,
            "total_problems": self.total_problems,
            "attempted": self.attempted,
            "passed": self.passed,
            "target_not_met": self.target_not_met,
            "test_failures": self.test_failures,
            "code_gen_failures": self.code_gen_failures,
            "test_gen_failures": self.test_gen_failures,
            "execution_errors": self.execution_errors,
            "coverage_unsupported": self.coverage_unsupported,
            "avg_branch_coverage": self.avg_branch_coverage,
            "median_branch_coverage": self.median_branch_coverage,
            "avg_tests_generated": self.avg_tests_generated,
            "avg_feedback_iterations": self.avg_feedback_iterations,
            "avg_execution_time_s": self.avg_execution_time_s,
            "problem_results": self.problem_results,
        }
