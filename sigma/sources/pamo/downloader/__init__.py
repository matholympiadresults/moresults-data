"""PAMO downloader - downloads raw results data from pamoofficial.org."""

from .pamo_downloader import (
    AVAILABLE_YEARS,
    NEW_FORMAT_START_YEAR,
    DownloadError,
    download_year,
    get_raw_filename,
)

__all__ = [
    "download_year",
    "get_raw_filename",
    "AVAILABLE_YEARS",
    "NEW_FORMAT_START_YEAR",
    "DownloadError",
]
