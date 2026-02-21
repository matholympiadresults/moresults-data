"""Base parser interface for BalcanMO data sources."""

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import ContestantResult


class BaseParser(ABC):
    """Abstract base class for year-specific BalcanMO parsers."""

    def __init__(self, year: int):
        """Initialize parser with year.

        Args:
            year: The competition year
        """
        self.year = year

    @abstractmethod
    def parse(self, raw_file: Path) -> list[ContestantResult]:
        """Parse the raw data file and extract contestant results.

        Args:
            raw_file: Path to the raw data file

        Returns:
            List of contestant results
        """
        pass

    def compute_ranks(self, results: list[ContestantResult]) -> None:
        """Compute competition-style ranks based on total scores.

        Contestants with the same score share the same rank.
        The next different score gets rank = position in sorted list.

        Args:
            results: List of contestant results to update in-place
        """
        if not results:
            return

        # Sort by total descending (higher score = better rank)
        sorted_results = sorted(results, key=lambda r: r.total, reverse=True)

        current_rank = 1
        for i, result in enumerate(sorted_results):
            if i > 0 and result.total < sorted_results[i - 1].total:
                # Different score than previous, rank = current position (1-indexed)
                current_rank = i + 1
            result.rank = current_rank
