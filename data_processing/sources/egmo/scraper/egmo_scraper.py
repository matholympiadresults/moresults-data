#!/usr/bin/env python3
"""
EGMO Results Scraper

Scrapes EGMO (European Girls' Mathematical Olympiad) results from egmo.org.

Supports two modes:
1. download - Downloads raw HTML and CSV files
2. parse - Parses raw files into structured JSON
"""

import csv
import re
from datetime import datetime
from io import StringIO
from pathlib import Path

import httpx

from .models import ContestantResult, EGMOYearResults, ValidationResult

# EGMO started in 2012
FIRST_EGMO_YEAR = 2012


class ScraperError(Exception):
    """Raised when scraping fails unexpectedly."""

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


# --- Download functions ---


def download_raw(year: int, raw_data_dir: Path, force: bool = False) -> tuple[Path, Path]:
    """Download raw HTML and CSV files for a given EGMO year.

    Args:
        year: The competition year (e.g., 2024)
        raw_data_dir: Directory to store raw files
        force: If True, re-download even if files exist

    Returns:
        Tuple of (html_path, csv_path)

    Raises:
        ScraperError: If download fails
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
        raise ScraperError(f"Failed to download EGMO {year}: HTTP {e.response.status_code}") from e
    except Exception as e:
        raise ScraperError(f"Failed to download EGMO {year}: {e}") from e

    return html_file, csv_file


# --- Parse functions ---


def scrape_person_ids(html_content: str) -> dict[str, int]:
    """Extract contestant_code -> person_id mapping from scoreboard HTML."""
    # Pattern matches: <a href="/people/person123/">CODE</a>
    # where CODE is a contestant code like BEL1, BGR2, TURB1, etc.
    # Country codes can be 3-4 letters (e.g., USA, TURB for Turkey B team)
    pattern = r'<a href="/people/person(\d+)/">([A-Z]{3,4}\d+)</a>'
    matches = re.findall(pattern, html_content)

    person_ids = {}
    for person_id, contestant_code in matches:
        person_ids[contestant_code] = int(person_id)

    return person_ids


def parse_optional_int(value: str) -> int | None:
    """Parse a string to int, returning None for empty strings."""
    value = value.strip()
    return int(value) if value else None


def parse_award(value: str) -> str | None:
    """Parse award string, returning None for empty strings."""
    value = value.strip()
    return value if value else None


def parse_raw(year: int, html_file: Path, csv_file: Path) -> EGMOYearResults:
    """Parse raw HTML and CSV files into structured data.

    Args:
        year: The competition year
        html_file: Path to the HTML file
        csv_file: Path to the CSV file

    Returns:
        EGMOYearResults with all contestant data
    """
    edition = year_to_edition(year)

    # Read files
    html_content = html_file.read_text(encoding="utf-8")
    csv_content = csv_file.read_text(encoding="utf-8")

    # Extract person IDs from HTML
    person_ids = scrape_person_ids(html_content)

    # Parse CSV
    # Remove BOM if present
    csv_content = csv_content.lstrip("\ufeff")
    reader = csv.DictReader(StringIO(csv_content))

    results = []
    num_problems = 0

    for row in reader:
        # Extract problem scores (P1-P8 or however many exist)
        problem_scores = []
        for i in range(1, 9):
            key = f"P{i}"
            if key in row:
                problem_scores.append(parse_optional_int(row[key]))
                num_problems = max(num_problems, i)

        contestant_code = row["Contestant Code"]

        # Get person_id from HTML scraping (fallback to 0 if not found)
        person_id = person_ids.get(contestant_code, 0)

        contestant = ContestantResult(
            person_id=person_id,
            country_name=row["Country Name"],
            country_code=row["Country Code"],
            contestant_code=contestant_code,
            given_name=row["Given Name"],
            family_name=row["Family Name"],
            problem_scores=problem_scores,
            total=int(row["Total"]),
            rank=parse_optional_int(row.get("Rank", "")),
            european_rank=parse_optional_int(row.get("European Rank", "")),
            award=parse_award(row.get("Award", "")),
            extra_awards=row.get("Extra Awards", "").strip() or None,
        )
        results.append(contestant)

    # Validate totals
    mismatches = validate_totals(results)

    return EGMOYearResults(
        year=year,
        edition=edition,
        source_url=f"https://www.egmo.org/egmos/egmo{edition}/scoreboard/",
        total_contestants=len(results),
        num_problems=num_problems,
        results=results,
        validation=ValidationResult(
            all_totals_match=len(mismatches) == 0,
            mismatches=mismatches,
        ),
    )


def validate_totals(results: list[ContestantResult]) -> list[dict]:
    """Validate that totals match sum of individual scores. Returns mismatches."""
    mismatches = []
    for r in results:
        valid_scores = [s for s in r.problem_scores if s is not None]
        calculated = sum(valid_scores)
        if calculated != r.total:
            mismatches.append(
                {
                    "name": r.full_name,
                    "country": r.country_code,
                    "calculated": calculated,
                    "reported": r.total,
                }
            )
    return mismatches


def save_json(data: EGMOYearResults, filepath: Path) -> None:
    """Save results to JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(data.model_dump_json(indent=2))


def scrape_year(year: int, raw_data_dir: Path, force: bool = False) -> EGMOYearResults:
    """Download and parse results for a single year.

    This is a convenience function that combines download_raw and parse_raw.

    Args:
        year: The competition year
        raw_data_dir: Directory to store raw files
        force: If True, re-download even if files exist

    Returns:
        EGMOYearResults with all contestant data
    """
    html_file, csv_file = download_raw(year, raw_data_dir, force=force)
    return parse_raw(year, html_file, csv_file)
