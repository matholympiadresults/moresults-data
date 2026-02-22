#!/usr/bin/env python3
"""
MEMO 2014 Parser

Parses the MEMO 2014 individual results ODS file into structured data.
"""

from pathlib import Path

from odf import text
from odf.opendocument import load
from odf.table import Table, TableCell, TableRow

from .models import ContestantResult, MEMOYearResults, ValidationResult

# Award mapping from ODS Prize column
AWARD_MAP = {
    "1": "Gold",
    "2": "Silver",
    "3": "Bronze",
    "H": "Honourable Mention",
}

# Country name normalization
COUNTRY_NAME_MAP = {
    "Czech Republic": "Czech Republic",
    "Czechia": "Czech Republic",
}


class ParserError(Exception):
    """Raised when parsing fails unexpectedly."""

    pass


def get_parsed_filename() -> str:
    """Get the filename for a parsed JSON file."""
    return "scoreboard.json"


def read_ods_rows(ods_path: Path) -> list[list[str]]:
    """Read all rows from the ODS file, handling cell repetition."""
    doc = load(str(ods_path))
    all_rows = []

    for sheet in doc.spreadsheet.getElementsByType(Table):
        rows = sheet.getElementsByType(TableRow)

        for row in rows:
            cells = row.getElementsByType(TableCell)
            values = []

            for cell in cells:
                # Handle repeated columns (ODS compression)
                repeated = cell.getAttribute("numbercolumnsrepeated")
                repeat_count = int(repeated) if repeated else 1

                # Get text content from cell
                p = cell.getElementsByType(text.P)
                cell_text = ""
                if p:
                    cell_text = str(p[0])

                # Add value (repeated if needed, but limit to avoid huge outputs)
                for _ in range(min(repeat_count, 20)):
                    values.append(cell_text)

            all_rows.append(values)

    return all_rows


def calculate_ranks(results: list[ContestantResult]) -> list[ContestantResult]:
    """Calculate ranks based on total scores (with ties)."""
    # Sort by total descending
    sorted_results = sorted(results, key=lambda r: r.total, reverse=True)

    ranked_results = []
    current_rank = 1
    prev_total = None

    for i, result in enumerate(sorted_results):
        if result.total != prev_total:
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


def parse_ods(ods_path: Path) -> list[ContestantResult]:
    """Parse the ODS file and extract contestant results."""
    rows = read_ods_rows(ods_path)
    results = []

    for row_idx, row in enumerate(rows):
        # Skip header row (has 'A1', 'A2', etc.)
        if row_idx == 0:
            continue

        # Skip empty rows
        if not row or not row[0]:
            continue

        # Ensure we have enough columns
        if len(row) < 10:
            raise ParserError(
                f"Row {row_idx}: Expected at least 10 columns, got {len(row)}. "
                f"Row content: {row[:10]}"
            )

        # Extract fields
        # Columns: first_name, last_name, code, country, A1, A2, A3, A4, Sum, Prize
        first_name = row[0].strip()
        last_name = row[1].strip()
        # row[2] is code (e.g., "CRO-3") - not needed for output
        country = row[3].strip()
        country = COUNTRY_NAME_MAP.get(country, country)

        name = f"{first_name} {last_name}".strip()
        if not name:
            raise ParserError(f"Row {row_idx}: Empty contestant name")

        if not country:
            raise ParserError(f"Row {row_idx}: Empty country for {name}")

        # Parse problem scores (columns 4-7: A1, A2, A3, A4)
        problem_scores = []
        for i in range(4):
            score_text = row[4 + i].strip()
            if not score_text:
                raise ParserError(f"Row {row_idx}: Empty score for A{i + 1}, contestant {name}")
            try:
                score = int(score_text)
            except ValueError as err:
                raise ParserError(
                    f"Row {row_idx}: Invalid score '{score_text}' for A{i + 1}, contestant {name}"
                ) from err
            if score < 0 or score > 8:
                raise ParserError(
                    f"Row {row_idx}: Score {score} out of range [0-8] for A{i + 1}, contestant {name}"
                )
            problem_scores.append(score)

        # Parse total (column 8)
        total_text = row[8].strip()
        if not total_text:
            raise ParserError(f"Row {row_idx}: Empty total for contestant {name}")
        try:
            total = int(total_text)
        except ValueError as err:
            raise ParserError(
                f"Row {row_idx}: Invalid total '{total_text}' for contestant {name}"
            ) from err

        # Parse award (column 9)
        award_text = row[9].strip() if len(row) > 9 else ""
        award = AWARD_MAP.get(award_text)

        results.append(
            ContestantResult(
                name=name,
                country=country,
                problem_scores=problem_scores,
                total=total,
                rank=None,  # Will be calculated later
                award=award,
            )
        )

    # Calculate ranks
    results = calculate_ranks(results)

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


def parse_2014(raw_dir: Path, output_dir: Path, force: bool = False) -> Path:
    """
    Parse the MEMO 2014 ODS file and save as structured JSON.

    Args:
        raw_dir: Directory containing raw ODS file (2014 year subdirectory)
        output_dir: Directory to save parsed JSON (2014 year subdirectory)
        force: If True, re-parse even if output file exists

    Returns:
        Path to the parsed JSON file

    Raises:
        ParserError: If parsing fails
        FileNotFoundError: If raw ODS file doesn't exist
    """
    from sigma.sources.memo.downloader.memo_2014_downloader import (
        get_raw_filename,
    )

    raw_file = raw_dir / get_raw_filename()
    output_file = output_dir / get_parsed_filename()

    if output_file.exists() and not force:
        return output_file

    if not raw_file.exists():
        raise FileNotFoundError(f"Raw ODS file not found: {raw_file}")

    results = parse_ods(raw_file)

    if not results:
        raise ParserError("No results found in MEMO 2014 ODS file.")

    mismatches = validate_totals(results)

    year_results = MEMOYearResults(
        year=2014,
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
