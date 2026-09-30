"""
datasources/selector.py
Loads the curated problem selection from config/selected_problems.json
and filters / scores problems from the underlying dataset adapter.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from datasources.base import BaseDataset
from models.schemas import Problem

logger = logging.getLogger(__name__)


class ProblemSelector:
    """
    Wraps a BaseDataset adapter and provides a deterministic curated
    subset of problems suitable for decision/branch coverage experiments.
    """

    def __init__(self, dataset: BaseDataset, selection_file: Optional[Path] = None) -> None:
        self._dataset = dataset
        self._selection_file = selection_file

    # ------------------------------------------------------------------
    def load(self) -> None:
        self._dataset.load()

    # ------------------------------------------------------------------
    def get_curated_problems(self) -> List[Problem]:
        """
        Return the deterministic curated subset from the selection file.
        Falls back to automatic heuristic selection if the file is absent.
        """
        if self._selection_file and self._selection_file.exists():
            return self._load_from_file()
        logger.warning(
            "Selected-problems file not found (%s). "
            "Falling back to automatic heuristic selection.",
            self._selection_file,
        )
        return self._auto_select()

    def _load_from_file(self) -> List[Problem]:
        with open(self._selection_file, "r", encoding="utf-8") as f:  # type: ignore[arg-type]
            cfg = json.load(f)
        ids: List[str] = cfg.get("problem_ids", [])
        problems: List[Problem] = []
        missing: List[str] = []
        for pid in ids:
            p = self._dataset.get_problem(pid)
            if p is not None:
                problems.append(p)
            else:
                missing.append(pid)
        if missing:
            logger.warning("Problem IDs in selection file not found in dataset: %s", missing)
        logger.info("Loaded %d curated problems from selection file.", len(problems))
        return problems

    def _auto_select(self, target: int = 20) -> List[Problem]:
        """
        Heuristically select up to `target` problems that have
        meaningful control flow in their reference solution.
        """
        selected: List[Problem] = []
        for p in self._dataset.iter_problems():
            if BaseDataset.has_meaningful_control_flow(p.canonical_solution):
                selected.append(p)
            if len(selected) >= target:
                break
        logger.info("Auto-selected %d problems with meaningful control flow.", len(selected))
        return selected

    # ------------------------------------------------------------------
    def get_problem(self, problem_id: str) -> Optional[Problem]:
        return self._dataset.get_problem(problem_id)

    def list_all_ids(self) -> List[str]:
        return self._dataset.list_ids()

    def list_meaningful_ids(self) -> List[str]:
        """Return IDs of problems with meaningful control flow."""
        return [
            p.problem_id
            for p in self._dataset.iter_problems()
            if BaseDataset.has_meaningful_control_flow(p.canonical_solution)
        ]
