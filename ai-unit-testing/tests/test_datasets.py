"""
tests/test_datasets.py
Unit tests for dataset normalization and the control-flow heuristic.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from datasources.base import BaseDataset
from datasources.mbpp import MBPPDataset, _extract_entry_point
from models.schemas import DatasetName


class TestControlFlowHeuristic:
    """Tests for BaseDataset.has_meaningful_control_flow"""

    def test_simple_function_no_branches(self):
        code = "def add(a, b):\n    return a + b\n"
        assert BaseDataset.has_meaningful_control_flow(code) is False

    def test_function_with_if_else(self):
        code = "def f(x):\n    if x > 0:\n        return x\n    else:\n        return -x\n"
        assert BaseDataset.has_meaningful_control_flow(code) is True

    def test_function_with_loop_and_condition(self):
        code = (
            "def count_evens(lst):\n"
            "    count = 0\n"
            "    for x in lst:\n"
            "        if x % 2 == 0:\n"
            "            count += 1\n"
            "    return count\n"
        )
        assert BaseDataset.has_meaningful_control_flow(code) is True

    def test_none_solution(self):
        assert BaseDataset.has_meaningful_control_flow(None) is False

    def test_empty_string(self):
        assert BaseDataset.has_meaningful_control_flow("") is False

    def test_try_except_counted(self):
        code = "def safe_div(a, b):\n    try:\n        return a / b\n    except ZeroDivisionError:\n        return None\n"
        assert BaseDataset.has_meaningful_control_flow(code) is True


class TestExtractEntryPoint:
    def test_simple_function(self):
        code = "def my_function(x, y):\n    return x + y"
        assert _extract_entry_point(code) == "my_function"

    def test_first_of_multiple_functions(self):
        code = "def first():\n    pass\n\ndef second():\n    pass"
        assert _extract_entry_point(code) == "first"

    def test_no_function(self):
        assert _extract_entry_point("x = 1") == "solution"

    def test_function_with_leading_whitespace_in_code(self):
        code = "# comment\ndef helper(n):\n    return n"
        assert _extract_entry_point(code) == "helper"


class TestMBPPDatasetNormalisation:
    """Test that MBPP records are correctly normalised without hitting the network."""

    def test_ingest_record_normalises_schema(self):
        ds = MBPPDataset()
        record = {
            "task_id": 999,
            "text": "Write a function to find the maximum of two numbers.",
            "code": "def max_of_two(a, b):\n    if a > b:\n        return a\n    else:\n        return b\n",
            "test_list": [],
        }
        ds._ingest_record(record)
        problem = ds.get_problem("mbpp_999")
        assert problem is not None
        assert problem.problem_id == "mbpp_999"
        assert problem.entry_point == "max_of_two"
        assert problem.dataset == DatasetName.MBPP
        assert "maximum" in problem.prompt.lower()

    def test_missing_task_id_uses_zero(self):
        ds = MBPPDataset()
        ds._ingest_record({"text": "test", "code": "def f(): pass"})
        assert ds.get_problem("mbpp_0") is not None

    def test_list_ids_sorted(self):
        ds = MBPPDataset()
        ds._ingest_record({"task_id": 20, "text": "t", "code": "def z(): pass"})
        ds._ingest_record({"task_id": 5, "text": "t", "code": "def a(): pass"})
        ids = ds.list_ids()
        assert ids == sorted(ids)
