#!/usr/bin/env python3
"""
MEMO 2009 Downloader

Downloads the MEMO 2009 individual results HTML from memo2009.wmi.amu.edu.pl.
"""

from pathlib import Path

import requests

MEMO_2009_RESULTS_URL = "https://www.memo2009.wmi.amu.edu.pl/dane/results.html"


class DownloadError(Exception):
    """Raised when download fails."""

    pass


def get_raw_filename() -> str:
    """Get the filename for the raw HTML file."""
    return "results.html"


def download_2009(output_dir: Path, force: bool = False) -> Path:
    """
    Download the MEMO 2009 results HTML.

    Args:
        output_dir: Directory to save the raw HTML (should be the 2009 year subdirectory)
        force: If True, re-download even if file exists

    Returns:
        Path to the downloaded file

    Raises:
        DownloadError: If download fails
    """
    output_file = output_dir / get_raw_filename()

    if output_file.exists() and not force:
        return output_file

    try:
        response = requests.get(MEMO_2009_RESULTS_URL, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise DownloadError(f"Failed to download MEMO 2009 HTML: {e}") from e

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_text(response.text, encoding="utf-8")

    return output_file
