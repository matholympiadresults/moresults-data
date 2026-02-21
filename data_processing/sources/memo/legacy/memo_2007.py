#!/usr/bin/env python3
"""
MEMO 2007 Downloader and Parser

Downloads and parses results from the 1st MEMO (Eisenstadt, Austria).
The data is stored in an XLS file on kag.upol.cz.
"""

from pathlib import Path

import requests
import xlrd

from data_processing.sources.memo.parser.models import (
    ContestantResult,
    MEMOYearResults,
    ValidationResult,
)

XLS_URL = "https://kag.upol.cz/memo/texty/1sj_v.xls"
YEAR = 2007

# Country code to full name mapping
COUNTRY_CODES = {
    "AUT": "Austria",
    "CZE": "Czech Republic",
    "HRV": "Croatia",
    "POL": "Poland",
    "SUI": "Switzerland",
    "SVK": "Slovakia",
    "SVN": "Slovenia",
}


class DownloadError(Exception):
    """Raised when download fails."""

    pass


class ParserError(Exception):
    """Raised when parsing fails."""

    pass


def download_2007(output_dir: Path, force: bool = False) -> Path:
    """
    Download the MEMO 2007 XLS file.

    Args:
        output_dir: Directory to save the raw XLS
        force: If True, re-download even if file exists

    Returns:
        Path to the downloaded file
    """
    output_file = output_dir / "individual.xls"

    if output_file.exists() and not force:
        return output_file

    try:
        response = requests.get(XLS_URL, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise DownloadError(f"Failed to download MEMO 2007: {e}") from e

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(response.content)

    return output_file


def normalize_award(award_text: str) -> str | None:
    """Normalize award text to match memo-official.org format."""
    if not award_text:
        return None
    award_lower = award_text.lower().strip()
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


def parse_2007_xls(xls_path: Path) -> list[ContestantResult]:
    """
    Parse the MEMO 2007 XLS file and extract individual results.

    The XLS structure (from kag.upol.cz/memo/texty/1sj_v.xls):
    Row 0: Rank, Lastname, Firstname, ID, Problem Nr., '', '', '', Σ, Award
    Row 1: '', '', '', '', 1, 2, 3, 4, '', ''
    Row 2+: data rows with rank, lastname, firstname, id (e.g., POL2), scores 1-4, total, award
    """
    workbook = xlrd.open_workbook(xls_path)
    sheet = workbook.sheet_by_index(0)

    results = []

    # Fixed column positions based on the actual file structure:
    # Col 0: Rank
    # Col 1: Lastname
    # Col 2: Firstname
    # Col 3: ID (e.g., POL2, AUT3)
    # Col 4-7: Problem scores (1, 2, 3, 4)
    # Col 8: Total (Σ)
    # Col 9: Award

    # Data starts at row 2 (row 0 is header, row 1 is problem numbers)
    for row_idx in range(2, sheet.nrows):
        row_values = [sheet.cell_value(row_idx, col) for col in range(sheet.ncols)]

        # Skip empty rows
        if all(str(v).strip() == "" for v in row_values):
            continue

        try:
            # Extract rank (col 0)
            rank_val = row_values[0]
            if not rank_val and rank_val != 0:
                continue  # Skip if no rank - likely not a data row
            rank = int(rank_val) if rank_val else None

            # Extract lastname and firstname (cols 1, 2)
            lastname = str(row_values[1]).strip()
            firstname = str(row_values[2]).strip()
            name = f"{firstname} {lastname}".strip()

            if not name:
                continue

            # Extract country from ID (col 3) - format is "POL2", "AUT3", etc.
            contestant_id = str(row_values[3]).strip().upper()
            # Extract country code (first 3 letters)
            country_code = "".join(c for c in contestant_id if c.isalpha())[:3]
            country = COUNTRY_CODES.get(country_code, country_code)

            if not country:
                continue

            # Extract problem scores (cols 4-7)
            problem_scores = []
            for col in range(4, 8):
                score_val = row_values[col]
                if isinstance(score_val, float):
                    score = int(score_val)
                else:
                    score_str = str(score_val).strip()
                    score = int(score_str) if score_str else 0
                if score < 0 or score > 8:
                    raise ParserError(f"Score {score} out of range [0-8] for {name}")
                problem_scores.append(score)

            # Extract total (col 8)
            total_val = row_values[8]
            if isinstance(total_val, float):
                total = int(total_val)
            else:
                total_str = str(total_val).strip()
                total = int(total_str) if total_str else sum(problem_scores)

            # Extract award (col 9)
            award_val = str(row_values[9]).strip()
            award = normalize_award(award_val)

            results.append(
                ContestantResult(
                    name=name,
                    country=country,
                    problem_scores=problem_scores,
                    total=total,
                    rank=rank,
                    award=award,
                )
            )

        except (ValueError, IndexError, TypeError):
            # Skip problematic rows
            continue

    return results


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


def parse_2007(raw_dir: Path, output_dir: Path, force: bool = False) -> Path:
    """
    Parse MEMO 2007 raw XLS and save as structured JSON.

    Args:
        raw_dir: Directory containing the raw XLS file
        output_dir: Directory to save the parsed JSON
        force: If True, re-parse even if output exists

    Returns:
        Path to the parsed JSON file
    """
    raw_file = raw_dir / "individual.xls"
    output_file = output_dir / "scoreboard.json"

    if output_file.exists() and not force:
        return output_file

    if not raw_file.exists():
        raise FileNotFoundError(f"Raw XLS file not found: {raw_file}")

    results = parse_2007_xls(raw_file)

    if not results:
        raise ParserError("No results found in MEMO 2007 XLS")

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
