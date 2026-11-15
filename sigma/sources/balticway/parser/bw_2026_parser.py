"""Baltic Way 2026 Parser

Parses the bw2026.lt results page. The site (Zyro/Astro) renders the table
client-side, so the raw page only contains it as an HTML string inside the
JSON-serialized props of an <astro-island> element.

Table rows: rank (td) + team name (th, with a flag emoji span) + 20 scores + sum.
"""

import json
from pathlib import Path

from bs4 import BeautifulSoup

from .models import BWYearResults, TeamResult, ValidationResult


class ParserError(Exception):
    """Raised when parsing fails unexpectedly."""

    pass


def get_parsed_filename() -> str:
    """Get the filename for a parsed JSON file."""
    return "scoreboard.json"


def _find_string_containing(value, needle: str) -> str | None:
    """Recursively search a JSON value for a string containing needle."""
    if isinstance(value, str):
        return value if needle in value else None
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        for item in value:
            found = _find_string_containing(item, needle)
            if found is not None:
                return found
    return None


def extract_table_html(html: str) -> str:
    """Extract the embedded results table HTML from the page's Astro props."""
    soup = BeautifulSoup(html, "html.parser")

    for island in soup.find_all(attrs={"props": True}):
        props = island["props"]
        if "<table" not in props:
            continue
        found = _find_string_containing(json.loads(props), "<table")
        if found is not None:
            return found

    raise ParserError("Could not find embedded results table for Baltic Way 2026")


def parse_html(html: str) -> list[TeamResult]:
    """Parse the results page and extract team results."""
    table = BeautifulSoup(extract_table_html(html), "html.parser").find("table")
    if table is None:
        raise ParserError("Could not parse embedded results table for Baltic Way 2026")

    results = []
    for row in table.find("tbody").find_all("tr"):
        team_cell = row.find("th")
        flag = team_cell.find(class_="results-flag")
        if flag is not None:
            flag.decompose()
        team_name = team_cell.get_text(strip=True)

        tds = [td.get_text(strip=True) for td in row.find_all("td")]
        # rank + 20 scores + sum
        if len(tds) != 22:
            raise ParserError(f"Unexpected row for {team_name!r}: {len(tds)} cells")

        results.append(
            TeamResult(
                team_name=team_name,
                problem_scores=[int(s) for s in tds[1:21]],
                total=int(tds[21]),
                rank=0,  # Placeholder, computed later
            )
        )

    if not results:
        raise ParserError("No results found for Baltic Way 2026")

    return results


def _compute_ranks(results: list[TeamResult]) -> list[TeamResult]:
    """Compute competition-style ranks from totals (ties get same rank)."""
    sorted_results = sorted(results, key=lambda r: r.total, reverse=True)
    ranked = []
    for i, result in enumerate(sorted_results):
        if i == 0 or result.total < sorted_results[i - 1].total:
            rank = i + 1
        ranked.append(result.model_copy(update={"rank": rank}))
    return ranked


def validate_totals(results: list[TeamResult]) -> list[dict]:
    """Validate that totals match sum of problem scores. Returns mismatches."""
    mismatches = []
    for r in results:
        calculated = sum(r.problem_scores)
        if calculated != r.total:
            mismatches.append(
                {
                    "team_name": r.team_name,
                    "calculated": calculated,
                    "reported": r.total,
                }
            )
    return mismatches


def parse_2026(raw_dir: Path, output_dir: Path, force: bool = False) -> Path:
    """Parse the Baltic Way 2026 results page and save as structured JSON.

    Args:
        raw_dir: Directory containing raw HTML file (2026 year subdirectory)
        output_dir: Directory to save parsed JSON (2026 year subdirectory)
        force: If True, re-parse even if output file exists

    Returns:
        Path to the parsed JSON file

    Raises:
        ParserError: If parsing fails
        FileNotFoundError: If raw HTML file doesn't exist
    """
    from sigma.sources.balticway.downloader.bw_2026_downloader import (
        get_raw_filename,
    )

    raw_file = raw_dir / get_raw_filename()
    output_file = output_dir / get_parsed_filename()

    if output_file.exists() and not force:
        return output_file

    if not raw_file.exists():
        raise FileNotFoundError(f"Raw HTML file not found: {raw_file}")

    results = _compute_ranks(parse_html(raw_file.read_text(encoding="utf-8")))
    mismatches = validate_totals(results)

    year_results = BWYearResults(
        year=2026,
        num_teams=len(results),
        results=results,
        validation=ValidationResult(
            all_totals_match=len(mismatches) == 0,
            mismatches=mismatches,
        ),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_text(year_results.model_dump_json(indent=2), encoding="utf-8")

    return output_file
