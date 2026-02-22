"""EGMO parser - parses raw HTML and CSV files into structured data."""

import csv
import re
from io import StringIO
from pathlib import Path

from ..downloader import year_to_edition
from .models import ContestantResult, EGMOYearResults, ValidationResult


class ParseError(Exception):
    """Raised when parsing fails unexpectedly."""

    pass


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
