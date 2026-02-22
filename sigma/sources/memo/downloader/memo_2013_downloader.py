#!/usr/bin/env python3
"""
MEMO 2013 Downloader

Downloads the MEMO 2013 individual results PDF from web.archive.org.
This is a separate source since MEMO 2013 data is not available on memo-official.org.
"""

from pathlib import Path

import requests

MEMO_2013_PDF_URL = (
    "https://web.archive.org/web/20201130004523/"
    "http://memo2013.mik.uni-pannon.hu/images/comprofiler/results/MEMO2013_results_individual.pdf"
)


class DownloadError(Exception):
    """Raised when download fails."""

    pass


def get_raw_filename() -> str:
    """Get the filename for the raw PDF file."""
    return "individual.pdf"


def download_2013(output_dir: Path, force: bool = False) -> Path:
    """
    Download the MEMO 2013 individual results PDF.

    Args:
        output_dir: Directory to save the raw PDF (should be the 2013 year subdirectory)
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
        response = requests.get(MEMO_2013_PDF_URL, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise DownloadError(f"Failed to download MEMO 2013 PDF: {e}") from e

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(response.content)

    return output_file
