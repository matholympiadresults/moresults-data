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
AVAILABLE_YEARS = list(range(2007, 2015)) + list(range(2015, 2026))

# Team competition data: 2007-2014 from skmo.sk, 2015+ from memo-official.org
# Missing: 2020 (COVID online only)
TEAM_AVAILABLE_YEARS = list(range(2007, 2015)) + list(range(2015, 2020)) + list(range(2021, 2026))


class DownloadError(Exception):
    """Raised when download fails."""

    pass


def get_raw_filename() -> str:
    """Get the filename for individual results raw HTML file."""
    return "individual.html"


def get_team_raw_filename() -> str:
    """Get the filename for team results raw HTML file."""
    return "team.html"


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
        from .memo_2007_downloader import download_2007

        return download_2007(output_dir, force=force)

    # Use legacy downloader for 2011 (HTML from memo2011.math.hr)
    if year == 2011:
        from .memo_2011_downloader import download_2011

        return download_2011(output_dir, force=force)

    # Use skmo downloader for 2012 (not on memo-official.org)
    if year == 2012:
        from data_processing.sources.memo.downloader.skmo_downloader import (
            download_year as download_skmo_year,
        )

        return download_skmo_year(year, output_dir, force=force)

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


def download_team_year(year: int, output_dir: Path, force: bool = False) -> Path:
    """
    Download the team results page HTML for a given year.

    Team data is only available for 2015+.
    For 2015, team data is on the same page as individual results.

    Args:
        year: The year to download
        output_dir: Directory to save the raw HTML (year subdirectory)
        force: If True, re-download even if file exists

    Returns:
        Path to the downloaded file

    Raises:
        DownloadError: If download fails
        ValueError: If year doesn't have team data
    """
    if year not in TEAM_AVAILABLE_YEARS:
        raise ValueError(f"Team data not available for year {year}")

    output_file = output_dir / get_team_raw_filename()

    if output_file.exists() and not force:
        return output_file

    # For years <= 2014, download from skmo.sk via archive.org
    if year <= 2014:
        from data_processing.sources.memo.downloader.skmo_downloader import (
            ARCHIVE_URL_TEMPLATE,
            year_to_rocnik,
        )

        rocnik = year_to_rocnik(year)
        url = ARCHIVE_URL_TEMPLATE.format(rocnik=rocnik)

        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
        except requests.RequestException as e:
            raise DownloadError(f"Failed to download MEMO team {year}: {e}") from e

        output_dir.mkdir(parents=True, exist_ok=True)
        # skmo.sk pages use windows-1250 encoding
        response.encoding = "windows-1250"
        output_file.write_text(response.text, encoding="utf-8")
        return output_file

    # For 2015, team data is on the same page as individual results
    if year == 2015:
        url = SPECIAL_URLS[2015]
        verify_ssl = False
    else:
        url = f"{BASE_URL}/{year}/team/"
        verify_ssl = True

    try:
        response = requests.get(url, timeout=30, verify=verify_ssl)
        response.raise_for_status()
    except requests.RequestException as e:
        raise DownloadError(f"Failed to download MEMO team {year}: {e}") from e

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_text(response.content.decode("utf-8"), encoding="utf-8")

    return output_file
