#!/usr/bin/env python3
"""
MEMO 2008 Parser

Parses the MEMO 2008 (2nd edition) individual results XLS into structured data.
"""

from pathlib import Path

import xlrd

from .models import ContestantResult, MEMOYearResults, ValidationResult

# Country code to full name mapping
# MEMO 2008 uses 3-letter codes in the ID column (e.g., "GER1", "HUN3")
COUNTRY_CODE_MAP = {
    "AUT": "Austria",
    "CRO": "Croatia",
    "CZE": "Czech Republic",
    "GER": "Germany",
    "HUN": "Hungary",
    "POL": "Poland",
    "SLO": "Slovenia",
    "SUI": "Switzerland",
    "SVK": "Slovakia",
}

# Award mapping
AWARD_MAP = {
    "Gold": "Gold",
    "Silver": "Silver",
    "Bronze": "Bronze",
    "HM": "Honourable Mention",
}


class ParserError(Exception):
    """Raised when parsing fails unexpectedly."""

    pass


def get_parsed_filename() -> str:
    """Get the filename for a parsed JSON file."""
    return "scoreboard.json"


def parse_xls(xls_path: Path) -> list[ContestantResult]:
    """Parse the XLS and extract contestant results.

    XLS columns:
    0: ID (e.g., "GER1", "HUN3") - contains country code
    1: Lastname
    2: Firstname
    3: I-1 (score 0-8)
    4: I-2 (score 0-8)
    5: I-3 (score 0-8)
    6: I-4 (score 0-8)
    7: Sum (total score)
    8: Rank
    9: Award (Gold, Silver, Bronze, HM, or empty)
    """
    workbook = xlrd.open_workbook(str(xls_path))
    sheet = workbook.sheet_by_index(0)

    results = []

    # Start from row 1 (skip header row 0)
    for row_idx in range(1, sheet.nrows):
        try:
            # Extract ID and parse country code
            contestant_id = sheet.cell_value(row_idx, 0)
            if not contestant_id:
                continue

            # Country code is the first 3 characters of the ID
            country_code = contestant_id[:3]
            if country_code not in COUNTRY_CODE_MAP:
                raise ParserError(
                    f"Row {row_idx}: Unknown country code '{country_code}' in ID '{contestant_id}'"
                )
            country = COUNTRY_CODE_MAP[country_code]

            # Extract name (lastname + firstname)
            lastname = str(sheet.cell_value(row_idx, 1)).strip()
            firstname = str(sheet.cell_value(row_idx, 2)).strip()
            name = f"{firstname} {lastname}".strip()
            if not name:
                raise ParserError(f"Row {row_idx}: Empty contestant name")

            # Extract problem scores (columns 3-6)
            problem_scores = []
            for col in range(3, 7):
                score_value = sheet.cell_value(row_idx, col)
                score = int(score_value)
                if score < 0 or score > 8:
                    raise ParserError(
                        f"Row {row_idx}: Score {score} out of range [0-8] for problem {col - 2}"
                    )
                problem_scores.append(score)

            # Extract total (column 7)
            total = int(sheet.cell_value(row_idx, 7))

            # Extract rank (column 8)
            rank = int(sheet.cell_value(row_idx, 8))

            # Extract award (column 9)
            award_text = str(sheet.cell_value(row_idx, 9)).strip()
            award = AWARD_MAP.get(award_text)

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
        f.write(data.model_dump_json(indent=2))


def parse_2008(raw_dir: Path, output_dir: Path, force: bool = False) -> Path:
    """
    Parse the MEMO 2008 XLS and save as structured JSON.

    Args:
        raw_dir: Directory containing raw XLS file (2008 year subdirectory)
        output_dir: Directory to save parsed JSON (2008 year subdirectory)
        force: If True, re-parse even if output file exists

    Returns:
        Path to the parsed JSON file

    Raises:
        ParserError: If parsing fails
        FileNotFoundError: If raw XLS file doesn't exist
    """
    from data_processing.sources.memo.downloader.memo_2008_downloader import (
        get_raw_filename,
    )

    raw_file = raw_dir / get_raw_filename()
    output_file = output_dir / get_parsed_filename()

    if output_file.exists() and not force:
        return output_file

    if not raw_file.exists():
        raise FileNotFoundError(f"Raw XLS file not found: {raw_file}")

    results = parse_xls(raw_file)

    if not results:
        raise ParserError("No results found in MEMO 2008 XLS.")

    mismatches = validate_totals(results)

    year_results = MEMOYearResults(
        year=2008,
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
