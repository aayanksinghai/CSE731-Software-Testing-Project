"""
datasets/humaneval.py
HumanEval dataset adapter.

Downloads via HuggingFace datasets library.
Falls back to a local JSON file at datasets/humaneval_data.json if offline.

Schema normalisation:
  HumanEval field  → Internal Problem field
  task_id          → problem_id  (e.g. "HumanEval/0" → "humaneval_0")
  prompt           → prompt
  canonical_solution → canonical_solution
  entry_point      → entry_point
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from datasets.base import BaseDataset
from models.schemas import DatasetName, Problem

logger = logging.getLogger(__name__)

_LOCAL_FALLBACK = Path(__file__).parent / "humaneval_data.json"


class HumanEvalDataset(BaseDataset):
    """Adapter for the HumanEval benchmark dataset."""

    def __init__(self) -> None:
        self._problems: Dict[str, Problem] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    def load(self) -> None:
        if self._loaded:
            return

        if _LOCAL_FALLBACK.exists():
            logger.info("Loading HumanEval from local fallback: %s", _LOCAL_FALLBACK)
            self._load_from_local(_LOCAL_FALLBACK)
        else:
            logger.info("Attempting to download HumanEval from HuggingFace…")
            try:
                self._load_from_huggingface()
            except Exception as exc:
                logger.error(
                    "HuggingFace download failed: %s\n"
                    "Run: python main.py setup   to download the dataset.",
                    exc,
                )
                raise RuntimeError(
                    "HumanEval dataset not available. "
                    "Run `python main.py setup` to download it, "
                    "or place humaneval_data.json in the datasets/ directory."
                ) from exc

        self._loaded = True
        logger.info("HumanEval loaded — %d problems available.", len(self._problems))

    # ------------------------------------------------------------------
    def _load_from_huggingface(self) -> None:
        from datasets import load_dataset  # HuggingFace datasets library
        ds = load_dataset("openai_humaneval", split="test", trust_remote_code=True)
        for record in ds:
            self._ingest_record(record)
        self._save_local_cache()

    def _load_from_local(self, path: Path) -> None:
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)
        for record in records:
            self._ingest_record(record)

    def _ingest_record(self, record: dict) -> None:
        raw_id = record.get("task_id", "")  # "HumanEval/0"
        numeric = raw_id.split("/")[-1] if "/" in raw_id else raw_id
        problem_id = f"humaneval_{numeric}"
        problem = Problem(
            problem_id=problem_id,
            prompt=record.get("prompt", ""),
            entry_point=record.get("entry_point", "solution"),
            canonical_solution=record.get("canonical_solution"),
            dataset=DatasetName.HUMANEVAL,
            raw=dict(record),
        )
        self._problems[problem_id] = problem

    def _save_local_cache(self) -> None:
        records = [p.raw for p in self._problems.values()]
        try:
            with open(_LOCAL_FALLBACK, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, default=str)
            logger.info("HumanEval cached to %s", _LOCAL_FALLBACK)
        except OSError as e:
            logger.warning("Could not write HumanEval cache: %s", e)

    # ------------------------------------------------------------------
    def get_problem(self, problem_id: str) -> Optional[Problem]:
        return self._problems.get(problem_id)

    def iter_problems(self) -> Iterator[Problem]:
        yield from self._problems.values()

    def list_ids(self) -> List[str]:
        return sorted(self._problems.keys())
