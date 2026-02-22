"""APMO downloader - fetches raw HTML files from apmo-official.org.

Stage 1 of the pipeline: downloads year_report.html and per-country HTML files.
"""

import re
from pathlib import Path

import httpx
from bs4 import BeautifulSoup


class DownloadError(Exception):
    """Raised when downloading fails unexpectedly."""

    pass


def fetch_year_report(year: int) -> str:
    """Fetch the year report page to get list of participating countries."""
    url = f"https://www.apmo-official.org/year_report/{year}"
    with httpx.Client() as client:
        response = client.get(url, timeout=30)
        response.raise_for_status()
    return response.text


def fetch_country_report(country_code: str, year: int) -> str:
    """Fetch detailed results for a specific country."""
    url = f"https://www.apmo-official.org/country_report/{country_code}/{year}"
    with httpx.Client() as client:
        response = client.get(url, timeout=30)
        response.raise_for_status()
    return response.text


def extract_countries_from_year_report(html: str) -> list[tuple[str, str]]:
    """Extract country codes and names from year report page.

    Returns list of (country_code, country_name) tuples, deduplicated.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen = {}  # code -> name mapping to deduplicate

    # Find all country links in the ranking table
    # Pattern: /country_report/CODE/YEAR
    for link in soup.find_all("a", href=re.compile(r"/country_report/([A-Z]+)/\d+")):
        href = link.get("href", "")
        match = re.search(r"/country_report/([A-Z]+)/", href)
        if match:
            code = match.group(1)
            name = link.get_text(strip=True)
            if code and name and code not in seen:
                seen[code] = name

    return list(seen.items())


def download_raw_year(year: int, raw_dir: Path, force: bool = False) -> list[Path]:
    """Download raw HTML files for a given APMO year.

    Downloads:
    - year_report.html: Contains list of participating countries
    - {country_code}.html: Individual country result pages

    Args:
        year: Competition year
        raw_dir: Directory to save raw files (should be raw/{year}/)
        force: If True, overwrite existing files

    Returns:
        List of paths to downloaded files
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []

    # Download year report
    year_report_path = raw_dir / "year_report.html"
    if force or not year_report_path.exists():
        html = fetch_year_report(year)
        year_report_path.write_text(html, encoding="utf-8")
        downloaded.append(year_report_path)

    # Extract countries from year report
    year_html = year_report_path.read_text(encoding="utf-8")
    countries = extract_countries_from_year_report(year_html)

    if not countries:
        raise DownloadError(f"No countries found for APMO {year}")

    # Download each country report
    for country_code, _country_name in countries:
        country_path = raw_dir / f"{country_code}.html"
        if force or not country_path.exists():
            try:
                html = fetch_country_report(country_code, year)
                country_path.write_text(html, encoding="utf-8")
                downloaded.append(country_path)
            except Exception as e:
                print(f"  Warning: Failed to fetch {country_code}: {e}")

    return downloaded
