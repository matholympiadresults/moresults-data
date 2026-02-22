"""MEMO downloader - downloads raw HTML from memo-official.org."""

from .memo_downloader import (
    AVAILABLE_YEARS,
    TEAM_AVAILABLE_YEARS,
    DownloadError,
    download_team_year,
    download_year,
)

__all__ = [
    "download_year",
    "download_team_year",
    "AVAILABLE_YEARS",
    "TEAM_AVAILABLE_YEARS",
    "DownloadError",
]
