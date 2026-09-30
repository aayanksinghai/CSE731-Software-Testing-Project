"""
tests/test_runner.py
Unit tests for execution/runner.py — coverage JSON parsing.
No subprocess calls are made.
"""

import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from execution.runner import _parse_coverage_json, _parse_pytest_json, parse_sandbox_output


def _write_coverage_json(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "coverage.json"
    p.write_text(json.dumps(data))
    return p


def _write_pytest_json(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "report.json"
    p.write_text(json.dumps(data))
    return p


class TestParseCoverageJson:
    def test_valid_coverage_json(self, tmp_path):
        data = {
            "totals": {
                "covered_branches": 8,
                "num_branches": 10,
            },
            "files": {}
        }
        p = _write_coverage_json(tmp_path, data)
        result = _parse_coverage_json(p)
        assert result.supported is True
        assert result.branch_coverage_pct == 80.0
        assert result.total_branches == 10
        assert result.covered_branches == 8

    def test_100_percent_coverage(self, tmp_path):
        data = {"totals": {"covered_branches": 4, "num_branches": 4}, "files": {}}
        p = _write_coverage_json(tmp_path, data)
        result = _parse_coverage_json(p)
        assert result.branch_coverage_pct == 100.0

    def test_zero_branches_returns_100_pct(self, tmp_path):
        data = {"totals": {"covered_branches": 0, "num_branches": 0}, "files": {}}
        p = _write_coverage_json(tmp_path, data)
        result = _parse_coverage_json(p)
        assert result.branch_coverage_pct == 100.0

    def test_missing_branch_keys_unsupported(self, tmp_path):
        data = {"totals": {"percent_covered": 90.0}, "files": {}}
        p = _write_coverage_json(tmp_path, data)
        result = _parse_coverage_json(p)
        assert result.supported is False

    def test_none_path_returns_unsupported(self):
        result = _parse_coverage_json(None)
        assert result.supported is False

    def test_nonexistent_file_returns_unsupported(self, tmp_path):
        result = _parse_coverage_json(tmp_path / "missing.json")
        assert result.supported is False

    def test_malformed_json_returns_unsupported(self, tmp_path):
        p = tmp_path / "coverage.json"
        p.write_text("{broken json")
        result = _parse_coverage_json(p)
        assert result.supported is False

    def test_missing_branches_collected(self, tmp_path):
        data = {
            "totals": {"covered_branches": 3, "num_branches": 4},
            "files": {
                "generated_code.py": {
                    "missing_branches": [[10, 15], [20, 25]]
                }
            }
        }
        p = _write_coverage_json(tmp_path, data)
        result = _parse_coverage_json(p)
        assert len(result.missing_branches) == 2


class TestParseSandboxOutput:
    def test_builds_execution_result(self, tmp_path):
        pytest_data = {
            "summary": {
                "collected": 3,
                "passed": 3,
                "failed": 0,
                "error": 0,
            }
        }
        cov_data = {
            "totals": {"covered_branches": 4, "num_branches": 4},
            "files": {}
        }
        pytest_path = _write_pytest_json(tmp_path, pytest_data)
        cov_path = _write_coverage_json(tmp_path, cov_data)

        sandbox_result = {
            "returncode": 0,
            "stdout": "3 passed",
            "stderr": "",
            "elapsed_s": 1.2,
            "timed_out": False,
            "pytest_json_path": pytest_path,
            "coverage_json_path": cov_path,
        }
        result = parse_sandbox_output("p1", sandbox_result)
        assert result.tests_passed == 3
        assert result.tests_failed == 0
        assert result.coverage.branch_coverage_pct == 100.0
        assert result.timed_out is False

    def test_timeout_flag_propagated(self, tmp_path):
        sandbox_result = {
            "returncode": -1,
            "stdout": "",
            "stderr": "",
            "elapsed_s": 30.0,
            "timed_out": True,
            "pytest_json_path": None,
            "coverage_json_path": None,
        }
        result = parse_sandbox_output("p2", sandbox_result)
        assert result.timed_out is True
        assert "timed out" in (result.error_message or "").lower()
