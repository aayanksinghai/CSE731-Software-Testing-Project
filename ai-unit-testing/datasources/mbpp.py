"""
datasources/mbpp.py
MBPP (Mostly Basic Python Problems) dataset adapter.

Downloads via HuggingFace `datasets` library (the installed package, NOT our local module).
Falls back to a local JSON file at datasources/mbpp_data.json if offline.

Schema normalisation:
  MBPP field  -> Internal Problem field
  task_id     -> problem_id  ("mbpp_<id>")
  text        -> prompt
  code        -> canonical_solution
  (heuristic) -> entry_point  (first def found in code)
"""

from __future__ import annotations

import json
import re
import logging
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from datasources.base import BaseDataset
from models.schemas import DatasetName, Problem

logger = logging.getLogger(__name__)

_LOCAL_FALLBACK = Path(__file__).parent / "mbpp_data.json"


def _extract_entry_point(code: str) -> str:
    """Extract the first function name from a Python code string."""
    match = re.search(r"^def\s+([a-zA-Z_]\w*)\s*\(", code, re.MULTILINE)
    return match.group(1) if match else "solution"


class MBPPDataset(BaseDataset):
    """Adapter for the MBPP benchmark dataset."""

    def __init__(self) -> None:
        self._problems: Dict[str, Problem] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    def load(self) -> None:
        """Load MBPP — tries local fallback first, then HuggingFace."""
        if self._loaded:
            return

        if _LOCAL_FALLBACK.exists():
            logger.info("Loading MBPP from local fallback: %s", _LOCAL_FALLBACK)
            self._load_from_local(_LOCAL_FALLBACK)
        else:
            logger.info("Attempting to download MBPP from HuggingFace...")
            try:
                self._load_from_huggingface()
            except Exception as exc:
                logger.error(
                    "HuggingFace download failed: %s\n"
                    "Run: python main.py setup   to download the dataset.",
                    exc,
                )
                raise RuntimeError(
                    "MBPP dataset not available. "
                    "Run `python main.py setup` to download it, "
                    "or place mbpp_data.json in the datasources/ directory."
                ) from exc

        self._loaded = True
        logger.info("MBPP loaded -- %d problems available.", len(self._problems))

    # ------------------------------------------------------------------
    def _load_from_huggingface(self) -> None:
        # HuggingFace's `datasets` package is shadowed by our local `datasets/`
        # directory on sys.path. We load it directly from site-packages.
        import sys, sysconfig
        sp = sysconfig.get_paths()["purelib"]  # e.g. .../site-packages

        # Temporarily put site-packages first so HuggingFace wins the race
        _orig_path = sys.path.copy()
        sys.path = [sp] + [p for p in sys.path if p != sp]
        # Remove any cached shadow module so Python re-resolves the import
        sys.modules.pop("datasets", None)
        try:
            from datasets import load_dataset as _load_dataset  # HuggingFace
        finally:
            sys.path = _orig_path  # restore original path

        ds = _load_dataset("google-research-datasets/mbpp", split="train+test+validation")
        for record in ds:
            self._ingest_record(record)

        # Persist a local cache so subsequent runs are offline-capable
        self._save_local_cache()

    def _load_from_local(self, path: Path) -> None:
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)
        for record in records:
            self._ingest_record(record)

    def _ingest_record(self, record: dict) -> None:
        task_id = record.get("task_id", 0)
        problem_id = f"mbpp_{task_id}"
        code = record.get("code", "")
        entry_point = _extract_entry_point(code)
        problem = Problem(
            problem_id=problem_id,
            prompt=record.get("text", ""),
            entry_point=entry_point,
            canonical_solution=code,
            dataset=DatasetName.MBPP,
            raw=dict(record),
        )
        self._problems[problem_id] = problem

    def _save_local_cache(self) -> None:
        records = [p.raw for p in self._problems.values()]
        try:
            with open(_LOCAL_FALLBACK, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, default=str)
            logger.info("MBPP cached to %s", _LOCAL_FALLBACK)
        except OSError as e:
            logger.warning("Could not write MBPP cache: %s", e)

    # ------------------------------------------------------------------
    def get_problem(self, problem_id: str) -> Optional[Problem]:
        return self._problems.get(problem_id)

    def iter_problems(self) -> Iterator[Problem]:
        yield from self._problems.values()

    def list_ids(self) -> List[str]:
        return sorted(self._problems.keys())
