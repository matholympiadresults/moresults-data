#!/usr/bin/env python3
"""
MEMO 2008 Downloader

Downloads the MEMO 2008 (2nd edition) individual results XLS from kag.upol.cz.
"""

from pathlib import Path

import requests

MEMO_2008_RESULTS_URL = "https://kag.upol.cz/memo/texty/2sj_v1.xls"


class DownloadError(Exception):
    """Raised when download fails."""

    pass


def get_raw_filename() -> str:
    """Get the filename for the raw XLS file."""
    return "results.xls"


def download_2008(output_dir: Path, force: bool = False) -> Path:
    """
    Download the MEMO 2008 results XLS.

    Args:
        output_dir: Directory to save the raw XLS (should be the 2008 year subdirectory)
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
        response = requests.get(MEMO_2008_RESULTS_URL, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise DownloadError(f"Failed to download MEMO 2008 XLS: {e}") from e

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(response.content)

    return output_file
