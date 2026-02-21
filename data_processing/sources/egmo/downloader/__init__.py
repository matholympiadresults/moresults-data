"""EGMO download module - downloads raw HTML and CSV from egmo.org."""

from .egmo_downloader import (
    FIRST_EGMO_YEAR,
    DownloadError,
    download_raw,
    edition_to_year,
    get_available_years,
    get_latest_edition,
    year_to_edition,
)

__all__ = [
    "FIRST_EGMO_YEAR",
    "DownloadError",
    "download_raw",
    "edition_to_year",
    "get_available_years",
    "get_latest_edition",
    "year_to_edition",
]
