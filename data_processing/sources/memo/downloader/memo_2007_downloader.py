#!/usr/bin/env python3
"""
MEMO 2007 Downloader

Downloads the XLS file from kag.upol.cz for the 1st MEMO (Eisenstadt, Austria).
"""

from pathlib import Path

import requests

XLS_URL = "https://kag.upol.cz/memo/texty/1sj_v.xls"


class DownloadError(Exception):
    """Raised when download fails."""

    pass


def download_2007(output_dir: Path, force: bool = False) -> Path:
    """
    Download the MEMO 2007 XLS file.

    Args:
        output_dir: Directory to save the raw XLS
        force: If True, re-download even if file exists

    Returns:
        Path to the downloaded file
    """
    output_file = output_dir / "individual.xls"

    if output_file.exists() and not force:
        return output_file

    try:
        response = requests.get(XLS_URL, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise DownloadError(f"Failed to download MEMO 2007: {e}") from e

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(response.content)

    return output_file
