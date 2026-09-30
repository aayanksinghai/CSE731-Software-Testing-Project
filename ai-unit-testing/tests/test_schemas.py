"""
tests/test_schemas.py
Unit tests for the data models in models/schemas.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from models.schemas import (
    CoverageResult,
    DatasetName,
    ExecutionResult,
    GeneratedCode,
    GeneratedTests,
    PipelineResult,
    Problem,
    Verdict,
    CoverageTarget,
)


class TestProblem:
    def test_to_dict_contains_required_fields(self):
        p = Problem(
            problem_id="test_1",
            prompt="Write a function",
            entry_point="my_func",
            canonical_solution="def my_func(): pass",
            dataset=DatasetName.MBPP,
        )
        d = p.to_dict()
        assert d["problem_id"] == "test_1"
        assert d["entry_point"] == "my_func"
        assert d["dataset"] == "MBPP"

    def test_raw_defaults_to_empty_dict(self):
        p = Problem("id", "prompt", "fn", None, DatasetName.HUMANEVAL)
        assert p.raw == {}


class TestGeneratedCode:
    def test_valid_flag_default_false(self):
        gc = GeneratedCode("p1", "def f(): pass", "f")
        assert gc.is_valid is False

    def test_to_dict_keys(self):
        gc = GeneratedCode("p1", "def f(): pass", "f", is_valid=True)
        d = gc.to_dict()
        assert "problem_id" in d
        assert "function_name" in d
        assert "is_valid" in d


class TestCoverageResult:
    def test_supported_false(self):
        cr = CoverageResult(supported=False, branch_coverage_pct=None,
                            total_branches=None, covered_branches=None)
        assert cr.supported is False

    def test_to_dict(self):
        cr = CoverageResult(supported=True, branch_coverage_pct=80.0,
                            total_branches=10, covered_branches=8,
                            missing_branches=["line 5 -> line 8"])
        d = cr.to_dict()
        assert d["branch_coverage_pct"] == 80.0
        assert len(d["missing_branches"]) == 1


class TestPipelineResult:
    def test_default_verdict_pending(self):
        r = PipelineResult("p1", "MBPP", "decision_coverage", 100.0)
        assert r.verdict == Verdict.PENDING

    def test_to_dict_verdict_is_string(self):
        r = PipelineResult("p1", "MBPP", "decision_coverage", 100.0)
        r.verdict = Verdict.PASS
        d = r.to_dict()
        assert d["verdict"] == "PASS"
        assert isinstance(d["verdict"], str)

    def test_to_dict_all_required_keys(self):
        r = PipelineResult("p1", "MBPP", "decision_coverage", 100.0)
        d = r.to_dict()
        for key in ("problem_id", "dataset", "testing_goal", "target_coverage",
                    "verdict", "iterations", "branch_coverage"):
            assert key in d, f"Missing key: {key}"
