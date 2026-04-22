"""Base parser interface for JBMO data sources."""

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import ContestantResult


class BaseParser(ABC):
    """Abstract base class for year-specific JBMO parsers."""

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
                current_rank = i + 1
            result.rank = current_rank

    def normalize_award(self, award: str | None) -> str | None:
        """Normalize award text to standard format."""
        if not award:
            return None
        award_lower = award.lower().strip()
        if "gold" in award_lower:
            return "Gold"
        if "silver" in award_lower:
            return "Silver"
        if "bronze" in award_lower:
            return "Bronze"
        if "honourable" in award_lower or "honorable" in award_lower or award_lower == "hm":
            return "Honourable Mention"
        return award if award else None
