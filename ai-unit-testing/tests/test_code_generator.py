"""
tests/test_code_generator.py
Unit tests for the Code Generator Agent (parsing/validation logic).
No real LLM calls are made.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from agents.code_generator import CodeGeneratorAgent, _validate_python
from models.schemas import DatasetName, Problem


def _make_problem(entry="my_func"):
    return Problem(
        problem_id="test_p1",
        prompt="Write a function",
        entry_point=entry,
        canonical_solution=None,
        dataset=DatasetName.MOCK,
    )


class TestValidatePython:
    def test_valid_code(self):
        ok, err = _validate_python("def f(x):\n    return x + 1\n")
        assert ok is True
        assert err == ""

    def test_invalid_syntax(self):
        ok, err = _validate_python("def f(\n    return x\n")
        assert ok is False
        assert err != ""

    def test_empty_string_is_valid(self):
        ok, _ = _validate_python("")
        assert ok is True


class TestCodeGeneratorMock:
    def test_mock_returns_valid_code(self):
        p = _make_problem()
        gc = CodeGeneratorAgent.mock_generate(p)
        assert gc.is_valid is True
        assert p.entry_point in gc.code
        assert gc.problem_id == p.problem_id

    def test_mock_code_contains_branches(self):
        p = _make_problem("check_val")
        gc = CodeGeneratorAgent.mock_generate(p)
        # Mock code should have if/elif/else
        assert "if " in gc.code
        assert "elif " in gc.code or "else:" in gc.code

    def test_mock_function_name_matches(self):
        p = _make_problem("my_special_fn")
        gc = CodeGeneratorAgent.mock_generate(p)
        assert gc.function_name == "my_special_fn"


class TestParseResponse:
    """Test _parse_response via duck-typed partial agent."""

    def _agent_with_mock_client(self):
        # Build agent without a real client (won't be called)
        class FakeClient:
            model = "mock"
            temperature = 0.0
            max_tokens = 100
        agent = object.__new__(CodeGeneratorAgent)
        # Load the template
        agent._client = FakeClient()
        from pathlib import Path
        agent._template = (
            Path(__file__).parent.parent / "prompts" / "code_generator.txt"
        ).read_text(encoding="utf-8")
        return agent

    def test_valid_json_response(self):
        agent = self._agent_with_mock_client()
        p = _make_problem("sum_evens")
        raw = '{"function_name": "sum_evens", "code": "def sum_evens(n):\\n    return sum(i for i in range(n) if i % 2 == 0)\\n"}'
        gc = agent._parse_response(p, raw)
        assert gc.is_valid is True
        assert gc.function_name == "sum_evens"

    def test_malformed_json_returns_invalid(self):
        agent = self._agent_with_mock_client()
        p = _make_problem()
        raw = "This is not JSON"
        gc = agent._parse_response(p, raw)
        assert gc.is_valid is False
        assert gc.parse_error is not None

    def test_empty_code_field_returns_invalid(self):
        agent = self._agent_with_mock_client()
        p = _make_problem()
        raw = '{"function_name": "f", "code": ""}'
        gc = agent._parse_response(p, raw)
        assert gc.is_valid is False
