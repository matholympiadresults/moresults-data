#!/usr/bin/env python3
"""
MEMO Legacy Parser

Parses raw HTML pages from skmo.sk (via archive.org) into structured data.
Handles MEMO 2007-2015 format which differs from memo-official.org.
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


def parse_html(html: str, year: int) -> list[ContestantResult]:
    """Parse the HTML and extract contestant results.

    The skmo.sk page has multiple tables:
    1. Slovak-only results (shorter table, first)
    2. Full individual results (all countries)
    3. Country summary for individual competition
    4. Team competition results

    We want to parse table 2 (full individual results).

    Raises ParserError if unexpected data is encountered.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Find all tables with class "poradie"
    tables = soup.find_all("table", class_="poradie")

    # Find the individual results table - it has header row with:
    # "", "name", "country", problem columns, "∑", "prize"
    individual_table = None
    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        # Check header row
        header_row = rows[0]
        header_cells = header_row.find_all("th")

        # Individual results table header pattern:
        # First th is empty, second is "name", third is "country"
        if len(header_cells) >= 9:
            header_text = " ".join(th.get_text(strip=True).lower() for th in header_cells)
            if "name" in header_text and "country" in header_text:
                individual_table = table
                break

    if not individual_table:
        raise ParserError(f"Could not find individual results table in HTML for year {year}")

    rows = individual_table.find_all("tr")

    # Track current rank for handling tied ranks (empty rank cells)
    current_rank: int | None = None

    for row_idx, row in enumerate(rows):
        cells = row.find_all("td")

        # Skip header row (has <th> elements, no <td>)
        if len(cells) == 0:
            continue

        # We expect 9 cells: rank, name, country, P1, P2, P3, P4, total, prize
        if len(cells) != 9:
            continue  # Skip malformed rows

        # Extract rank (cell 0) - can be empty for tied ranks
        rank_text = cells[0].get_text(strip=True)
        rank_text = rank_text.rstrip(".")  # Remove trailing dot
        if rank_text:
            try:
                current_rank = int(rank_text)
            except ValueError:
                # Skip non-numeric ranks (like empty or special rows)
                continue
        # If rank_text is empty, current_rank remains from previous row

        # Extract name (cell 1)
        name = cells[1].get_text(strip=True)
        if not name:
            continue

        # Extract country (cell 2)
        country = cells[2].get_text(strip=True)
        if not country:
            raise ParserError(f"Year {year}, row {row_idx}: Empty country for {name}")

        # Extract problem scores (cells 3-6: P1, P2, P3, P4)
        problem_scores = []
        for i in range(4):
            score_text = cells[3 + i].get_text(strip=True)
            if not score_text:
                raise ParserError(
                    f"Year {year}, row {row_idx}: Empty score for P{i + 1}, contestant {name}"
                )
            try:
                score = int(score_text)
            except ValueError as err:
                raise ParserError(
                    f"Year {year}, row {row_idx}: Invalid score '{score_text}' for P{i + 1}, "
                    f"contestant {name}"
                ) from err
            if score < 0 or score > 8:
                raise ParserError(
                    f"Year {year}, row {row_idx}: Score {score} out of range [0-8] for P{i + 1}, "
                    f"contestant {name}"
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
        award_text = cells[8].get_text(strip=True).lower()
        award = _normalize_award(award_text)

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


def _normalize_award(award_text: str) -> str | None:
    """Normalize award text to standard format."""
    if not award_text:
        return None

    award_lower = award_text.lower()
    if "gold" in award_lower:
        return "Gold"
    if "silver" in award_lower:
        return "Silver"
    if "bronze" in award_lower:
        return "Bronze"
    if "hm" in award_lower or "honourable" in award_lower or "honorable" in award_lower:
        return "Honourable Mention"

    return None


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
    Parse raw HTML for a single year and save as structured JSON.

    Args:
        year: The year to parse
        raw_dir: Directory containing raw HTML file
        output_dir: Directory to save parsed JSON
        force: If True, re-parse even if output file exists

    Returns:
        Path to the parsed JSON file

    Raises:
        ParserError: If parsing fails
        FileNotFoundError: If raw HTML file doesn't exist
    """
    from sigma.sources.memo.downloader.skmo_downloader import get_raw_filename

    raw_file = raw_dir / get_raw_filename(year)
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
