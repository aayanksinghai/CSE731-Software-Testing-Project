"""
agents/test_generator.py
Agent 2 — Test Case Generator Agent

Responsibility:
  Receive generated implementation code plus the testing goal
  (decision/branch coverage) and produce an executable pytest test suite.
  On subsequent iterations, receive coverage feedback and refine the suite.

Input:   GeneratedCode + testing goal + optional coverage feedback string
Output:  GeneratedTests (test_code, coverage_target, iteration)

The agent's claimed coverage in coverage_metadata is advisory only.
Actual coverage is always measured by the Executor Agent.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Optional

from agents.llm_client import LLMClient, extract_json
from models.schemas import CoverageTarget, GeneratedCode, GeneratedTests

logger = logging.getLogger(__name__)

_PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "test_generator.txt"


def _load_prompt_template() -> str:
    if _PROMPT_FILE.exists():
        return _PROMPT_FILE.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Test generator prompt not found: {_PROMPT_FILE}")


def _validate_python(code: str) -> tuple[bool, str]:
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as exc:
        return False, str(exc)


class TestGeneratorAgent:
    """
    Agent 2: Generates pytest test code targeting decision/branch coverage.
    Supports feedback-loop iterations.
    """

    SYSTEM_PROMPT = (
        "You are an expert Python software testing engineer specialising in "
        "decision/branch coverage. "
        "Respond only with a valid JSON object as specified by the user. "
        "Do not include any text outside the JSON."
    )

    def __init__(self, client: LLMClient) -> None:
        self._client = client
        self._template = _load_prompt_template()

    # ------------------------------------------------------------------
    def generate(
        self,
        generated_code: GeneratedCode,
        testing_goal: str = "decision_coverage",
        coverage_feedback: Optional[str] = None,
        iteration: int = 1,
    ) -> GeneratedTests:
        """
        Request a pytest test suite from the LLM.

        Parameters
        ----------
        generated_code    : The code to be tested.
        testing_goal      : e.g. "decision_coverage"
        coverage_feedback : Structured feedback from the Executor (retry mode).
        iteration         : Which iteration this is (1-based).
        """
        feedback_section = ""
        if coverage_feedback:
            feedback_section = (
                "PREVIOUS RUN FEEDBACK (use this to improve coverage):\n"
                + coverage_feedback
            )

        user_prompt = self._template.format(
            function_name=generated_code.function_name,
            function_code=generated_code.code,
            feedback_section=feedback_section,
        )

        logger.info(
            "[%s] Test Generator Agent: iteration %d, requesting tests…",
            generated_code.problem_id, iteration,
        )

        try:
            raw = self._client.chat(self.SYSTEM_PROMPT, user_prompt)
        except Exception as exc:
            logger.error("[%s] LLM API error: %s", generated_code.problem_id, exc)
            return GeneratedTests(
                problem_id=generated_code.problem_id,
                test_code="",
                coverage_target=None,
                iteration=iteration,
                is_valid=False,
                parse_error=f"API error: {exc}",
                raw_response=None,
            )

        return self._parse_response(generated_code, raw, iteration)

    def _parse_response(
        self, generated_code: GeneratedCode, raw: str, iteration: int
    ) -> GeneratedTests:
        try:
            data = extract_json(raw)
        except ValueError as exc:
            logger.warning("[%s] JSON parse error: %s", generated_code.problem_id, exc)
            return GeneratedTests(
                problem_id=generated_code.problem_id,
                test_code="",
                coverage_target=None,
                iteration=iteration,
                is_valid=False,
                parse_error=str(exc),
                raw_response=raw,
            )

        test_code = data.get("test_code", "").strip()
        if not test_code:
            return GeneratedTests(
                problem_id=generated_code.problem_id,
                test_code="",
                coverage_target=None,
                iteration=iteration,
                is_valid=False,
                parse_error="LLM returned empty test_code field.",
                raw_response=raw,
            )

        # Normalise escaped newlines
        test_code = test_code.replace("\\n", "\n").replace("\\t", "\t")

        # Parse coverage metadata (advisory only)
        coverage_target: Optional[CoverageTarget] = None
        meta = data.get("coverage_metadata", {})
        if meta:
            coverage_target = CoverageTarget(
                criterion=meta.get("criterion", "decision_coverage"),
                target_percentage=float(meta.get("target_percentage", 100.0)),
                intended_branches=meta.get("intended_branches", []),
                edge_cases=meta.get("edge_cases", []),
            )

        valid, err = _validate_python(test_code)
        if not valid:
            logger.warning(
                "[%s] Generated tests have syntax error: %s",
                generated_code.problem_id, err,
            )

        return GeneratedTests(
            problem_id=generated_code.problem_id,
            test_code=test_code,
            coverage_target=coverage_target,
            iteration=iteration,
            is_valid=valid,
            parse_error=err if not valid else None,
            raw_response=raw,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def mock_generate(
        generated_code: GeneratedCode,
        iteration: int = 1,
    ) -> GeneratedTests:
        """
        Mock implementation for smoke-test / dry-run mode.
        Generates real pytest tests that IMPORT from generated_code.py.
        MUST NOT be presented as an AI experiment result.
        """
        fn = generated_code.function_name
        test_code = f"""\
# [MOCK MODE - no LLM call made]
# These tests were generated by the mock pipeline, not by an AI model.

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generated_code import {fn}
import pytest


def test_{fn}_none_input():
    \"\"\"Branch: n is None -> return None\"\"\"
    assert {fn}(None) is None


def test_{fn}_negative():
    \"\"\"Branch: n < 0 -> return -1\"\"\"
    assert {fn}(-5) == -1


def test_{fn}_zero():
    \"\"\"Branch: n == 0 -> return 0\"\"\"
    assert {fn}(0) == 0


def test_{fn}_even_loop():
    \"\"\"Branch: n > 0, loop runs, even index\"\"\"
    result = {fn}(4)
    assert result == 0 + 2  # indices 0, 2


def test_{fn}_odd_not_added():
    \"\"\"Branch: n > 0, loop runs, odd index not added\"\"\"
    result = {fn}(3)
    assert result == 0 + 2  # only indices 0 and 2


def test_{fn}_large_even():
    \"\"\"Branch: larger even n, multiple loop iterations\"\"\"
    result = {fn}(6)
    assert result == 0 + 2 + 4
"""
        valid, err = _validate_python(test_code)
        return GeneratedTests(
            problem_id=generated_code.problem_id,
            test_code=test_code,
            coverage_target=CoverageTarget(
                criterion="decision_coverage",
                target_percentage=100.0,
                intended_branches=[
                    "n is None -> return None",
                    "n < 0 -> return -1",
                    "n == 0 -> return 0",
                    "n > 0 -> enter loop",
                    "i % 2 == 0 -> add to total",
                    "i % 2 != 0 -> skip",
                ],
                edge_cases=["None input", "negative", "zero", "small positive"],
            ),
            iteration=iteration,
            is_valid=valid,
            parse_error=err if not valid else None,
            raw_response="[MOCK MODE - no LLM call made]",
        )
