"""EGMO downloader - downloads raw HTML and CSV files from egmo.org."""

from datetime import datetime
from pathlib import Path

import httpx

# EGMO started in 2012
FIRST_EGMO_YEAR = 2012


class DownloadError(Exception):
    """Raised when downloading fails unexpectedly."""

    pass


def year_to_edition(year: int) -> int:
    """Convert calendar year to EGMO edition number."""
    return year - FIRST_EGMO_YEAR + 1


def edition_to_year(edition: int) -> int:
    """Convert EGMO edition number to calendar year."""
    return edition + FIRST_EGMO_YEAR - 1


def get_latest_edition() -> int:
    """Calculate the latest EGMO edition based on current year."""
    return year_to_edition(datetime.now().year)


def get_available_years() -> list[int]:
    """Get list of all available EGMO years."""
    return list(range(FIRST_EGMO_YEAR, datetime.now().year + 1))


def download_raw(year: int, raw_data_dir: Path, force: bool = False) -> tuple[Path, Path]:
    """Download raw HTML and CSV files for a given EGMO year.

    Args:
        year: The competition year (e.g., 2024)
        raw_data_dir: Directory to store raw files
        force: If True, re-download even if files exist

    Returns:
        Tuple of (html_path, csv_path)

    Raises:
        DownloadError: If download fails
    """
    edition = year_to_edition(year)
    base_url = f"https://www.egmo.org/egmos/egmo{edition}/scoreboard"

    html_file = raw_data_dir / str(year) / f"egmo_{year}_scoreboard.html"
    csv_file = raw_data_dir / str(year) / f"egmo_{year}_scores.csv"

    # Skip if already exists and not forcing
    if html_file.exists() and csv_file.exists() and not force:
        return html_file, csv_file

    # Create year subdirectory
    html_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with httpx.Client() as client:
            # Download HTML (for person IDs)
            html_response = client.get(f"{base_url}/")
            html_response.raise_for_status()
            html_file.write_text(html_response.text, encoding="utf-8")

            # Download CSV (for scores)
            csv_response = client.get(f"{base_url}/scores.csv")
            csv_response.raise_for_status()
            csv_file.write_text(csv_response.text, encoding="utf-8")

    except httpx.HTTPStatusError as e:
        raise DownloadError(f"Failed to download EGMO {year}: HTTP {e.response.status_code}") from e
    except Exception as e:
        raise DownloadError(f"Failed to download EGMO {year}: {e}") from e

    return html_file, csv_file
