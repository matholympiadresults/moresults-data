"""
IMO Parse Module

Parses raw HTML pages into structured data.
This is the second stage of the data pipeline: download -> parse -> ingest.
"""

import json
import re
from pathlib import Path

import click
from bs4 import BeautifulSoup
from pydantic import BaseModel


class ProblemScores(BaseModel):
    """Scores for IMO problems (typically 6, but some years have 7)."""

    p1: int | None
    p2: int | None
    p3: int | None
    p4: int | None
    p5: int | None
    p6: int | None
    p7: int | None = None  # Only used in 1960 and 1962


class ContestantResult(BaseModel):
    """Individual contestant result."""

    contestant_id: int | None
    name: str | None
    country_code: str
    scores: ProblemScores
    total: int
    rank: int | None
    award: str | None


class ValidationResult(BaseModel):
    """Validation results for parsed data."""

    all_totals_match: bool
    mismatches: list[dict]


class IMOYearResults(BaseModel):
    """Complete results for a single IMO year."""

    year: int
    total_contestants: int
    results: list[ContestantResult]
    validation: ValidationResult


# Years with different max score per problem (default is 7)
MAX_SCORE_BY_YEAR: dict[int, int] = {
    1959: 8,
    1960: 8,
    1962: 8,
    1963: 8,
    1964: 9,
    1965: 9,
    1966: 8,
    1967: 8,
    1968: 8,
    1969: 8,
    1970: 8,
    1971: 9,
    1972: 8,
    1973: 8,
    1974: 8,
    1975: 8,
    1976: 8,
    1977: 8,
    1978: 8,
}

# Years that allow empty scores (stored as None)
ALLOW_EMPTY_SCORES_YEARS: set[int] = {
    1959,
    1960,
    1961,
    1962,
    1963,
    1964,
    1966,
    1967,
    1968,
    1970,
    1971,
    1972,
    1975,
    1977,
    1978,
    1980,
    1981,
    1983,
    1992,
}

# Years that allow empty contestant names
ALLOW_EMPTY_NAMES_YEARS: set[int] = {1959}

# Years that allow empty ranks
ALLOW_EMPTY_RANKS_YEARS: set[int] = {1992}

# Years that allow unknown person rows (rows with '?' or '*' instead of contestant link)
ALLOW_UNKNOWN_PERSON_YEARS: set[int] = {
    1959,
    1960,
    1961,
    1962,
    1963,
    1964,
    1966,
    1967,
    1970,
    1971,
    1972,
    1975,
    1979,
    1980,
    1981,
    1986,
    2003,
    2004,
    2005,
}

# Years with different number of problems (default is 6)
NUM_PROBLEMS_BY_YEAR: dict[int, int] = {
    1960: 7,
    1962: 7,
}

# Sentinel for unknown persons
UNKNOWN_PERSON = "UNKNOWN_PERSON"


class ParseError(Exception):
    """Raised when parsing fails unexpectedly."""

    pass


def parse_html(html: str, year: int) -> list[ContestantResult]:
    """
    Parse the HTML and extract contestant results.

    Args:
        html: Raw HTML content
        year: The IMO year (used for year-specific validation rules)

    Returns:
        List of contestant results

    Raises:
        ParseError: If unexpected data is encountered
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Find the main results table
    table = soup.find("table", class_="table_results")
    if not table:
        # Fallback: find any table with contestant data
        tables = soup.find_all("table")
        for t in tables:
            if t.find("a", href=re.compile(r"participant_r\.aspx\?id=")):
                table = t
                break

    if not table:
        raise ParseError(f"Could not find results table in HTML for year {year}")

    rows = table.find_all("tr")

    for row_idx, row in enumerate(rows):
        cells = row.find_all("td")

        # Skip rows with no cells (likely header rows with <th>)
        if len(cells) == 0:
            continue

        # Check if this is a header row (contains <th> elements)
        if row.find("th"):
            continue

        # Check for contestant link - if not present, this might be a header or separator row
        contestant_link = cells[0].find("a", href=re.compile(r"participant_r\.aspx\?id="))
        is_unknown_person = False
        if not contestant_link:
            # Check if first cell is empty or contains only whitespace
            first_cell_text = cells[0].get_text(strip=True)
            if not first_cell_text:
                continue
            # Check for unknown person marker '?' or '*'
            if first_cell_text in ("?", "*") and year in ALLOW_UNKNOWN_PERSON_YEARS:
                is_unknown_person = True
            else:
                raise ParseError(
                    f"Year {year}, row {row_idx}: Found row with {len(cells)} cells "
                    f"but no contestant link. First cell: {first_cell_text!r}."
                )

        # Expected cells: name, country, p1-pN, total, rank, award
        num_problems = NUM_PROBLEMS_BY_YEAR.get(year, 6)
        expected_cells = 2 + num_problems + 3  # name, country, problems, total, rank, award
        if len(cells) != expected_cells:
            raise ParseError(
                f"Year {year}, row {row_idx}: Expected {expected_cells} cells, got {len(cells)}. "
                f"Contestant: {contestant_link.get_text(strip=True) if contestant_link else 'unknown'}"
            )

        # Extract contestant ID and name
        if is_unknown_person:
            contestant_id = None
            name = UNKNOWN_PERSON
        else:
            href = contestant_link.get("href", "")
            id_match = re.search(r"id=(\d+)", href)
            if not id_match:
                raise ParseError(
                    f"Year {year}, row {row_idx}: Could not extract contestant ID from href: {href}"
                )
            contestant_id = int(id_match.group(1))

            name = contestant_link.get_text(strip=True)
            if not name:
                if year not in ALLOW_EMPTY_NAMES_YEARS:
                    raise ParseError(f"Year {year}, row {row_idx}: Empty contestant name")
                name = None

        # Extract country code
        country_cell = cells[1]
        country_link = country_cell.find("a")
        if country_link:
            country_href = country_link.get("href", "")
            code_match = re.search(r"code=([A-Za-z0-9]+)", country_href)
            if not code_match:
                raise ParseError(
                    f"Year {year}, row {row_idx}: Could not extract country code from href: {country_href}"
                )
            country_code = code_match.group(1)
        else:
            country_code = country_cell.get_text(strip=True)
            if not country_code:
                raise ParseError(f"Year {year}, row {row_idx}: Empty country code for {name}")

        # Extract problem scores (cells 2 to 2+num_problems)
        score_values: list[int | None] = []
        for i in range(num_problems):
            score_text = cells[2 + i].get_text(strip=True)
            if not score_text:
                if year not in ALLOW_EMPTY_SCORES_YEARS:
                    raise ParseError(
                        f"Year {year}, row {row_idx}: Empty score for P{i + 1}, contestant {name}"
                    )
                score_values.append(None)
                continue
            try:
                score = int(score_text)
            except ValueError as err:
                raise ParseError(
                    f"Year {year}, row {row_idx}: Invalid score '{score_text}' for P{i + 1}, contestant {name}"
                ) from err
            max_score = MAX_SCORE_BY_YEAR.get(year, 7)
            if score < 0 or score > max_score:
                raise ParseError(
                    f"Year {year}, row {row_idx}: Score {score} out of range [0-{max_score}] for P{i + 1}, contestant {name}"
                )
            score_values.append(score)

        # Pad with None if fewer than 7 problems
        while len(score_values) < 7:
            score_values.append(None)

        scores = ProblemScores(
            p1=score_values[0],
            p2=score_values[1],
            p3=score_values[2],
            p4=score_values[3],
            p5=score_values[4],
            p6=score_values[5],
            p7=score_values[6],
        )

        # Extract total, rank, award (after problem scores)
        total_idx = 2 + num_problems
        rank_idx = total_idx + 1
        award_idx = total_idx + 2

        total_text = cells[total_idx].get_text(strip=True)
        if not total_text:
            raise ParseError(f"Year {year}, row {row_idx}: Empty total for contestant {name}")
        try:
            total = int(total_text)
        except ValueError as err:
            raise ParseError(
                f"Year {year}, row {row_idx}: Invalid total '{total_text}' for contestant {name}"
            ) from err

        rank_text = cells[rank_idx].get_text(strip=True)
        if not rank_text:
            if year not in ALLOW_EMPTY_RANKS_YEARS:
                raise ParseError(f"Year {year}, row {row_idx}: Empty rank for contestant {name}")
            rank = None
        else:
            try:
                rank = int(rank_text)
            except ValueError as err:
                raise ParseError(
                    f"Year {year}, row {row_idx}: Invalid rank '{rank_text}' for contestant {name}"
                ) from err

        # Award can be empty
        award_text = cells[award_idx].get_text(strip=True)
        award = award_text if award_text else None

        results.append(
            ContestantResult(
                contestant_id=contestant_id,
                name=name,
                country_code=country_code,
                scores=scores,
                total=total,
                rank=rank,
                award=award,
            )
        )

    return results


def validate_totals(results: list[ContestantResult]) -> list[dict]:
    """Validate that totals match sum of individual scores. Returns mismatches."""
    mismatches = []
    for r in results:
        scores = [
            r.scores.p1,
            r.scores.p2,
            r.scores.p3,
            r.scores.p4,
            r.scores.p5,
            r.scores.p6,
            r.scores.p7,
        ]
        # Filter out None values (unused problems or missing scores)
        valid_scores = [s for s in scores if s is not None]
        # Skip validation if no valid scores
        if not valid_scores:
            continue
        calculated = sum(valid_scores)
        if calculated != r.total:
            mismatches.append(
                {
                    "contestant_id": r.contestant_id,
                    "name": r.name,
                    "calculated": calculated,
                    "reported": r.total,
                }
            )
    return mismatches


def parse_year(html: str, year: int) -> IMOYearResults:
    """
    Parse HTML for a single year and return structured data.

    Args:
        html: Raw HTML content
        year: The IMO year

    Returns:
        Structured year results with validation
    """
    results = parse_html(html, year)

    if not results:
        raise ParseError(f"No results found for year {year}. The year may not have data yet.")

    mismatches = validate_totals(results)

    return IMOYearResults(
        year=year,
        total_contestants=len(results),
        results=results,
        validation=ValidationResult(
            all_totals_match=len(mismatches) == 0,
            mismatches=mismatches,
        ),
    )


def save_json(data: IMOYearResults, output_path: Path) -> None:
    """Save parsed results to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data.model_dump(), f, indent=2, ensure_ascii=False)


def load_html(input_path: Path) -> str:
    """Load raw HTML from a file."""
    with open(input_path, encoding="utf-8") as f:
        return f.read()


def get_year_dir(base_dir: Path, year: int) -> Path:
    """Get the directory for a specific year."""
    return base_dir / str(year)


def get_raw_html_path(base_dir: Path, year: int) -> Path:
    """Get the path to the raw HTML file for a specific year."""
    return get_year_dir(base_dir, year) / "results.html"


def get_parsed_json_path(base_dir: Path, year: int) -> Path:
    """Get the path to the parsed JSON file for a specific year."""
    return get_year_dir(base_dir, year) / "results.json"


def discover_years(input_dir: Path) -> list[int]:
    """
    Discover available years from yearly directory structure.

    Looks for directories like input_dir/2024/results.html
    """
    years = []
    for year_dir in input_dir.iterdir():
        if year_dir.is_dir() and year_dir.name.isdigit():
            html_path = year_dir / "results.html"
            if html_path.exists():
                years.append(int(year_dir.name))
    return sorted(years)


def parse_years(
    input_dir: Path,
    output_dir: Path,
    years: list[int] | None = None,
    force: bool = False,
) -> dict[str, int]:
    """
    Parse raw HTML files into structured JSON.

    Expects yearly directory structure:
        imo/raw/2024/results.html -> imo/parsed/2024/results.json
        imo/raw/2023/results.html -> imo/parsed/2023/results.json
        ...

    Args:
        input_dir: Base directory containing yearly subdirectories with results.html
        output_dir: Base directory to save parsed JSON files
        years: Specific years to parse (None = all available)
        force: Re-parse even if output file exists

    Returns:
        Stats dict with success/failure counts
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    stats = {"success": 0, "skipped": 0, "failed": 0}

    # Discover available years
    available_years = discover_years(input_dir)

    if not available_years:
        click.echo(f"No yearly directories with results.html found in {input_dir}", err=True)
        return stats

    # Filter to requested years
    target_years = available_years
    if years is not None:
        target_years = [y for y in available_years if y in years]

    for year in target_years:
        html_path = get_raw_html_path(input_dir, year)
        output_path = get_parsed_json_path(output_dir, year)

        if output_path.exists() and not force:
            click.echo(f"  {year}: Already parsed, skipping")
            stats["skipped"] += 1
            continue

        try:
            html = load_html(html_path)
            data = parse_year(html, year)
            save_json(data, output_path)
            click.echo(f"  {year}: Parsed {data.total_contestants} contestants")
            stats["success"] += 1

        except ParseError as e:
            click.echo(f"  {year}: {e}", err=True)
            stats["failed"] += 1
        except Exception as e:
            click.echo(f"  {year}: Unexpected error - {e}", err=True)
            stats["failed"] += 1

    return stats
