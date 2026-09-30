"""
agents/test_executor.py
Agent 3 — Test Case Executor Agent

Responsibility (primarily deterministic):
  - Write generated code and tests to an isolated output directory.
  - Execute them in a subprocess via SandboxRunner.
  - Parse results using the runner module.
  - Calculate the final verdict via the evaluation module.
  - Persist all artifacts (code, tests, logs, coverage, result JSON).
  - Return a structured ExecutionResult + Verdict.

This agent NEVER overrides measured coverage based on the LLM's claim.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Optional

from execution.sandbox import SandboxRunner
from execution.runner import parse_sandbox_output
from evaluation.verdict import calculate_verdict, build_coverage_feedback
from models.schemas import (
    ExecutionResult,
    GeneratedCode,
    GeneratedTests,
    PipelineResult,
    Verdict,
)

logger = logging.getLogger(__name__)


class TestExecutorAgent:
    """
    Agent 3: Executes generated tests and measures actual coverage.
    """

    def __init__(self, timeout_s: int = 30) -> None:
        self._sandbox = SandboxRunner(timeout_s=timeout_s)

    # ------------------------------------------------------------------
    def execute(
        self,
        generated_code: GeneratedCode,
        generated_tests: GeneratedTests,
        output_dir: Path,
        target_pct: float = 100.0,
        iteration: int = 1,
    ) -> tuple[ExecutionResult, Verdict]:
        """
        Run the tests and calculate a verdict.

        Parameters
        ----------
        generated_code  : Validated Python implementation.
        generated_tests : Validated pytest test suite.
        output_dir      : Per-problem output directory (persistent).
        target_pct      : Required branch coverage % (default 100.0).
        iteration       : Current feedback-loop iteration number.

        Returns
        -------
        (ExecutionResult, Verdict)
        """
        # Create a sub-directory per iteration so all runs are preserved
        run_dir = output_dir / f"run_{iteration}"
        run_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "[%s] Test Executor Agent: running iteration %d in %s",
            generated_code.problem_id, iteration, run_dir,
        )

        # ── Write source files ──────────────────────────────────────────
        (run_dir / "generated_code.py").write_text(
            generated_code.code, encoding="utf-8"
        )
        (run_dir / "generated_tests.py").write_text(
            generated_tests.test_code, encoding="utf-8"
        )

        # ── Execute in sandbox ──────────────────────────────────────────
        sandbox_result = self._sandbox.execute(
            code=generated_code.code,
            tests=generated_tests.test_code,
            work_dir=run_dir,
        )

        # ── Parse results ───────────────────────────────────────────────
        exec_result = parse_sandbox_output(generated_code.problem_id, sandbox_result)

        # ── Calculate verdict ────────────────────────────────────────────
        verdict = calculate_verdict(exec_result, target_pct=target_pct)

        # ── Persist execution log ────────────────────────────────────────
        log_path = run_dir / "execution.log"
        log_path.write_text(
            f"=== STDOUT ===\n{exec_result.stdout}\n"
            f"=== STDERR ===\n{exec_result.stderr}\n"
            f"=== VERDICT ===\n{verdict.value}\n",
            encoding="utf-8",
        )

        # ── Persist structured result ────────────────────────────────────
        result_dict = exec_result.to_dict()
        result_dict["verdict"] = verdict.value
        result_dict["iteration"] = iteration
        (run_dir / "result.json").write_text(
            json.dumps(result_dict, indent=2), encoding="utf-8"
        )

        # Copy coverage artifacts to the run directory (already there)
        # coverage.json and htmlcov/ are written by SandboxRunner into run_dir

        logger.info(
            "[%s] Iteration %d: verdict=%s coverage=%.1f%%",
            generated_code.problem_id,
            iteration,
            verdict.value,
            (exec_result.coverage.branch_coverage_pct or 0.0)
            if exec_result.coverage and exec_result.coverage.supported
            else 0.0,
        )

        return exec_result, verdict

    # ------------------------------------------------------------------
    def get_coverage_feedback(self, exec_result: ExecutionResult) -> str:
        """Return structured feedback suitable for the Test Generator Agent."""
        return build_coverage_feedback(exec_result)

    # ------------------------------------------------------------------
    @staticmethod
    def write_final_result(result: PipelineResult, output_dir: Path) -> None:
        """Persist the final PipelineResult JSON to the problem output dir."""
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "result.json"
        path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        logger.info("Final result written to %s", path)

    # ------------------------------------------------------------------
    @staticmethod
    def copy_best_artifacts(output_dir: Path, best_run: int) -> None:
        """
        Copy code/tests/coverage from the best run to the problem root
        for easy inspection.
        """
        run_dir = output_dir / f"run_{best_run}"
        if not run_dir.exists():
            return
        for fname in ("generated_code.py", "generated_tests.py",
                      "execution.log", "coverage.json"):
            src = run_dir / fname
            if src.exists():
                shutil.copy2(src, output_dir / fname)
        # Copy htmlcov if present
        htmlcov_src = run_dir / "htmlcov"
        htmlcov_dst = output_dir / "htmlcov"
        if htmlcov_src.exists():
            if htmlcov_dst.exists():
                shutil.rmtree(htmlcov_dst)
            shutil.copytree(htmlcov_src, htmlcov_dst)
