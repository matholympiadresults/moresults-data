"""Baltic Way 2026 Downloader

Downloads the results page from bw2026.lt (37th Baltic Way, Vilnius, Lithuania).
"""

from pathlib import Path

import requests

RESULTS_URL = "https://bw2026.lt/results"


class DownloadError(Exception):
    """Raised when download fails."""

    pass


def get_raw_filename() -> str:
    """Get the filename for the raw HTML file."""
    return "results.html"


def download_2026(output_dir: Path, force: bool = False) -> Path:
    """Download the Baltic Way 2026 results page.

    Args:
        output_dir: Directory to save the raw HTML
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
        response = requests.get(RESULTS_URL, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise DownloadError(f"Failed to download Baltic Way 2026: {e}") from e

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_text(response.text, encoding="utf-8")

    return output_file
