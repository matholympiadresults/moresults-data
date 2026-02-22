"""Base class for olympiad data source adapters."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path


class SourceAdapter(ABC):
    """Abstract base class for olympiad data sources.

    Data pipeline:
    1. download_raw() - Download raw data (HTML, PDF, CSV) to source_dir/{source}/raw/{year}/
    2. parse_raw() - Parse raw data to source_dir/{source}/parsed/{year}/
    3. ingest() - Ingest parsed data into the database
    """

    name: str  # e.g., "egmo"
    display_name: str  # e.g., "EGMO"
    first_year: int
    last_year: int | None = None  # None = current year

    def get_raw_dir(self, source_dir: Path, year: int) -> Path:
        """Get the raw data directory for a specific year.

        Args:
            source_dir: Base directory for all source data
            year: Year for the year-specific subdirectory (required)

        Returns:
            Path to source_dir/{source}/raw/{year}/
        """
        return source_dir / self.name / "raw" / str(year)

    def get_raw_base_dir(self, source_dir: Path) -> Path:
        """Get the base raw data directory (without year).

        Args:
            source_dir: Base directory for all source data

        Returns:
            Path to source_dir/{source}/raw/
        """
        return source_dir / self.name / "raw"

    def get_parsed_dir(self, source_dir: Path, year: int) -> Path:
        """Get the parsed data directory for a specific year.

        Args:
            source_dir: Base directory for all source data
            year: Year for the year-specific subdirectory (required)

        Returns:
            Path to source_dir/{source}/parsed/{year}/
        """
        return source_dir / self.name / "parsed" / str(year)

    def get_parsed_base_dir(self, source_dir: Path) -> Path:
        """Get the base parsed data directory (without year).

        Args:
            source_dir: Base directory for all source data

        Returns:
            Path to source_dir/{source}/parsed/
        """
        return source_dir / self.name / "parsed"

    @abstractmethod
    def download_raw(
        self,
        source_dir: Path,
        years: list[int] | None,
        force: bool,
    ) -> None:
        """Download raw data files to source_dir/{source}/raw/{year}/.

        Args:
            source_dir: Base directory for all source data
            years: List of years to download, or None for all available
            force: If True, overwrite existing files
        """
        pass

    @abstractmethod
    def parse_raw(
        self,
        source_dir: Path,
        years: list[int] | None,
        force: bool,
    ) -> None:
        """Parse raw files from source_dir/{source}/raw/{year}/ to source_dir/{source}/parsed/{year}/.

        Args:
            source_dir: Base directory for all source data
            years: List of years to parse, or None for all available
            force: If True, overwrite existing parsed files
        """
        pass

    @abstractmethod
    def ingest(
        self,
        source_dir: Path,
        output_path: Path,
        years: list[int] | None,
    ) -> None:
        """Ingest parsed data from source_dir/{source}/parsed/{year}/ into database.

        Args:
            source_dir: Base directory for all source data
            output_path: Path to the output database file
            years: List of years to ingest, or None for all available
        """
        pass

    def info(self, year: int, source_dir: Path) -> None:
        """Get info for a specific year. Optional - not all sources support this."""
        raise NotImplementedError(f"{self.display_name} does not support info command")

    def get_available_years(self) -> range:
        """Get range of years with available data."""
        end = self.last_year or datetime.now().year
        return range(self.first_year, end + 1)

    def find_available_raw_years(self, source_dir: Path) -> list[int]:
        """Find years that have raw data downloaded.

        Args:
            source_dir: Base directory for all source data

        Returns:
            Sorted list of years with raw data
        """
        raw_base = self.get_raw_base_dir(source_dir)
        years = []
        if raw_base.exists():
            for year_dir in raw_base.iterdir():
                if year_dir.is_dir() and year_dir.name.isdigit():
                    years.append(int(year_dir.name))
        return sorted(years)

    def find_available_parsed_years(self, source_dir: Path) -> list[int]:
        """Find years that have parsed data available.

        Args:
            source_dir: Base directory for all source data

        Returns:
            Sorted list of years with parsed data
        """
        parsed_base = self.get_parsed_base_dir(source_dir)
        years = []
        if parsed_base.exists():
            for year_dir in parsed_base.iterdir():
                if year_dir.is_dir() and year_dir.name.isdigit():
                    years.append(int(year_dir.name))
        return sorted(years)
