"""Base parser interface for BalcanMO data sources."""

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import ContestantResult


class BaseParser(ABC):
    """Abstract base class for year-specific BalcanMO parsers."""

    def __init__(self, year: int, raw_data_dir: Path):
        """Initialize parser with year and raw data directory.

        Args:
            year: The competition year
            raw_data_dir: Directory to store raw downloaded files
        """
        self.year = year
        self.raw_data_dir = raw_data_dir

    @property
    @abstractmethod
    def source_url(self) -> str:
        """Return the source URL for this year's data."""
        pass

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return the source type ('html' or 'pdf')."""
        pass

    @abstractmethod
    def download_raw(self, force: bool = False) -> Path:
        """Download raw data and save to raw_data_dir.

        Args:
            force: If True, re-download even if file exists

        Returns:
            Path to the downloaded file
        """
        pass

    @abstractmethod
    def parse(self, raw_file: Path) -> list[ContestantResult]:
        """Parse the raw data file and extract contestant results.

        Args:
            raw_file: Path to the raw data file

        Returns:
            List of contestant results
        """
        pass

    def get_raw_filename(self) -> str:
        """Get the filename for storing raw data."""
        ext = "pdf" if self.source_type == "pdf" else "html"
        return f"bmo_{self.year}_raw.{ext}"

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
