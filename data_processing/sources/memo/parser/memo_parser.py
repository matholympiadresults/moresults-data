#!/usr/bin/env python3
"""
MEMO Parser

Parses raw HTML pages from memo-official.org into structured data.
"""

from pathlib import Path

from bs4 import BeautifulSoup

from .models import ContestantResult, MEMOYearResults, ValidationResult


class ParserError(Exception):
    """Raised when parsing fails unexpectedly."""

    pass


def get_parsed_filename() -> str:
    """Get the filename for a parsed JSON file."""
    return "scoreboard.json"


def _parse_rank(rank_text: str, current_rank: int | None, year: int, row_idx: int) -> int | None:
    """Parse rank text, handling tied ranks (e.g., '1-2', '3-5') and empty cells."""
    if not rank_text:
        return current_rank

    # Handle tied rank format like "1-2" or "3-5"
    if "-" in rank_text:
        try:
            start_rank = int(rank_text.split("-")[0])
            return start_rank
        except ValueError as err:
            raise ParserError(
                f"Year {year}, row {row_idx}: Invalid tied rank '{rank_text}'"
            ) from err

    try:
        return int(rank_text)
    except ValueError as err:
        raise ParserError(f"Year {year}, row {row_idx}: Invalid rank '{rank_text}'") from err


def parse_html_2015(html: str, year: int) -> list[ContestantResult]:
    """Parse the 2015 MEMO HTML format from memo2015.dmfa.si.

    This format has 12 columns:
    rank, name, surname, code, nr, country, I-1, I-2, I-3, I-4, sum, medal
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Find the individual results table (first table with class="schedule")
    tables = soup.find_all("table", class_="schedule")
    if not tables:
        raise ParserError(f"Could not find results table in HTML for year {year}")

    # First table is individual results, second is team results
    table = tables[0]
    rows = table.find_all("tr")

    current_rank: int | None = None

    for row_idx, row in enumerate(rows):
        cells = row.find_all("td")

        # Skip header row
        if len(cells) == 0:
            continue

        # 2015 format: 12 cells
        if len(cells) != 12:
            raise ParserError(
                f"Year {year}, row {row_idx}: Expected 12 cells, got {len(cells)}. "
                f"Row content: {row.get_text(strip=True)[:100]}"
            )

        # Extract rank (cell 0) - may be tied like "1-2"
        rank_text = cells[0].get_text(strip=True)
        current_rank = _parse_rank(rank_text, current_rank, year, row_idx)

        # Extract name (cells 1 and 2: first name and surname)
        first_name = cells[1].get_text(strip=True)
        surname = cells[2].get_text(strip=True)
        name = f"{first_name} {surname}".strip()
        if not name:
            raise ParserError(f"Year {year}, row {row_idx}: Empty contestant name")

        # Skip cells 3 (code) and 4 (nr)

        # Extract country (cell 5)
        country = cells[5].get_text(strip=True)
        if not country:
            raise ParserError(f"Year {year}, row {row_idx}: Empty country for {name}")

        # Extract problem scores (cells 6-9: I-1, I-2, I-3, I-4)
        problem_scores = []
        for i in range(4):
            score_text = cells[6 + i].get_text(strip=True)
            if not score_text:
                raise ParserError(
                    f"Year {year}, row {row_idx}: Empty score for I-{i + 1}, contestant {name}"
                )
            try:
                score = int(score_text)
            except ValueError as err:
                raise ParserError(
                    f"Year {year}, row {row_idx}: Invalid score '{score_text}' for I-{i + 1}, contestant {name}"
                ) from err
            if score < 0 or score > 8:
                raise ParserError(
                    f"Year {year}, row {row_idx}: Score {score} out of range [0-8] for I-{i + 1}, contestant {name}"
                )
            problem_scores.append(score)

        # Extract total points (cell 10)
        total_text = cells[10].get_text(strip=True)
        if not total_text:
            raise ParserError(f"Year {year}, row {row_idx}: Empty total for contestant {name}")
        try:
            total = int(total_text)
        except ValueError as err:
            raise ParserError(
                f"Year {year}, row {row_idx}: Invalid total '{total_text}' for contestant {name}"
            ) from err

        # Extract award (cell 11) - can be empty
        award_text = cells[11].get_text(strip=True)
        award = award_text if award_text else None

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

    return results


def parse_html_standard(html: str, year: int) -> list[ContestantResult]:
    """Parse the standard MEMO HTML format from memo-official.org (2016+).

    This format has 9 cells: rank, name, country, I-1, I-2, I-3, I-4, points, prize
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Find the results table
    table = soup.find("table", class_="table")
    if not table:
        raise ParserError(f"Could not find results table in HTML for year {year}")

    rows = table.find_all("tr")

    # Track current rank for handling tied ranks (empty rank cells)
    current_rank: int | None = None

    for row_idx, row in enumerate(rows):
        cells = row.find_all("td")

        # Skip header row (has <th> elements, no <td>)
        if len(cells) == 0:
            continue

        # We expect 9 cells: rank, name, country, I-1, I-2, I-3, I-4, points, prize
        if len(cells) != 9:
            raise ParserError(
                f"Year {year}, row {row_idx}: Expected 9 cells, got {len(cells)}. "
                f"Row content: {row.get_text(strip=True)[:100]}"
            )

        # Extract rank (cell 0) - can be empty for tied ranks
        rank_text = cells[0].get_text(strip=True)
        if rank_text:
            try:
                current_rank = int(rank_text)
            except ValueError as err:
                raise ParserError(
                    f"Year {year}, row {row_idx}: Invalid rank '{rank_text}'"
                ) from err
        # If rank_text is empty, current_rank remains from previous row

        # Extract name (cell 1)
        name = cells[1].get_text(strip=True)
        if not name:
            raise ParserError(f"Year {year}, row {row_idx}: Empty contestant name")

        # Extract country (cell 2)
        country = cells[2].get_text(strip=True)
        if not country:
            raise ParserError(f"Year {year}, row {row_idx}: Empty country for {name}")

        # Extract problem scores (cells 3-6: I-1, I-2, I-3, I-4)
        problem_scores = []
        for i in range(4):
            score_text = cells[3 + i].get_text(strip=True)
            if not score_text:
                raise ParserError(
                    f"Year {year}, row {row_idx}: Empty score for I-{i + 1}, contestant {name}"
                )
            try:
                score = int(score_text)
            except ValueError as err:
                raise ParserError(
                    f"Year {year}, row {row_idx}: Invalid score '{score_text}' for I-{i + 1}, contestant {name}"
                ) from err
            if score < 0 or score > 8:
                raise ParserError(
                    f"Year {year}, row {row_idx}: Score {score} out of range [0-8] for I-{i + 1}, contestant {name}"
                )
            problem_scores.append(score)

        # Extract total points (cell 7)
        total_text = cells[7].get_text(strip=True)
        if not total_text:
            raise ParserError(f"Year {year}, row {row_idx}: Empty total for contestant {name}")
        try:
            total = int(total_text)
        except ValueError as err:
            raise ParserError(
                f"Year {year}, row {row_idx}: Invalid total '{total_text}' for contestant {name}"
            ) from err

        # Extract award/prize (cell 8) - can be empty
        award_text = cells[8].get_text(strip=True)
        award = award_text if award_text else None

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

    return results


def parse_html(html: str, year: int) -> list[ContestantResult]:
    """Parse the HTML and extract contestant results.

    Dispatches to the appropriate parser based on year.
    Raises ParserError if unexpected data is encountered.
    """
    if year == 2015:
        return parse_html_2015(html, year)
    else:
        return parse_html_standard(html, year)


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


def parse_year(year: int, raw_dir: Path, output_dir: Path, force: bool = False) -> Path:
    """
    Parse raw data for a single year and save as structured JSON.

    Args:
        year: The year to parse
        raw_dir: Directory containing raw file (year subdirectory)
        output_dir: Directory to save parsed JSON (year subdirectory)
        force: If True, re-parse even if output file exists

    Returns:
        Path to the parsed JSON file

    Raises:
        ParserError: If parsing fails
        FileNotFoundError: If raw file doesn't exist
    """
    # Dispatch to specialized parsers for years with different formats
    if year == 2007:
        from data_processing.sources.memo.legacy.memo_2007 import parse_2007

        return parse_2007(raw_dir, output_dir, force=force)

    if year == 2008:
        from data_processing.sources.memo.parser.memo_2008_parser import parse_2008

        return parse_2008(raw_dir, output_dir, force=force)

    if year == 2009:
        from data_processing.sources.memo.parser.memo_2009_parser import parse_2009

        return parse_2009(raw_dir, output_dir, force=force)

    if year == 2010:
        from data_processing.sources.memo.parser.skmo_parser import (
            parse_year as parse_skmo_year,
        )

        return parse_skmo_year(year, raw_dir, output_dir, force=force)

    if year == 2011:
        from data_processing.sources.memo.legacy.memo_2011 import parse_2011

        return parse_2011(raw_dir, output_dir, force=force)

    if year == 2013:
        from data_processing.sources.memo.parser.memo_2013_parser import parse_2013

        return parse_2013(raw_dir, output_dir, force=force)

    if year == 2014:
        from data_processing.sources.memo.parser.memo_2014_parser import parse_2014

        return parse_2014(raw_dir, output_dir, force=force)

    # Standard parser for 2015+
    from data_processing.sources.memo.downloader.memo_downloader import get_raw_filename

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

    year_results = MEMOYearResults(
        year=year,
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
