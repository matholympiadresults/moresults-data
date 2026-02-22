"""Baltic Way Downloader

Downloads results pages (HTML or PDF) from math.olympiaadid.ut.ee.

URL patterns:
- 1992-2019: https://www.math.olympiaadid.ut.ee/eng/html/bw/bw{YY}_res.html
- 2020-2023, 2025: https://www.math.olympiaadid.ut.ee/eng/html/bw/bw{YY}_res.pdf
- 2024: https://bw2024.olympiaadid.ut.ee/results (external HTML)
"""

from pathlib import Path

import requests

BASE_URL = "https://www.math.olympiaadid.ut.ee/eng/html/bw"

# Years where results are available as PDF
PDF_YEARS = {2020, 2021, 2022, 2023, 2025}

# 2024 is hosted on a separate site
EXTERNAL_YEARS = {
    2024: "https://bw2024.olympiaadid.ut.ee/results",
}

# All years with results available online (1990-1991 have no results links)
AVAILABLE_YEARS = list(range(1992, 2026))


class DownloadError(Exception):
    """Raised when download fails."""

    pass


def _get_url(year: int) -> str:
    """Get the download URL for a given year."""
    if year in EXTERNAL_YEARS:
        return EXTERNAL_YEARS[year]

    yy = f"{year % 100:02d}"
    ext = "pdf" if year in PDF_YEARS else "html"
    return f"{BASE_URL}/bw{yy}_res.{ext}"


def _get_filename(year: int) -> str:
    """Get the output filename for a given year."""
    if year in EXTERNAL_YEARS:
        return "results.html"
    return "results.pdf" if year in PDF_YEARS else "results.html"


def download_year(year: int, output_dir: Path, force: bool = False) -> Path:
    """Download the results page for a given year.

    Args:
        year: The year to download
        output_dir: Directory to save the file
        force: If True, re-download even if file exists

    Returns:
        Path to the downloaded file

    Raises:
        DownloadError: If download fails
    """
    filename = _get_filename(year)
    output_file = output_dir / filename

    if output_file.exists() and not force:
        return output_file

    url = _get_url(year)

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise DownloadError(f"Failed to download Baltic Way {year}: {e}") from e

    output_dir.mkdir(parents=True, exist_ok=True)

    if year in PDF_YEARS:
        output_file.write_bytes(response.content)
    else:
        output_file.write_text(response.text, encoding="utf-8")

    return output_file
