"""
config/settings.py
Loads all configuration from environment variables and config/config.yaml.
All components import settings from here — never from os.environ directly.
"""

from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Optional

# Project root is two levels up from this file (ai-unit-testing/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------
# Load optional config.yaml
# ------------------------------------------------------------------

_config_yaml_path = PROJECT_ROOT / "config" / "config.yaml"
_yaml_cfg: dict = {}
if _config_yaml_path.exists():
    with open(_config_yaml_path, "r", encoding="utf-8") as _f:
        _yaml_cfg = yaml.safe_load(_f) or {}


def _get(env_key: str, yaml_path: list[str], default=None):
    """Resolve: env var → yaml → default (priority order)."""
    val = os.environ.get(env_key)
    if val is not None:
        return val
    node = _yaml_cfg
    for k in yaml_path:
        if isinstance(node, dict):
            node = node.get(k)
        else:
            node = None
            break
    if node is not None:
        return node
    return default


# ------------------------------------------------------------------
# LLM / Provider settings
# ------------------------------------------------------------------

LLM_API_KEY: str = _get("LLM_API_KEY", ["llm", "api_key"], "")
LLM_BASE_URL: str = _get("LLM_BASE_URL", ["llm", "base_url"], "https://openrouter.ai/api/v1")
LLM_MODEL: str = _get("LLM_MODEL", ["llm", "model"], "openai/gpt-4o-mini")
LLM_TEMPERATURE: float = float(_get("LLM_TEMPERATURE", ["llm", "temperature"], 0.2))
LLM_MAX_TOKENS: int = int(_get("LLM_MAX_TOKENS", ["llm", "max_tokens"], 4000))

# ------------------------------------------------------------------
# Pipeline settings
# ------------------------------------------------------------------

TESTING_GOAL: str = _get("TESTING_GOAL", ["pipeline", "testing_goal"], "decision_coverage")
TARGET_COVERAGE: float = float(_get("TARGET_COVERAGE", ["pipeline", "target_coverage"], 100.0))
MAX_FEEDBACK_ITERATIONS: int = int(_get("MAX_FEEDBACK_ITERATIONS", ["pipeline", "max_feedback_iterations"], 3))
SUBPROCESS_TIMEOUT_S: int = int(_get("SUBPROCESS_TIMEOUT_S", ["pipeline", "subprocess_timeout_s"], 30))

# ------------------------------------------------------------------
# Dataset settings
# ------------------------------------------------------------------

DATASET_NAME: str = _get("DATASET_NAME", ["dataset", "name"], "MBPP")
SELECTED_PROBLEMS_FILE: Path = PROJECT_ROOT / "config" / "selected_problems.json"
RANDOM_SEED: int = int(_get("RANDOM_SEED", ["dataset", "random_seed"], 42))

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------

OUTPUTS_DIR: Path = PROJECT_ROOT / "outputs"
EXPERIMENTS_DIR: Path = PROJECT_ROOT / "experiments"
PROMPTS_DIR: Path = PROJECT_ROOT / "prompts"

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)


def summary() -> dict:
    """Return a reproducibility-safe settings summary (no secrets)."""
    return {
        "llm_model": LLM_MODEL,
        "llm_base_url": LLM_BASE_URL,
        "llm_temperature": LLM_TEMPERATURE,
        "llm_max_tokens": LLM_MAX_TOKENS,
        "testing_goal": TESTING_GOAL,
        "target_coverage": TARGET_COVERAGE,
        "max_feedback_iterations": MAX_FEEDBACK_ITERATIONS,
        "subprocess_timeout_s": SUBPROCESS_TIMEOUT_S,
        "dataset": DATASET_NAME,
        "random_seed": RANDOM_SEED,
    }


def validate() -> list[str]:
    """Return a list of configuration errors (empty = OK)."""
    errors = []
    if not LLM_API_KEY:
        errors.append(
            "LLM_API_KEY is not set. Copy .env.example to .env and add your API key, "
            "or use --mock mode for pipeline testing."
        )
    return errors
