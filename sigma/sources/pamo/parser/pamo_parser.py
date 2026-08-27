#!/usr/bin/env python3
"""
PAMO Parser

Parses raw data from pamoofficial.org into structured data.

Years before the 2026 site redesign come as per-year HTML pages; later years
come as records from the site-wide students JSON feed.
"""

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

from .models import ContestantResult, PAMOYearResults, ValidationResult

# PAMO started in 1987 (edition 1)
PAMO_START_YEAR = 1987

# Award labels used by the students JSON feed
JSON_AWARDS = {
    "GOLD": "GOLD",
    "SILVER": "SILVER",
    "BRONZE": "BRONZE",
    "HM": "HM",
    "HONOURABLE MENTION": "HM",
    "HONORABLE MENTION": "HM",
    "CERTIFICATE OF RECOGNITION": "HM",
}


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


def _json_award(value: str | None, year: int, name: str, field: str) -> str | None:
    """Convert an award label from the students JSON feed to a normalized award."""
    if not value or not value.strip():
        return None
    award = JSON_AWARDS.get(value.strip().upper())
    if award is None:
        raise ParserError(f"Year {year}: Unknown {field} {value!r} for contestant {name}")
    return award


def _json_score(value: str | None, year: int, name: str, problem: int) -> int | None:
    """Convert a problem score from the students JSON feed."""
    text = (value or "").strip()
    if not text or text == "-":
        # Missing score - website data quality issue, record as None
        return None
    try:
        score = int(text)
    except ValueError as e:
        raise ParserError(
            f"Year {year}: Invalid score {text!r} for P{problem}, contestant {name}"
        ) from e
    if score < 0 or score > 7:
        raise ParserError(
            f"Year {year}: Score {score} out of range [0-7] for P{problem}, contestant {name}"
        )
    return score


def parse_students_json(raw: str, year: int) -> list[ContestantResult]:
    """Parse contestant records from the students JSON feed.

    Only official contestants are kept, matching what the legacy per-year HTML
    pages listed.

    Raises ParserError if unexpected data is encountered.
    """
    try:
        records = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ParserError(f"Year {year}: Invalid JSON in raw file: {e}") from e

    if not isinstance(records, list):
        raise ParserError(f"Year {year}: Expected a list of contestant records")

    results = []
    current_rank: int | None = None

    for record in records:
        if str(record.get("YEAR", "")).strip() != str(year):
            raise ParserError(
                f"Year {year}: Raw file contains a record for year {record.get('YEAR')!r}"
            )
        if record.get("STATUS", "").strip().upper() != "OFFICIAL":
            continue

        name = (record.get("NAME") or "").strip()
        if not name:
            raise ParserError(f"Year {year}: Contestant record without a name: {record!r}")

        country = (record.get("CODE") or "").strip().upper()
        if not country:
            raise ParserError(f"Year {year}: Missing country code for contestant {name}")

        rank_text = str(record.get("RANK", "")).strip()
        if rank_text:
            try:
                current_rank = int(rank_text)
            except ValueError:
                pass  # Keep previous rank for tied contestants

        problem_scores = [_json_score(record.get(f"P{i}"), year, name, i) for i in range(1, 7)]

        total_text = str(record.get("TOTAL", "")).strip()
        try:
            total = int(total_text)
        except ValueError as e:
            raise ParserError(
                f"Year {year}: Invalid total {total_text!r} for contestant {name}"
            ) from e

        results.append(
            ContestantResult(
                name=name,
                country=country,
                problem_scores=problem_scores,
                total=total,
                rank=current_rank,
                award=_json_award(record.get("AWARD"), year, name, "award"),
                pamo_g_award=_json_award(record.get("PAMOG"), year, name, "PAMO-G award"),
            )
        )

    if not results:
        raise ParserError(f"Could not find any official results for year {year}")

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
        f.write(data.model_dump_json(indent=2))


def parse_year(year: int, raw_dir: Path, output_dir: Path, force: bool = False) -> Path:
    """
    Parse raw data for a single year and save as structured JSON.

    Args:
        year: The year to parse
        raw_dir: Directory containing the raw file (year subdirectory)
        output_dir: Directory to save parsed JSON (year subdirectory)
        force: If True, re-parse even if output file exists

    Returns:
        Path to the parsed JSON file

    Raises:
        ParserError: If parsing fails
        FileNotFoundError: If the raw file doesn't exist
    """
    from sigma.sources.pamo.downloader.pamo_downloader import (
        NEW_FORMAT_START_YEAR,
        get_raw_filename,
    )

    raw_file = raw_dir / get_raw_filename(year)
    output_file = output_dir / get_parsed_filename()

    if output_file.exists() and not force:
        return output_file

    if not raw_file.exists():
        raise FileNotFoundError(f"Raw file not found: {raw_file}")

    raw = raw_file.read_text(encoding="utf-8")
    if year >= NEW_FORMAT_START_YEAR:
        results = parse_students_json(raw, year)
    else:
        results = parse_html(raw, year)

    if not results:
        raise ParserError(f"No results found for year {year}. The year may not have data yet.")

    mismatches = validate_totals(results)

    year_results = PAMOYearResults(
        year=year,
        edition=pamo_year_to_edition(year),
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
