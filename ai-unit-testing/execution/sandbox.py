"""
execution/sandbox.py
Executes generated Python code and pytest tests inside an isolated
subprocess with a timeout. Generated code is NEVER imported directly
into the main process.

Safety model:
  - Subprocess only (never exec/eval in the main process)
  - Configurable timeout (SUBPROCESS_TIMEOUT_S)
  - Isolated temporary working directory
  - Controlled environment (inherits PATH but strips sensitive vars)
  - stdout + stderr fully captured
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Variables to strip from the subprocess environment
_SENSITIVE_ENV_VARS = {"LLM_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"}


def _safe_env() -> dict:
    """Return an env dict with API keys removed."""
    env = os.environ.copy()
    for key in _SENSITIVE_ENV_VARS:
        env.pop(key, None)
    return env


def run_subprocess(
    cmd: list[str],
    cwd: Path,
    timeout_s: int,
    extra_env: Optional[dict] = None,
) -> Tuple[int, str, str, float, bool]:
    """
    Run cmd in cwd with a timeout.

    Returns
    -------
    (returncode, stdout, stderr, elapsed_s, timed_out)
    """
    env = _safe_env()
    if extra_env:
        env.update(extra_env)

    timed_out = False
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=env,
        )
        elapsed = time.monotonic() - start
        return proc.returncode, proc.stdout, proc.stderr, elapsed, False
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - start
        stdout = exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        logger.warning("Subprocess timed out after %.1fs", elapsed)
        return -1, stdout, stderr, elapsed, True
    except Exception as exc:
        elapsed = time.monotonic() - start
        logger.error("Subprocess launch failed: %s", exc)
        return -2, "", str(exc), elapsed, False


class SandboxRunner:
    """
    High-level interface for running pytest + coverage inside a sandbox.

    Workflow per problem:
      1.  Write generated_code.py into a temp directory
      2.  Write generated_tests.py into the same directory
      3.  Run:  coverage run --branch -m pytest generated_tests.py
                             --json-report --json-report-file=report.json
      4.  Run:  coverage json --omit="generated_tests.py" -o coverage.json
      5.  Read and return the raw output files
    """

    def __init__(self, timeout_s: int = 30) -> None:
        self.timeout_s = timeout_s

    def execute(
        self,
        code: str,
        tests: str,
        work_dir: Optional[Path] = None,
    ) -> dict:
        """
        Execute tests against code.

        Parameters
        ----------
        code      : The generated Python implementation source.
        tests     : The generated pytest source.
        work_dir  : If provided, files are written here (and kept).
                    If None, a temporary directory is used and cleaned up.

        Returns
        -------
        dict with keys:
            returncode, stdout, stderr, elapsed_s, timed_out,
            pytest_json_path, coverage_json_path, work_dir
        """
        cleanup = work_dir is None
        tmp = tempfile.mkdtemp(prefix="aiu_sandbox_") if cleanup else None
        base = Path(tmp) if cleanup else work_dir  # type: ignore[arg-type]
        base.mkdir(parents=True, exist_ok=True)

        code_file = base / "generated_code.py"
        test_file = base / "generated_tests.py"
        report_file = base / "report.json"
        coverage_json = base / "coverage.json"
        coverage_html_dir = base / "htmlcov"

        code_file.write_text(code, encoding="utf-8")
        test_file.write_text(tests, encoding="utf-8")

        python = sys.executable

        # ── Step 1: coverage run --branch -m pytest ──────────────────────
        cmd_run = [
            python, "-m", "coverage", "run",
            "--branch",
            f"--include={code_file}",
            "-m", "pytest",
            str(test_file),
            "--tb=short",
            "-q",
            "--json-report",
            f"--json-report-file={report_file}",
        ]
        rc, stdout, stderr, elapsed, timed_out = run_subprocess(
            cmd_run, cwd=base, timeout_s=self.timeout_s
        )

        # ── Step 2: coverage json ─────────────────────────────────────────
        cov_rc, cov_out, cov_err, _, _ = run_subprocess(
            [python, "-m", "coverage", "json",
             f"--include={code_file}",
             "-o", str(coverage_json)],
            cwd=base,
            timeout_s=10,
        )

        # ── Step 3: coverage html (best-effort, non-blocking) ─────────────
        run_subprocess(
            [python, "-m", "coverage", "html",
             f"--include={code_file}",
             "-d", str(coverage_html_dir)],
            cwd=base,
            timeout_s=10,
        )

        return {
            "returncode": rc,
            "stdout": stdout,
            "stderr": stderr,
            "elapsed_s": elapsed,
            "timed_out": timed_out,
            "pytest_json_path": report_file if report_file.exists() else None,
            "coverage_json_path": coverage_json if coverage_json.exists() else None,
            "coverage_html_dir": coverage_html_dir if coverage_html_dir.exists() else None,
            "work_dir": base,
        }
