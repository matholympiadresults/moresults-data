#!/usr/bin/env python3
"""
MEMO 2011 Downloader

Downloads the results page from memo2011.math.hr (5th MEMO, Varaždin, Croatia).
"""

from pathlib import Path

import requests

BASE_URL = "https://memo2011.math.hr"
RESULTS_URL = f"{BASE_URL}/index.php?option=com_content&view=article&id=16&Itemid=36&lang=en"


class DownloadError(Exception):
    """Raised when download fails."""

    pass


def download_2011(output_dir: Path, force: bool = False) -> Path:
    """
    Download the MEMO 2011 results page.

    Args:
        output_dir: Directory to save the raw HTML
        force: If True, re-download even if file exists

    Returns:
        Path to the downloaded file
    """
    output_file = output_dir / "results.html"

    if output_file.exists() and not force:
        return output_file

    try:
        response = requests.get(RESULTS_URL, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise DownloadError(f"Failed to download MEMO 2011: {e}") from e

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_text(response.text, encoding="utf-8")

    return output_file
