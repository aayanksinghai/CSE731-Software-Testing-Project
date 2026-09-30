"""
datasources/base.py
Abstract base class for all dataset adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Iterator, List, Optional

from models.schemas import Problem


class BaseDataset(ABC):
    """
    All dataset adapters inherit from this class and must implement
    the three abstract methods below.
    """

    @abstractmethod
    def load(self) -> None:
        """Download or load the dataset from disk into memory."""

    @abstractmethod
    def get_problem(self, problem_id: str) -> Optional[Problem]:
        """Return a single normalised Problem by its ID, or None if not found."""

    @abstractmethod
    def iter_problems(self) -> Iterator[Problem]:
        """Iterate over all available normalised problems."""

    @abstractmethod
    def list_ids(self) -> List[str]:
        """Return a sorted list of all available problem IDs."""

    # ------------------------------------------------------------------
    # Control-flow complexity heuristic
    # ------------------------------------------------------------------

    @staticmethod
    def has_meaningful_control_flow(solution: Optional[str]) -> bool:
        """
        Return True if the reference solution has enough control-flow
        structure to be worth including in a decision/branch coverage
        experiment.

        Heuristic: at least 2 of the following keywords must appear.
        """
        if not solution:
            return False
        keywords = ("if ", "elif ", "else:", "for ", "while ",
                    "try:", "except", "return ", "and ", "or ")
        hits = sum(1 for kw in keywords if kw in solution)
        return hits >= 2
