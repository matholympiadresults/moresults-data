#!/usr/bin/env python3
"""
PAMO Parser

Parses raw HTML pages from pamoofficial.org into structured data.
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from bs4 import BeautifulSoup

from .models import ContestantResult, PAMOYearResults, ValidationResult

# PAMO started in 1987 (edition 1)
PAMO_START_YEAR = 1987


class ParserError(Exception):
    """Raised when parsing fails unexpectedly."""

    pass


def pamo_year_to_edition(year: int) -> int:
    """Convert year to PAMO edition number."""
    return year - PAMO_START_YEAR + 1


def get_parsed_filename() -> str:
    """Get the filename for a parsed JSON file."""
    return "scoreboard.json"


def parse_award_from_image(img_tag) -> str | None:
    """Extract award type from image tag."""
    if not img_tag:
        return None
    src = img_tag.get("src", "")
    alt = img_tag.get("alt", "").lower()

    if "gold" in src.lower() or "gold" in alt:
        return "GOLD"
    if "silver" in src.lower() or "silver" in alt:
        return "SILVER"
    if "bronze" in src.lower() or "bronze" in alt:
        return "BRONZE"
    if "hm" in src.lower() or "honourable" in alt or "honorable" in alt:
        return "HM"
    return None


def extract_country_code(country_cell) -> str:
    """Extract country code from country cell.

    The country cell contains a link like ../../countries/TUN/individual.html
    """
    link = country_cell.find("a")
    if link and link.get("href"):
        href = link.get("href", "")
        # Extract country code from URL: ../../countries/TUN/individual.html -> TUN
        match = re.search(r"/countries/([A-Z]+)/", href)
        if match:
            return match.group(1)
    # Fallback: use text content
    return country_cell.get_text(strip=True).upper()[:3]


def parse_html(html: str, year: int) -> list[ContestantResult]:
    """Parse the HTML and extract contestant results.

    Raises ParserError if unexpected data is encountered.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Find the results table - it should have headers like Contestant, Country, Rank, etc.
    tables = soup.find_all("table")

    results_table = None
    for table in tables:
        # Check if this table has the expected headers
        header_row = table.find("tr")
        if header_row:
            header_text = header_row.get_text().lower()
            if "contestant" in header_text and "country" in header_text:
                results_table = table
                break

    if not results_table:
        raise ParserError(f"Could not find results table for year {year}")

    rows = results_table.find_all("tr")

    # Determine column indices from header row
    header_row = rows[0]
    headers = [th.get_text(strip=True).lower() for th in header_row.find_all(["th", "td"])]

    # Find column indices
    try:
        contestant_idx = next(i for i, h in enumerate(headers) if "contestant" in h)
        country_idx = next(i for i, h in enumerate(headers) if "country" in h)
        rank_idx = next(i for i, h in enumerate(headers) if "rank" in h)
        award_idx = next(i for i, h in enumerate(headers) if h == "award")
        total_idx = next(i for i, h in enumerate(headers) if "total" in h)
    except StopIteration as e:
        raise ParserError(f"Could not find required columns in header: {headers}") from e

    # Find problem score columns (P1-P6)
    problem_indices = []
    for i, h in enumerate(headers):
        if re.match(r"^p\d+$", h):
            problem_indices.append(i)

    if not problem_indices:
        raise ParserError(f"Could not find problem columns in header: {headers}")

    # Find PAMO-G award column if present
    pamo_g_idx = None
    for i, h in enumerate(headers):
        if "pamo-g" in h or "pamog" in h:
            pamo_g_idx = i
            break

    # Track current rank for handling tied ranks
    current_rank: int | None = None

    # Parse data rows (skip header)
    for row_idx, row in enumerate(rows[1:], start=1):
        cells = row.find_all(["td", "th"])

        if len(cells) < len(headers):
            continue

        # Skip empty or footer rows
        contestant_text = cells[contestant_idx].get_text(strip=True)
        if not contestant_text:
            continue

        # Extract name
        name = contestant_text

        # Extract country code
        country = extract_country_code(cells[country_idx])

        # Extract rank
        rank_text = cells[rank_idx].get_text(strip=True)
        if rank_text:
            try:
                current_rank = int(rank_text)
            except ValueError:
                pass  # Keep previous rank for tied contestants

        # Extract award from image
        award_cell = cells[award_idx]
        award_img = award_cell.find("img")
        award = parse_award_from_image(award_img)

        # Extract PAMO-G award if column exists
        pamo_g_award = None
        if pamo_g_idx is not None:
            pamo_g_cell = cells[pamo_g_idx]
            pamo_g_img = pamo_g_cell.find("img")
            pamo_g_award = parse_award_from_image(pamo_g_img)

        # Extract problem scores
        problem_scores: list[int | None] = []
        for prob_idx in problem_indices:
            score_text = cells[prob_idx].get_text(strip=True)
            if not score_text:
                # Empty score - website data quality issue, record as None
                problem_scores.append(None)
                continue
            try:
                score = int(score_text)
            except ValueError as e:
                raise ParserError(
                    f"Year {year}, row {row_idx}: Invalid score '{score_text}' for "
                    f"P{len(problem_scores) + 1}, contestant {name}"
                ) from e
            if score < 0 or score > 7:
                raise ParserError(
                    f"Year {year}, row {row_idx}: Score {score} out of range [0-7] for "
                    f"P{len(problem_scores) + 1}, contestant {name}"
                )
            problem_scores.append(score)

        # Extract total
        total_text = cells[total_idx].get_text(strip=True)
        if not total_text:
            raise ParserError(f"Year {year}, row {row_idx}: Empty total for contestant {name}")
        try:
            total = int(total_text)
        except ValueError as e:
            raise ParserError(
                f"Year {year}, row {row_idx}: Invalid total '{total_text}' for contestant {name}"
            ) from e

        results.append(
            ContestantResult(
                name=name,
                country=country,
                problem_scores=problem_scores,
                total=total,
                rank=current_rank,
                award=award,
                pamo_g_award=pamo_g_award,
            )
        )

    if not results:
        raise ParserError(f"Could not find any results in HTML for year {year}")

    return results


def validate_totals(results: list[ContestantResult]) -> list[dict]:
    """Validate that totals match sum of individual scores. Returns mismatches."""
    mismatches = []
    for r in results:
        # Skip validation if any scores are missing
        if None in r.problem_scores:
            continue
        calculated = sum(s for s in r.problem_scores if s is not None)
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


def save_json(data: PAMOYearResults, filepath: Path) -> None:
    """Save results to JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data.model_dump(), f, indent=2, ensure_ascii=False)


def parse_year(year: int, raw_dir: Path, output_dir: Path, force: bool = False) -> Path:
    """
    Parse raw HTML for a single year and save as structured JSON.

    Args:
        year: The year to parse
        raw_dir: Directory containing raw HTML file (year subdirectory)
        output_dir: Directory to save parsed JSON (year subdirectory)
        force: If True, re-parse even if output file exists

    Returns:
        Path to the parsed JSON file

    Raises:
        ParserError: If parsing fails
        FileNotFoundError: If raw HTML file doesn't exist
    """
    from data_processing.sources.pamo.downloader.pamo_downloader import get_raw_filename

    raw_file = raw_dir / get_raw_filename()
    output_file = output_dir / get_parsed_filename()

    if output_file.exists() and not force:
        return output_file

    if not raw_file.exists():
        raise FileNotFoundError(f"Raw HTML file not found: {raw_file}")

    html = raw_file.read_text(encoding="utf-8")
    results = parse_html(html, year)

    if not results:
        raise ParserError(f"No results found for year {year}. The year may not have data yet.")

    mismatches = validate_totals(results)

    year_results = PAMOYearResults(
        year=year,
        edition=pamo_year_to_edition(year),
        parsed_at=datetime.now(UTC).isoformat(),
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
