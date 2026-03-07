"""
RMM Raw Data Downloader

Downloads raw HTML pages from rmms.lbi.ro for later parsing.
"""

from pathlib import Path

import requests

# URL pattern: rmms.lbi.ro/rmm{year}/index.php?id=results_math
BASE_URL_TEMPLATE = "https://rmms.lbi.ro/rmm{year}/index.php?id=results_math"

# RMM started in 2008 (edition 1)
RMM_START_YEAR = 2008

# Available years (may need updating as new competitions happen)
AVAILABLE_YEARS = list(range(2008, 2027))


class DownloadError(Exception):
    """Raised when downloading fails."""

    pass


def fetch_page(year: int) -> str:
    """Fetch the results page HTML for a given year.

    Args:
        year: The competition year to fetch

    Returns:
        Raw HTML content as a string

    Raises:
        DownloadError: If the request fails
    """
    url = BASE_URL_TEMPLATE.format(year=year)
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        # The server doesn't specify charset in Content-Type header, causing requests
        # to default to ISO-8859-1. The HTML meta tag and actual content are UTF-8.
        response.encoding = "utf-8"
        return response.text
    except requests.RequestException as e:
        raise DownloadError(f"Failed to download RMM {year}: {e}") from e


def download_year(year: int, output_dir: Path, force: bool = False) -> Path:
    """Download raw HTML for a single year.

    Args:
        year: The competition year to download
        output_dir: Directory to save the HTML file
        force: If True, re-download even if file exists

    Returns:
        Path to the saved HTML file

    Raises:
        DownloadError: If the download fails
    """
    output_file = output_dir / f"rmm_{year}.html"

    if output_file.exists() and not force:
        return output_file

    html = fetch_page(year)
    output_file.write_text(html, encoding="utf-8")
    return output_file
