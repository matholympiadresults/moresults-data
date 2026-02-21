#!/usr/bin/env python3
"""
MEMO 2009 Parser

Parses the MEMO 2009 individual results HTML into structured data.
"""

import html
import json
from pathlib import Path

from bs4 import BeautifulSoup

from .models import ContestantResult, MEMOYearResults, ValidationResult

# Country name mapping (MEMO 2009 uses full names)
COUNTRY_NAME_MAP = {
    "Austria": "Austria",
    "Croatia": "Croatia",
    "Czech Republic": "Czech Republic",
    "Germany": "Germany",
    "Hungary": "Hungary",
    "Lithuania": "Lithuania",
    "Poland": "Poland",
    "Slovakia": "Slovakia",
    "Slovenia": "Slovenia",
    "Switzerland": "Switzerland",
}

# Award mapping
AWARD_MAP = {
    "gold": "Gold",
    "silver": "Silver",
    "bronze": "Bronze",
}


class ParserError(Exception):
    """Raised when parsing fails unexpectedly."""

    pass


def get_parsed_filename() -> str:
    """Get the filename for a parsed JSON file."""
    return "scoreboard.json"


def clean_text(text: str) -> str:
    """Clean HTML entities and extra whitespace from text."""
    # Decode HTML entities
    text = html.unescape(text)
    # Normalize whitespace
    text = " ".join(text.split())
    return text.strip()


def parse_html(html_content: str) -> list[ContestantResult]:
    """Parse the HTML and extract contestant results."""
    soup = BeautifulSoup(html_content, "html.parser")
    results = []

    # Find the individual competition table (id="results")
    table = soup.find("table", id="results")
    if not table:
        raise ParserError("Could not find individual results table (id='results')")

    tbody = table.find("tbody")
    if not tbody:
        raise ParserError("Could not find tbody in results table")

    rows = tbody.find_all("tr")

    # Track ranks based on score ordering
    current_rank = 0
    prev_score = None

    for row_idx, row in enumerate(rows):
        cells = row.find_all("td")

        if len(cells) < 7:
            continue

        try:
            # Name is in first cell, may have multiple text parts (first + last name)
            name_cell = cells[0]
            name_parts = [clean_text(t) for t in name_cell.stripped_strings]
            name = " ".join(name_parts)

            # Country is in second cell
            country = clean_text(cells[1].get_text())
            if country not in COUNTRY_NAME_MAP:
                raise ParserError(f"Unknown country: {country}")

            # Problem scores are in cells 2-5 (I-1 through I-4)
            problem_scores = []
            for i in range(4):
                score_text = clean_text(cells[2 + i].get_text())
                score = int(score_text)
                if score < 0 or score > 8:
                    raise ParserError(
                        f"Row {row_idx}: Score {score} out of range [0-8] for problem {i + 1}"
                    )
                problem_scores.append(score)

            # Total is in cell 6
            total_text = clean_text(cells[6].get_text())
            total = int(total_text)

            # Medal/award is in cell 7 (if present)
            award = None
            if len(cells) > 7:
                award_text = clean_text(cells[7].get_text()).lower()
                award = AWARD_MAP.get(award_text)

            # Calculate rank
            if prev_score is None or total < prev_score:
                current_rank = len(results) + 1
            prev_score = total

            results.append(
                ContestantResult(
                    name=name,
                    country=country,
                    problem_scores=problem_scores,
                    total=total,
                    rank=current_rank,
                    award=award,
                )
            )
        except (ValueError, IndexError) as e:
            raise ParserError(f"Row {row_idx}: Failed to parse: {e}") from e

    return results


def validate_totals(results: list[ContestantResult]) -> list[dict]:
    """Validate that totals match sum of individual scores. Returns mismatches."""
    mismatches = []
    for r in results:
        calculated = sum(r.problem_scores)
        if calculated != r.total:
            mismatches.append(
                {
                    "name": r.name,
                    "country": r.country,
                    "calculated": calculated,
                    "reported": r.total,
                }
            )
    return mismatches


def save_json(data: MEMOYearResults, filepath: Path) -> None:
    """Save results to JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data.model_dump(), f, indent=2, ensure_ascii=False)


def parse_2009(raw_dir: Path, output_dir: Path, force: bool = False) -> Path:
    """
    Parse the MEMO 2009 HTML and save as structured JSON.

    Args:
        raw_dir: Directory containing raw HTML file (2009 year subdirectory)
        output_dir: Directory to save parsed JSON (2009 year subdirectory)
        force: If True, re-parse even if output file exists

    Returns:
        Path to the parsed JSON file

    Raises:
        ParserError: If parsing fails
        FileNotFoundError: If raw HTML file doesn't exist
    """
    from data_processing.sources.memo.downloader.memo_2009_downloader import (
        get_raw_filename,
    )

    raw_file = raw_dir / get_raw_filename()
    output_file = output_dir / get_parsed_filename()

    if output_file.exists() and not force:
        return output_file

    if not raw_file.exists():
        raise FileNotFoundError(f"Raw HTML file not found: {raw_file}")

    html_content = raw_file.read_text(encoding="utf-8")
    results = parse_html(html_content)

    if not results:
        raise ParserError("No results found in MEMO 2009 HTML.")

    mismatches = validate_totals(results)

    year_results = MEMOYearResults(
        year=2009,
        total_contestants=len(results),
        results=results,
        validation=ValidationResult(
            all_totals_match=len(mismatches) == 0,
            mismatches=mismatches,
        ),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    save_json(year_results, output_file)

    return output_file
