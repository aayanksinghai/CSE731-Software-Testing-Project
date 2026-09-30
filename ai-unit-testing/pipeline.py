"""
pipeline.py
Core orchestrator — wires together the three agents and the feedback loop.

Data flow:
  Problem → CodeGeneratorAgent → GeneratedCode
          → TestGeneratorAgent → GeneratedTests
          → TestExecutorAgent  → ExecutionResult + Verdict
          → [feedback loop back to TestGeneratorAgent if TARGET_NOT_MET]
          → PipelineResult

This module contains no LLM logic; it only coordinates agents and
passes structured data between them.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agents.code_generator import CodeGeneratorAgent
from agents.test_generator import TestGeneratorAgent
from agents.test_executor import TestExecutorAgent
from models.schemas import (
    GeneratedCode,
    GeneratedTests,
    PipelineResult,
    Problem,
    Verdict,
)

logger = logging.getLogger(__name__)


class Pipeline:
    """
    End-to-end pipeline for a single Problem.

    Supports:
      - Real mode (calls LLM API)
      - Mock mode (uses deterministic stubs — pipeline testing only)
    """

    def __init__(
        self,
        code_agent: CodeGeneratorAgent,
        test_agent: TestGeneratorAgent,
        executor_agent: TestExecutorAgent,
        outputs_root: Path,
        testing_goal: str = "decision_coverage",
        target_coverage: float = 100.0,
        max_iterations: int = 3,
        mock: bool = False,
        model: Optional[str] = None,
        provider_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        self._code_agent = code_agent
        self._test_agent = test_agent
        self._executor = executor_agent
        self._outputs_root = outputs_root
        self._testing_goal = testing_goal
        self._target_coverage = target_coverage
        self._max_iterations = max_iterations
        self._mock = mock
        self._model = model
        self._provider_url = provider_url
        self._temperature = temperature
        self._max_tokens = max_tokens

    # ------------------------------------------------------------------
    def run(self, problem: Problem) -> PipelineResult:
        """Execute the full pipeline for one Problem."""
        overall_start = time.monotonic()
        ts = datetime.now(timezone.utc).isoformat()

        result = PipelineResult(
            problem_id=problem.problem_id,
            dataset=problem.dataset.value,
            testing_goal=self._testing_goal,
            target_coverage=self._target_coverage,
            model=self._model,
            provider_url=self._provider_url,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            timestamp=ts,
        )

        # Per-problem output directory
        problem_dir = self._outputs_root / problem.problem_id
        problem_dir.mkdir(parents=True, exist_ok=True)

        # ── Stage 1: Code Generation ───────────────────────────────────
        logger.info("=" * 60)
        logger.info("Problem: %s | Dataset: %s", problem.problem_id, problem.dataset.value)
        logger.info("Stage 1: Code Generation")

        if self._mock:
            generated_code = CodeGeneratorAgent.mock_generate(problem)
        else:
            generated_code = self._code_agent.generate(problem)

        result.generated_code = generated_code.code
        result.code_valid = generated_code.is_valid

        if not generated_code.is_valid:
            result.verdict = Verdict.CODE_GENERATION_FAILURE
            result.error_detail = generated_code.parse_error
            result.total_time_s = time.monotonic() - overall_start
            TestExecutorAgent.write_final_result(result, problem_dir)
            logger.warning(
                "[%s] Code generation failed: %s",
                problem.problem_id, generated_code.parse_error,
            )
            return result

        logger.info("[%s] Code generated successfully (%d chars).", problem.problem_id, len(generated_code.code))

        # ── Stage 2 + 3: Test Generation → Execution (with feedback loop) ─
        coverage_feedback: Optional[str] = None
        best_exec_result = None
        best_verdict = Verdict.PENDING
        best_iteration = 1

        for iteration in range(1, self._max_iterations + 1):
            result.iterations = iteration
            logger.info("Stage 2+3: Test Generation + Execution — Iteration %d / %d", iteration, self._max_iterations)

            # ── Stage 2: Test Generation ─────────────────────────────────
            if self._mock:
                generated_tests = TestGeneratorAgent.mock_generate(generated_code, iteration)
            else:
                generated_tests = self._test_agent.generate(
                    generated_code,
                    testing_goal=self._testing_goal,
                    coverage_feedback=coverage_feedback,
                    iteration=iteration,
                )

            result.generated_tests = generated_tests.test_code
            result.tests_valid = generated_tests.is_valid

            if not generated_tests.is_valid:
                result.verdict = Verdict.TEST_GENERATION_FAILURE
                result.error_detail = generated_tests.parse_error
                logger.warning(
                    "[%s] Test generation failed: %s",
                    problem.problem_id, generated_tests.parse_error,
                )
                # Do not retry test generation failure (malformed LLM output)
                break

            # ── Stage 3: Execute + Measure Coverage ───────────────────────
            exec_result, verdict = self._executor.execute(
                generated_code=generated_code,
                generated_tests=generated_tests,
                output_dir=problem_dir,
                target_pct=self._target_coverage,
                iteration=iteration,
            )

            best_exec_result = exec_result
            best_verdict = verdict
            best_iteration = iteration

            # Collect test counts
            result.tests_generated = exec_result.tests_collected or len(
                [l for l in generated_tests.test_code.splitlines()
                 if l.strip().startswith("def test_")]
            )
            result.tests_passed = exec_result.tests_passed
            result.tests_failed = exec_result.tests_failed
            result.execution_time_s = exec_result.execution_time_s

            if exec_result.coverage and exec_result.coverage.supported:
                result.branch_coverage = exec_result.coverage.branch_coverage_pct
                result.total_branches = exec_result.coverage.total_branches
                result.covered_branches = exec_result.coverage.covered_branches
                result.missing_branches = exec_result.coverage.missing_branches

            # ── Check if done ─────────────────────────────────────────────
            if verdict == Verdict.PASS:
                logger.info("[%s] Target coverage achieved on iteration %d! ✓", problem.problem_id, iteration)
                break

            if verdict in (Verdict.EXECUTION_ERROR, Verdict.CODE_GENERATION_FAILURE):
                logger.warning("[%s] Unrecoverable error on iteration %d: %s", problem.problem_id, iteration, verdict.value)
                break

            if iteration < self._max_iterations:
                logger.info(
                    "[%s] Coverage not met (%.1f%% < %.1f%%). Building feedback for next iteration…",
                    problem.problem_id,
                    result.branch_coverage or 0.0,
                    self._target_coverage,
                )
                coverage_feedback = self._executor.get_coverage_feedback(exec_result)
            else:
                logger.info("[%s] Maximum iterations reached.", problem.problem_id)

        # ── Finalise result ───────────────────────────────────────────────
        result.verdict = best_verdict
        result.total_time_s = time.monotonic() - overall_start

        if best_exec_result and best_verdict == Verdict.PASS:
            TestExecutorAgent.copy_best_artifacts(problem_dir, best_iteration)

        TestExecutorAgent.write_final_result(result, problem_dir)
        logger.info(
            "[%s] FINAL VERDICT: %s  (%.1fs total)",
            problem.problem_id, result.verdict.value, result.total_time_s,
        )
        return result
