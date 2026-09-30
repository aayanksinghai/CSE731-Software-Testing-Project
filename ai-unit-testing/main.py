"""
main.py
Command-line interface for the AI-Assisted Unit Testing pipeline.

Commands:
  setup            Download / cache the benchmark dataset.
  list-problems    Show all available problem IDs (with control-flow filter).
  smoke-test       Verify the full pipeline in mock mode (no API key needed).
  run-one          Run the pipeline on a single problem.
  run-experiment   Run the pipeline on the full curated problem set.

Usage examples:
  python main.py setup
  python main.py list-problems
  python main.py smoke-test
  python main.py run-one --problem-id mbpp_11
  python main.py run-one --problem-id mbpp_11 --mock
  python main.py run-experiment
  python main.py run-experiment --mock
"""

from __future__ import annotations

import json
import logging
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Load .env before any config import ───────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars can be set manually

# ── Project imports ───────────────────────────────────────────────────
# Ensure the project root is on sys.path when running as `python main.py`
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config.settings as settings
from agents.code_generator import CodeGeneratorAgent
from agents.test_generator import TestGeneratorAgent
from agents.test_executor import TestExecutorAgent
from datasources.mbpp import MBPPDataset
from datasources.humaneval import HumanEvalDataset
from datasources.selector import ProblemSelector
from models.schemas import DatasetName, ExperimentSummary, PipelineResult, Verdict
from pipeline import Pipeline

# ── Logging setup ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Helper: build pipeline from current settings
# ══════════════════════════════════════════════════════════════════════

def _build_pipeline(mock: bool = False) -> Pipeline:
    if not mock:
        from agents.llm_client import LLMClient
        client = LLMClient(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
        code_agent = CodeGeneratorAgent(client)
        test_agent = TestGeneratorAgent(client)
    else:
        # In mock mode these agents won't be called via .generate()
        code_agent = None   # type: ignore[assignment]
        test_agent = None   # type: ignore[assignment]

    executor = TestExecutorAgent(timeout_s=settings.SUBPROCESS_TIMEOUT_S)
    return Pipeline(
        code_agent=code_agent,
        test_agent=test_agent,
        executor_agent=executor,
        outputs_root=settings.OUTPUTS_DIR,
        testing_goal=settings.TESTING_GOAL,
        target_coverage=settings.TARGET_COVERAGE,
        max_iterations=settings.MAX_FEEDBACK_ITERATIONS,
        mock=mock,
        model=settings.LLM_MODEL,
        provider_url=settings.LLM_BASE_URL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
    )


def _build_selector() -> ProblemSelector:
    name = settings.DATASET_NAME.upper()
    if name == "HUMANEVAL":
        ds = HumanEvalDataset()
    else:
        ds = MBPPDataset()
    return ProblemSelector(ds, selection_file=settings.SELECTED_PROBLEMS_FILE)


# ══════════════════════════════════════════════════════════════════════
# Commands
# ══════════════════════════════════════════════════════════════════════

def cmd_setup() -> None:
    """Download and cache the configured benchmark dataset."""
    print(f"\n[setup] Downloading dataset: {settings.DATASET_NAME}")
    selector = _build_selector()
    selector.load()
    print("[setup] Dataset ready.\n")


def cmd_list_problems(show_all: bool = False) -> None:
    """List available problem IDs."""
    selector = _build_selector()
    selector.load()
    if show_all:
        ids = selector.list_all_ids()
        label = "ALL"
    else:
        ids = selector.list_meaningful_ids()
        label = "meaningful control-flow"
    print(f"\n[list-problems] {len(ids)} problems with {label}:\n")
    for pid in ids:
        p = selector.get_problem(pid)
        snippet = (p.prompt[:80].replace("\n", " ") + "…") if p else ""
        print(f"  {pid:<20}  {snippet}")
    print()


def cmd_smoke_test() -> None:
    """Run the pipeline end-to-end in mock mode (no API key required)."""
    print("\n" + "=" * 60)
    print("  SMOKE TEST - MOCK MODE")
    print("  No LLM API calls are made. This tests pipeline infrastructure only.")
    print("=" * 60 + "\n")

    # Use a mock problem
    from models.schemas import Problem, DatasetName
    mock_problem = Problem(
        problem_id="smoke_test_mock",
        prompt="Write a function sum_evens(n) that returns the sum of even numbers from 0 to n-1.",
        entry_point="sum_evens",
        canonical_solution=None,
        dataset=DatasetName.MOCK,
    )

    pipeline = _build_pipeline(mock=True)
    result = pipeline.run(mock_problem)

    print("\n" + "-" * 40)
    print(f"  Problem ID  : {result.problem_id}")
    print(f"  Verdict     : {result.verdict.value}")
    print(f"  Coverage    : {result.branch_coverage}%")
    print(f"  Tests Pass  : {result.tests_passed}")
    print(f"  Iterations  : {result.iterations}")
    print(f"  Total Time  : {result.total_time_s:.2f}s")
    print("-" * 40)

    if result.verdict in (Verdict.PASS, Verdict.TARGET_NOT_MET):
        print("\n[OK] Smoke test PASSED - pipeline infrastructure is working correctly.")
        print("     The mock tests ran end-to-end through all 3 iterations.")
        print("     Add your API key to .env and run: python main.py run-one --problem-id <ID>\n")
    else:
        print(f"\n[FAIL] Smoke test encountered: {result.verdict.value}")
        print(f"       Detail: {result.error_detail}\n")


def cmd_run_one(problem_id: str, mock: bool = False) -> None:
    """Run the pipeline for a single problem."""
    if not mock:
        errors = settings.validate()
        if errors:
            for e in errors:
                print(f"[ERROR] {e}")
            sys.exit(1)

    selector = _build_selector()
    selector.load()
    problem = selector.get_problem(problem_id)
    if problem is None:
        print(f"[ERROR] Problem '{problem_id}' not found in dataset {settings.DATASET_NAME}.")
        print("       Run: python main.py list-problems")
        sys.exit(1)

    if mock:
        print(f"\n[run-one] MOCK MODE — problem: {problem_id}")
        print("  ⚠  Mock mode is for pipeline testing only. Not an AI experiment.\n")

    pipeline = _build_pipeline(mock=mock)
    result = pipeline.run(problem)

    _print_result(result)


def cmd_run_experiment(mock: bool = False) -> None:
    """Run the pipeline over the full curated problem set."""
    if not mock:
        errors = settings.validate()
        if errors:
            for e in errors:
                print(f"[ERROR] {e}")
            sys.exit(1)

    if mock:
        print("\n" + "=" * 60)
        print("  EXPERIMENT - MOCK MODE")
        print("  [!] Mock mode is for pipeline testing only. Not an AI experiment.")
        print("=" * 60 + "\n")

    selector = _build_selector()
    selector.load()
    problems = selector.get_curated_problems()

    if not problems:
        print("[ERROR] No curated problems found. Check config/selected_problems.json.")
        sys.exit(1)

    print(f"\n[run-experiment] Processing {len(problems)} curated problems…\n")

    pipeline = _build_pipeline(mock=mock)
    results: list[PipelineResult] = []
    exp_start = time.monotonic()

    for i, problem in enumerate(problems, 1):
        print(f"[{i:02d}/{len(problems):02d}] {problem.problem_id}")
        result = pipeline.run(problem)
        results.append(result)
        print(f"         → {result.verdict.value}  coverage={result.branch_coverage}%\n")

    total_time = time.monotonic() - exp_start
    summary = _compute_summary(results, total_time)
    _save_experiment(summary, settings.EXPERIMENTS_DIR)
    _print_summary(summary)


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════

def _print_result(result: PipelineResult) -> None:
    print("\n" + "-" * 50)
    print(f"  Problem ID       : {result.problem_id}")
    print(f"  Dataset          : {result.dataset}")
    print(f"  Testing Goal     : {result.testing_goal}")
    print(f"  Target Coverage  : {result.target_coverage}%")
    print(f"  Iterations       : {result.iterations}")
    print(f"  Tests Generated  : {result.tests_generated}")
    print(f"  Tests Passed     : {result.tests_passed}")
    print(f"  Tests Failed     : {result.tests_failed}")
    print(f"  Branch Coverage  : {result.branch_coverage}%")
    print(f"  Total Branches   : {result.total_branches}")
    print(f"  Covered Branches : {result.covered_branches}")
    print(f"  VERDICT          : {result.verdict.value}")
    print(f"  Total Time       : {result.total_time_s:.2f}s")
    if result.error_detail:
        print(f"  Error Detail     : {result.error_detail}")
    print("-" * 50 + "\n")

    out_dir = settings.OUTPUTS_DIR / result.problem_id
    print(f"  Artifacts saved to: {out_dir}\n")


def _compute_summary(results: list[PipelineResult], total_time: float) -> ExperimentSummary:
    ts = datetime.now(timezone.utc).isoformat()
    summary = ExperimentSummary(
        timestamp=ts,
        dataset=settings.DATASET_NAME,
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        target_coverage=settings.TARGET_COVERAGE,
        total_problems=len(results),
        attempted=len(results),
    )

    coverages: list[float] = []
    test_counts: list[int] = []
    iterations_counts: list[int] = []
    times: list[float] = []

    for r in results:
        summary.problem_results.append(r.to_dict())
        times.append(r.total_time_s)
        iterations_counts.append(r.iterations)
        if r.tests_generated:
            test_counts.append(r.tests_generated)

        if r.verdict == Verdict.PASS:
            summary.passed += 1
            if r.branch_coverage is not None:
                coverages.append(r.branch_coverage)
        elif r.verdict == Verdict.TARGET_NOT_MET:
            summary.target_not_met += 1
            if r.branch_coverage is not None:
                coverages.append(r.branch_coverage)
        elif r.verdict == Verdict.TEST_FAILURE:
            summary.test_failures += 1
        elif r.verdict == Verdict.CODE_GENERATION_FAILURE:
            summary.code_gen_failures += 1
        elif r.verdict == Verdict.TEST_GENERATION_FAILURE:
            summary.test_gen_failures += 1
        elif r.verdict == Verdict.EXECUTION_ERROR:
            summary.execution_errors += 1
        elif r.verdict == Verdict.COVERAGE_UNSUPPORTED:
            summary.coverage_unsupported += 1

    if coverages:
        summary.avg_branch_coverage = round(statistics.mean(coverages), 2)
        summary.median_branch_coverage = round(statistics.median(coverages), 2)
    if test_counts:
        summary.avg_tests_generated = round(statistics.mean(test_counts), 2)
    if iterations_counts:
        summary.avg_feedback_iterations = round(statistics.mean(iterations_counts), 2)
    if times:
        summary.avg_execution_time_s = round(statistics.mean(times), 2)

    return summary


def _save_experiment(summary: ExperimentSummary, experiments_dir: Path) -> None:
    experiments_dir.mkdir(parents=True, exist_ok=True)
    ts_safe = summary.timestamp.replace(":", "-").replace("+", "_")
    fname = experiments_dir / f"experiment_{ts_safe}.json"
    fname.write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")
    # Also write experiment_summary.json in outputs root for easy access
    (settings.OUTPUTS_DIR / "experiment_summary.json").write_text(
        json.dumps(summary.to_dict(), indent=2), encoding="utf-8"
    )
    logger.info("Experiment summary saved to %s", fname)


def _print_summary(summary: ExperimentSummary) -> None:
    print("\n" + "=" * 60)
    print("  EXPERIMENT SUMMARY")
    print("=" * 60)
    # (ASCII only - Windows console compatibility)
    print(f"  Total Problems          : {summary.total_problems}")
    print(f"  Attempted               : {summary.attempted}")
    print(f"  PASS                    : {summary.passed}")
    print(f"  TARGET_NOT_MET          : {summary.target_not_met}")
    print(f"  TEST_FAILURE            : {summary.test_failures}")
    print(f"  CODE_GEN_FAILURE        : {summary.code_gen_failures}")
    print(f"  TEST_GEN_FAILURE        : {summary.test_gen_failures}")
    print(f"  EXECUTION_ERROR         : {summary.execution_errors}")
    print(f"  COVERAGE_UNSUPPORTED    : {summary.coverage_unsupported}")
    print(f"  Avg Branch Coverage     : {summary.avg_branch_coverage}%")
    print(f"  Median Branch Coverage  : {summary.median_branch_coverage}%")
    print(f"  Avg Tests Generated     : {summary.avg_tests_generated}")
    print(f"  Avg Feedback Iterations : {summary.avg_feedback_iterations}")
    print(f"  Avg Execution Time      : {summary.avg_execution_time_s}s")
    print("=" * 60 + "\n")


# ══════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="AI-Assisted Unit Testing Pipeline (CSE731 Mini Project)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="Download/cache the benchmark dataset.")

    list_p = sub.add_parser("list-problems", help="List available problem IDs.")
    list_p.add_argument("--all", action="store_true", help="Show all IDs (not just meaningful ones).")

    sub.add_parser("smoke-test", help="End-to-end pipeline test in mock mode (no API key needed).")

    run_one_p = sub.add_parser("run-one", help="Run pipeline on a single problem.")
    run_one_p.add_argument("--problem-id", required=True, help="Problem ID, e.g. mbpp_11")
    run_one_p.add_argument("--mock", action="store_true", help="Mock mode (no LLM call).")

    run_exp_p = sub.add_parser("run-experiment", help="Run pipeline on the curated problem set.")
    run_exp_p.add_argument("--mock", action="store_true", help="Mock mode (no LLM call).")

    args = parser.parse_args()

    if args.command == "setup":
        cmd_setup()
    elif args.command == "list-problems":
        cmd_list_problems(show_all=getattr(args, "all", False))
    elif args.command == "smoke-test":
        cmd_smoke_test()
    elif args.command == "run-one":
        cmd_run_one(args.problem_id, mock=args.mock)
    elif args.command == "run-experiment":
        cmd_run_experiment(mock=args.mock)


if __name__ == "__main__":
    main()
