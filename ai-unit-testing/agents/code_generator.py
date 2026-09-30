"""
agents/code_generator.py
Agent 1 — Code Generator Agent

Responsibility:
  Receive a benchmark Problem and produce a syntactically valid
  Python implementation of the required function.

Input:   Problem (problem_id, prompt, entry_point)
Output:  GeneratedCode (code, function_name, is_valid)

The agent NEVER executes the code it generates.
Structured JSON is validated before passing to the next stage.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

from agents.llm_client import LLMClient, extract_json
from models.schemas import GeneratedCode, Problem

logger = logging.getLogger(__name__)

_PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "code_generator.txt"


def _load_prompt_template() -> str:
    if _PROMPT_FILE.exists():
        return _PROMPT_FILE.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Code generator prompt not found: {_PROMPT_FILE}")


def _validate_python(code: str) -> tuple[bool, str]:
    """Return (is_valid, error_message)."""
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as exc:
        return False, str(exc)


class CodeGeneratorAgent:
    """
    Agent 1: Generates Python implementation code for a given Problem.
    """

    SYSTEM_PROMPT = (
        "You are an expert Python software engineer. "
        "Respond only with a valid JSON object as specified by the user. "
        "Do not include any text outside the JSON."
    )

    def __init__(self, client: LLMClient) -> None:
        self._client = client
        self._template = _load_prompt_template()

    # ------------------------------------------------------------------
    def generate(self, problem: Problem) -> GeneratedCode:
        """
        Call the LLM, parse and validate the response, return GeneratedCode.
        """
        user_prompt = self._template.format(
            problem_description=problem.prompt,
            entry_point=problem.entry_point,
        )

        logger.info("[%s] Code Generator Agent: requesting implementation…", problem.problem_id)

        try:
            raw = self._client.chat(self.SYSTEM_PROMPT, user_prompt)
        except Exception as exc:
            logger.error("[%s] LLM API error: %s", problem.problem_id, exc)
            return GeneratedCode(
                problem_id=problem.problem_id,
                code="",
                function_name=problem.entry_point,
                is_valid=False,
                parse_error=f"API error: {exc}",
                raw_response=None,
            )

        return self._parse_response(problem, raw)

    def _parse_response(self, problem: Problem, raw: str) -> GeneratedCode:
        """Parse the JSON response and validate the Python syntax."""
        try:
            data = extract_json(raw)
        except ValueError as exc:
            logger.warning("[%s] JSON parse error: %s", problem.problem_id, exc)
            return GeneratedCode(
                problem_id=problem.problem_id,
                code="",
                function_name=problem.entry_point,
                is_valid=False,
                parse_error=str(exc),
                raw_response=raw,
            )

        code = data.get("code", "").strip()
        function_name = data.get("function_name", problem.entry_point).strip()

        if not code:
            return GeneratedCode(
                problem_id=problem.problem_id,
                code="",
                function_name=function_name,
                is_valid=False,
                parse_error="LLM returned empty code field.",
                raw_response=raw,
            )

        # Normalise escaped newlines
        code = code.replace("\\n", "\n").replace("\\t", "\t")

        valid, err = _validate_python(code)
        if not valid:
            logger.warning("[%s] Generated code has syntax error: %s", problem.problem_id, err)

        return GeneratedCode(
            problem_id=problem.problem_id,
            code=code,
            function_name=function_name,
            is_valid=valid,
            parse_error=err if not valid else None,
            raw_response=raw,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def mock_generate(problem: Problem) -> GeneratedCode:
        """
        Mock implementation for smoke-test / dry-run mode.
        Returns a simple but real Python function with multiple branches.
        MUST NOT be presented as an AI experiment result.
        """
        code = (
            f"def {problem.entry_point}(n):\n"
            f"    \"\"\"Mock implementation of {problem.entry_point} for pipeline testing.\"\"\"\n"
            f"    if n is None:\n"
            f"        return None\n"
            f"    if n < 0:\n"
            f"        return -1\n"
            f"    elif n == 0:\n"
            f"        return 0\n"
            f"    else:\n"
            f"        total = 0\n"
            f"        for i in range(n):\n"
            f"            if i % 2 == 0:\n"
            f"                total += i\n"
            f"        return total\n"
        )
        return GeneratedCode(
            problem_id=problem.problem_id,
            code=code,
            function_name=problem.entry_point,
            is_valid=True,
            parse_error=None,
            raw_response="[MOCK MODE — no LLM call made]",
        )
