#!/usr/bin/env python3
"""
MEMO 2011 Downloader and Parser

Downloads and parses results from memo2011.math.hr (5th MEMO, Varaždin, Croatia).
This site has a different structure than memo-official.org.
"""

from pathlib import Path

import requests
from bs4 import BeautifulSoup

from data_processing.sources.memo.parser.models import (
    ContestantResult,
    MEMOYearResults,
    ValidationResult,
)

BASE_URL = "https://memo2011.math.hr"
RESULTS_URL = f"{BASE_URL}/index.php?option=com_content&view=article&id=16&Itemid=36&lang=en"

YEAR = 2011


class DownloadError(Exception):
    """Raised when download fails."""

    pass


class ParserError(Exception):
    """Raised when parsing fails."""

    pass


def download_2011(output_dir: Path, force: bool = False) -> Path:
    """
    Download the MEMO 2011 results page.

    Args:
        output_dir: Directory to save the raw HTML
        force: If True, re-download even if file exists

    Returns:
        Path to the downloaded file
    """
    output_file = output_dir / "results.html"

    if output_file.exists() and not force:
        return output_file

    try:
        response = requests.get(RESULTS_URL, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise DownloadError(f"Failed to download MEMO 2011: {e}") from e

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_text(response.text, encoding="utf-8")

    return output_file


def parse_2011_html(html: str) -> list[ContestantResult]:
    """
    Parse the MEMO 2011 HTML and extract individual results.

    The HTML has a table with columns:
    Contestant | Given name | Family name | Country | I1 | I2 | I3 | I4 | Total | Award
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Find all tables - the first one is individual results
    tables = soup.find_all("table")
    if not tables:
        raise ParserError("Could not find any tables in HTML")

    # The individual results table is the first one
    individual_table = tables[0]
    rows = individual_table.find_all("tr")

    for row_idx, row in enumerate(rows):
        cells = row.find_all("td")

        # Skip header row (has <th> elements, no <td>)
        if len(cells) == 0:
            continue

        # We expect 10 cells:
        # contestant_id, given_name, family_name, country, I1, I2, I3, I4, total, award
        if len(cells) != 10:
            raise ParserError(
                f"Row {row_idx}: Expected 10 cells, got {len(cells)}. "
                f"Row content: {row.get_text(strip=True)[:100]}"
            )

        # Extract contestant ID (e.g., "POL3") - not used in current schema
        _ = cells[0].get_text(strip=True)

        # Extract given and family names
        given_name = cells[1].get_text(strip=True)
        family_name = cells[2].get_text(strip=True)
        name = f"{given_name} {family_name}".strip()

        if not name:
            raise ParserError(f"Row {row_idx}: Empty contestant name")

        # Extract country
        country = cells[3].get_text(strip=True)
        if not country:
            raise ParserError(f"Row {row_idx}: Empty country for {name}")

        # Extract problem scores (cells 4-7: I1, I2, I3, I4)
        problem_scores = []
        for i in range(4):
            score_text = cells[4 + i].get_text(strip=True)
            if not score_text:
                raise ParserError(f"Row {row_idx}: Empty score for I{i + 1}, contestant {name}")
            try:
                score = int(score_text)
            except ValueError as err:
                raise ParserError(
                    f"Row {row_idx}: Invalid score '{score_text}' for I{i + 1}, contestant {name}"
                ) from err
            if score < 0 or score > 8:
                raise ParserError(
                    f"Row {row_idx}: Score {score} out of range [0-8] for I{i + 1}, contestant {name}"
                )
            problem_scores.append(score)

        # Extract total (cell 8)
        total_text = cells[8].get_text(strip=True)
        if not total_text:
            raise ParserError(f"Row {row_idx}: Empty total for contestant {name}")
        try:
            total = int(total_text)
        except ValueError as err:
            raise ParserError(
                f"Row {row_idx}: Invalid total '{total_text}' for contestant {name}"
            ) from err

        # Extract award (cell 9) - e.g., "Gold medal", "Silver medal", etc.
        award_text = cells[9].get_text(strip=True)
        # Normalize award format to match memo-official.org
        award = normalize_award(award_text) if award_text else None

        results.append(
            ContestantResult(
                name=name,
                country=country,
                problem_scores=problem_scores,
                total=total,
                rank=None,  # Not provided in 2011 data, will compute from total
                award=award,
            )
        )

    # Compute ranks from total scores
    results = compute_ranks(results)

    return results


def normalize_award(award_text: str) -> str | None:
    """Normalize award text to match memo-official.org format."""
    award_lower = award_text.lower()
    if "gold" in award_lower:
        return "Gold"
    elif "silver" in award_lower:
        return "Silver"
    elif "bronze" in award_lower:
        return "Bronze"
    elif "honourable" in award_lower or "honorable" in award_lower:
        return "Honourable Mention"
    return None


def compute_ranks(results: list[ContestantResult]) -> list[ContestantResult]:
    """Compute ranks based on total scores."""
    # Sort by total descending
    sorted_results = sorted(results, key=lambda r: r.total, reverse=True)

    ranked_results = []
    current_rank = 1
    prev_total = None

    for i, result in enumerate(sorted_results):
        if prev_total is not None and result.total < prev_total:
            current_rank = i + 1

        ranked_results.append(
            ContestantResult(
                name=result.name,
                country=result.country,
                problem_scores=result.problem_scores,
                total=result.total,
                rank=current_rank,
                award=result.award,
            )
        )
        prev_total = result.total

    return ranked_results


def validate_totals(results: list[ContestantResult]) -> list[dict]:
    """Validate that totals match sum of individual scores."""
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


def parse_2011(raw_dir: Path, output_dir: Path, force: bool = False) -> Path:
    """
    Parse MEMO 2011 raw HTML and save as structured JSON.

    Args:
        raw_dir: Directory containing the raw HTML file
        output_dir: Directory to save the parsed JSON
        force: If True, re-parse even if output exists

    Returns:
        Path to the parsed JSON file
    """
    raw_file = raw_dir / "results.html"
    output_file = output_dir / "scoreboard.json"

    if output_file.exists() and not force:
        return output_file

    if not raw_file.exists():
        raise FileNotFoundError(f"Raw HTML file not found: {raw_file}")

    html = raw_file.read_text(encoding="utf-8")
    results = parse_2011_html(html)

    if not results:
        raise ParserError("No results found in MEMO 2011 HTML")

    mismatches = validate_totals(results)

    year_results = MEMOYearResults(
        year=YEAR,
        total_contestants=len(results),
        results=results,
        validation=ValidationResult(
            all_totals_match=len(mismatches) == 0,
            mismatches=mismatches,
        ),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(year_results.model_dump_json(indent=2))

    return output_file
