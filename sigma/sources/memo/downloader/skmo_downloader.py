#!/usr/bin/env python3
"""
MEMO Legacy Downloader

Downloads raw HTML pages from web.archive.org (skmo.sk) for MEMO 2007-2015.
These years are not available on memo-official.org.
"""

from pathlib import Path

import requests

# Archive.org URL pattern for skmo.sk MEMO results
# rocnik = year in Slovak MO numbering (rocnik 56 = 2006/2007 = MEMO 1)
# MEMO started in 2007 (edition 1) which corresponds to rocnik 56
ARCHIVE_URL_TEMPLATE = (
    "https://web.archive.org/web/20240623010205/"
    "https://skmo.sk/poradia.php?jazyk=en&rocnik={rocnik}&sutaz=_MEMO"
)

# MEMO edition to Slovak MO rocnik mapping
# MEMO 1 (2007) = rocnik 56, MEMO 4 (2010) = rocnik 59, etc.
MEMO_START_ROCNIK = 56  # rocnik for MEMO 1 (2007)
MEMO_START_YEAR = 2007


class DownloadError(Exception):
    """Raised when download fails."""

    pass


def year_to_rocnik(year: int) -> int:
    """Convert MEMO year to Slovak MO rocnik number."""
    edition = year - MEMO_START_YEAR + 1
    return MEMO_START_ROCNIK + edition - 1


def get_raw_filename(year: int) -> str:
    """Get the filename for a raw HTML file."""
    return f"skmo_{year}.html"


def download_year(year: int, output_dir: Path, force: bool = False) -> Path:
    """
    Download the MEMO results page HTML from archive.org for a given year.

    Args:
        year: The year to download (2007-2015)
        output_dir: Directory to save the raw HTML
        force: If True, re-download even if file exists

    Returns:
        Path to the downloaded file

    Raises:
        DownloadError: If download fails
    """
    output_file = output_dir / get_raw_filename(year)

    if output_file.exists() and not force:
        return output_file

    rocnik = year_to_rocnik(year)
    url = ARCHIVE_URL_TEMPLATE.format(rocnik=rocnik)

    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
    except requests.RequestException as e:
        raise DownloadError(f"Failed to download MEMO {year}: {e}") from e

    output_dir.mkdir(parents=True, exist_ok=True)
    # The page uses windows-1250 encoding as declared in meta tag
    # We need to decode with windows-1250 and save as UTF-8
    response.encoding = "windows-1250"
    output_file.write_text(response.text, encoding="utf-8")

    return output_file
