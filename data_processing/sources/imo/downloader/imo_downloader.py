"""
IMO Download Module

Downloads raw HTML pages from imo-official.org.
This is the first stage of the data pipeline: download -> parse -> ingest.
"""

import time
from pathlib import Path

import click
import requests

BASE_URL = "https://www.imo-official.org/year_individual_r.aspx"

# IMO has been held since 1959 (except 1980)
FIRST_IMO_YEAR = 1959


class DownloadError(Exception):
    """Raised when download fails."""

    pass


def download_year(year: int, timeout: int = 30) -> str:
    """
    Download the raw HTML results page for a given year.

    Args:
        year: The IMO year to download
        timeout: Request timeout in seconds

    Returns:
        Raw HTML content as string

    Raises:
        DownloadError: If the download fails
    """
    url = f"{BASE_URL}?year={year}"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        raise DownloadError(f"Failed to download year {year}: {e}") from e


def save_raw_html(html: str, output_path: Path) -> None:
    """Save raw HTML to a file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def get_year_dir(base_dir: Path, year: int) -> Path:
    """Get the directory for a specific year."""
    return base_dir / str(year)


def get_raw_html_path(base_dir: Path, year: int) -> Path:
    """Get the path to the raw HTML file for a specific year."""
    return get_year_dir(base_dir, year) / "results.html"


def download_years(
    output_dir: Path,
    years: list[int],
    delay: float = 1.0,
    force: bool = False,
) -> dict[str, int]:
    """
    Download raw HTML for multiple years.

    Files are saved in yearly directories:
        imo/raw/2024/results.html
        imo/raw/2023/results.html
        ...

    Args:
        output_dir: Base directory to save HTML files
        years: List of years to download
        delay: Delay between requests in seconds
        force: Re-download even if file exists

    Returns:
        Stats dict with success/failure counts
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    stats = {"success": 0, "skipped": 0, "failed": 0}

    for year in years:
        output_path = get_raw_html_path(output_dir, year)

        if output_path.exists() and not force:
            click.echo(f"  {year}: Already exists, skipping")
            stats["skipped"] += 1
            continue

        try:
            html = download_year(year)
            save_raw_html(html, output_path)
            click.echo(f"  {year}: Downloaded ({len(html):,} bytes)")
            stats["success"] += 1

            # Be nice to the server
            if year != years[-1]:
                time.sleep(delay)

        except DownloadError as e:
            click.echo(f"  {year}: {e}", err=True)
            stats["failed"] += 1

    return stats
