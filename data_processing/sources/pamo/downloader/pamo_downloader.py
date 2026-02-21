#!/usr/bin/env python3
"""
PAMO Downloader

Downloads raw HTML pages from pamoofficial.org for later parsing.
"""

from pathlib import Path

import requests

# URL pattern: www.pamoofficial.org/timeline/{year}/individual.html
BASE_URL_TEMPLATE = "https://www.pamoofficial.org/timeline/{year}/individual.html"

# PAMO started in 1987 (edition 1)
PAMO_START_YEAR = 1987

# Available years with data on the website (not all years have online results)
# Note: 2015 page exists but has no data
AVAILABLE_YEARS = [
    2007,
    2012,
    2013,
    2016,
    2017,
    2018,
    2019,
    2021,
    2022,
    2023,
    2024,
    2025,
]


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
    output_file = output_dir / get_raw_filename()

    if output_file.exists() and not force:
        return output_file

    url = BASE_URL_TEMPLATE.format(year=year)

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise DownloadError(f"Failed to download PAMO {year}: {e}") from e

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_text(response.text, encoding="utf-8")

    return output_file
