#!/usr/bin/env python3
"""
PAMO Downloader

Downloads raw HTML pages from pamoofficial.org for later parsing.
"""

import json
from pathlib import Path

import requests

# Legacy URL pattern (static per-year HTML pages, used before the 2026 redesign)
BASE_URL_TEMPLATE = "https://www.pamoofficial.org/timeline/{year}/individual.html"

# The redesigned website renders every year's results client-side from a single
# JSON file holding all contestants of all years.
STUDENTS_JSON_URL = "https://www.pamoofficial.org/data/students.json"

# First year only served by the redesigned website.
NEW_FORMAT_START_YEAR = 2026

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
    2026,
]


class DownloadError(Exception):
    """Raised when download fails."""

    pass


def get_raw_filename(year: int) -> str:
    """Get the filename for a year's raw file.

    Years from :data:`NEW_FORMAT_START_YEAR` onward come from the site-wide
    students JSON feed; older years come from per-year HTML pages.
    """
    if year >= NEW_FORMAT_START_YEAR:
        return "students.json"
    return "individual.html"


def _download_students_json(year: int) -> str:
    """Download the site-wide students feed and return this year's records as JSON.

    The redesigned website serves one JSON file covering every year, so the
    records are filtered down to the requested year before being stored.
    """
    try:
        response = requests.get(STUDENTS_JSON_URL, timeout=30)
        response.raise_for_status()
        students = response.json()
    except (requests.RequestException, ValueError) as e:
        raise DownloadError(f"Failed to download PAMO {year}: {e}") from e

    year_students = [s for s in students if str(s.get("YEAR", "")).strip() == str(year)]
    if not year_students:
        raise DownloadError(f"No PAMO {year} contestants found in {STUDENTS_JSON_URL}")

    return json.dumps(year_students, indent=2, ensure_ascii=False)


def _download_individual_html(year: int) -> str:
    """Download the legacy per-year results page HTML."""
    url = BASE_URL_TEMPLATE.format(year=year)

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise DownloadError(f"Failed to download PAMO {year}: {e}") from e

    return response.text


def download_year(year: int, output_dir: Path, force: bool = False) -> Path:
    """
    Download the raw results data for a given year.

    Args:
        year: The year to download
        output_dir: Directory to save the raw file (year subdirectory)
        force: If True, re-download even if file exists

    Returns:
        Path to the downloaded file

    Raises:
        DownloadError: If download fails
    """
    output_file = output_dir / get_raw_filename(year)

    if output_file.exists() and not force:
        return output_file

    if year >= NEW_FORMAT_START_YEAR:
        content = _download_students_json(year)
    else:
        content = _download_individual_html(year)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_text(content, encoding="utf-8")

    return output_file
