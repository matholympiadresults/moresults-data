"""Base parser interface for EMO data sources."""

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import ContestantResult


class BaseParser(ABC):
    """Abstract base class for year-specific EMO parsers."""

    def __init__(self, year: int):
        self.year = year

    @abstractmethod
    def parse(self, raw_file: Path) -> list[ContestantResult]:
        """Parse the raw data file and extract contestant results."""
        pass

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
