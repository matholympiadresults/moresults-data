"""JBMO raw data downloader.

Dispatches to year-specific downloaders. Each year is hosted on a different
website with different formats, so each has its own download module.
"""

from pathlib import Path

from .downloaders import (
    dl_2010,
    dl_2012,
    dl_2013,
    dl_2014,
    dl_2015,
    dl_2016,
    dl_2021,
    dl_2023,
    dl_2024,
    dl_2025,
)

# Available years (only those with usable data)
AVAILABLE_YEARS = [2010, 2012, 2013, 2014, 2015, 2016, 2021, 2023, 2024, 2025]

# Years that use PDF sources (primary file)
PDF_YEARS = {2010, 2023}

# Per-year downloader modules
_DOWNLOADERS = {
    2010: dl_2010,
    2012: dl_2012,
    2013: dl_2013,
    2014: dl_2014,
    2015: dl_2015,
    2016: dl_2016,
    2021: dl_2021,
    2023: dl_2023,
    2024: dl_2024,
    2025: dl_2025,
}


class DownloadError(Exception):
    """Raised when downloading fails unexpectedly."""

    pass


def get_source_url(year: int) -> str:
    """Get the source URL for a given year."""
    if year not in _DOWNLOADERS:
        raise ValueError(
            f"No source URL available for year {year}. Available years: {AVAILABLE_YEARS}"
        )
    return _DOWNLOADERS[year].SOURCE_URL


def get_source_type(year: int) -> str:
    """Get the source type ('html' or 'pdf') for a given year."""
    return "pdf" if year in PDF_YEARS else "html"


def get_raw_filename(year: int) -> str:
    """Get the primary filename for storing raw data."""
    if year not in _DOWNLOADERS:
        raise ValueError(
            f"No downloader available for year {year}. Available years: {AVAILABLE_YEARS}"
        )
    return _DOWNLOADERS[year].PRIMARY_FILENAME


def download_raw(year: int, raw_data_dir: Path, force: bool = False) -> Path:
    """Download raw data for a given year.

    Dispatches to the year-specific downloader module.

    Args:
        year: The competition year
        raw_data_dir: Directory to store raw data files
        force: If True, re-download even if file exists

    Returns:
        Path to the primary downloaded file

    Raises:
        DownloadError: If download fails
    """
    if year not in _DOWNLOADERS:
        raise DownloadError(
            f"No downloader available for year {year}. Available years: {AVAILABLE_YEARS}"
        )

    try:
        return _DOWNLOADERS[year].download(raw_data_dir, force=force)
    except Exception as e:
        raise DownloadError(f"Failed to download data for year {year}: {e}") from e
