#!/usr/bin/env python3
"""
MEMO Downloader

Downloads raw HTML pages from memo-official.org for later parsing.
"""

from pathlib import Path

import requests

BASE_URL = "https://www.memo-official.org/MEMO/results"

# Special URLs for years not on memo-official.org
SPECIAL_URLS = {
    2015: "http://memo2015.dmfa.si/results.html",
}

# Available years - MEMO started in 2007
# Missing: 2012 (no data sources found yet)
AVAILABLE_YEARS = list(range(2007, 2012)) + [2013, 2014] + list(range(2015, 2026))


class DownloadError(Exception):
    """Raised when download fails."""

    pass


def get_raw_filename() -> str:
    """Get the filename for a raw HTML file."""
    return "individual.html"


def download_year(year: int, output_dir: Path, force: bool = False) -> Path:
    """
    Download the individual results page HTML for a given year.

    Args:
        year: The year to download
        output_dir: Directory to save the raw HTML (year subdirectory)
        force: If True, re-download even if file exists

    Returns:
        Path to the downloaded file

    Raises:
        DownloadError: If download fails
    """
    # Use legacy downloader for 2007 (XLS file)
    if year == 2007:
        from data_processing.sources.memo.legacy.memo_2007 import download_2007

        return download_2007(output_dir, force=force)

    # Use pass-through downloader for 2014 (local ODS file)
    if year == 2014:
        from data_processing.sources.memo.downloader.memo_2014_downloader import (
            download_2014,
        )

        return download_2014(output_dir, force=force)

    output_file = output_dir / get_raw_filename()

    if output_file.exists() and not force:
        return output_file

    # Use special URL if available, otherwise standard memo-official.org
    if year in SPECIAL_URLS:
        url = SPECIAL_URLS[year]
    else:
        url = f"{BASE_URL}/{year}/individual/"

    try:
        response = requests.get(url, timeout=30, verify=(year not in SPECIAL_URLS))
        response.raise_for_status()
    except requests.RequestException as e:
        raise DownloadError(f"Failed to download MEMO {year}: {e}") from e

    output_dir.mkdir(parents=True, exist_ok=True)
    # Use content bytes and decode as UTF-8 to avoid encoding detection issues
    output_file.write_text(response.content.decode("utf-8"), encoding="utf-8")

    return output_file
