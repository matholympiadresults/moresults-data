"""PAMO downloader - downloads raw HTML from pamoofficial.org."""

from .pamo_downloader import AVAILABLE_YEARS, DownloadError, download_year

__all__ = ["download_year", "AVAILABLE_YEARS", "DownloadError"]
