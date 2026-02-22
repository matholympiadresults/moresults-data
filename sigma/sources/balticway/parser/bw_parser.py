"""Baltic Way Parser

Parses raw HTML and PDF results pages into structured data.

HTML years: 1992-2019, 2024
PDF years: 2020-2023, 2025
"""

from pathlib import Path

import pdfplumber
from bs4 import BeautifulSoup

from .models import BWYearResults, TeamResult, ValidationResult

# Baltic Way started in 1990 (edition 1)
BW_START_YEAR = 1990


class ParserError(Exception):
    """Raised when parsing fails unexpectedly."""

    pass


def get_parsed_filename() -> str:
    """Get the filename for a parsed JSON file."""
    return "scoreboard.json"


def _compute_ranks(results: list[TeamResult]) -> list[TeamResult]:
    """Compute competition-style ranks from totals (ties get same rank)."""
    sorted_results = sorted(results, key=lambda r: r.total, reverse=True)
    ranked = []
    for i, result in enumerate(sorted_results):
        if i == 0 or result.total < sorted_results[i - 1].total:
            rank = i + 1
        # else: same rank as previous (tie)
        ranked.append(result.model_copy(update={"rank": rank}))
    return ranked


def _parse_score(text: str) -> int | None:
    """Parse a single score cell. Returns int or None if not a valid integer score."""
    text = text.strip()
    if text == "-":
        return 0
    try:
        return int(text)
    except ValueError:
        return None


def _extract_rows_from_html(html: str, year: int) -> list[TeamResult]:
    """Parse HTML table and extract team results."""
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("table")
    if not table:
        raise ParserError(f"Could not find results table for year {year}")

    rows = table.find_all("tr")
    results = []

    for row in rows:
        cells = row.find_all("td")
        if not cells:
            continue

        # Get text from all cells
        cell_texts = [cell.get_text(strip=True) for cell in cells]

        # Determine if this row has a rank column (2024 format: rank + team + 20 scores + total = 23)
        # Standard format: team + 20 scores + total = 22
        if len(cell_texts) == 23:
            # 2024 format with rank column
            team_name = cell_texts[1]
            score_texts = cell_texts[2:22]
            total_text = cell_texts[22]
        elif len(cell_texts) == 22:
            team_name = cell_texts[0]
            score_texts = cell_texts[1:21]
            total_text = cell_texts[21]
        else:
            # Skip header rows, sub-header rows, or other non-data rows
            continue

        # Skip empty team names, "average" rows, and category labels
        if not team_name or team_name.lower() in ("average", "team", ""):
            continue

        # Parse all 20 scores
        scores = []
        valid_row = True
        for st in score_texts:
            score = _parse_score(st)
            if score is None:
                # Non-integer score (e.g. decimal average) → skip this row
                valid_row = False
                break
            scores.append(score)

        if not valid_row or len(scores) != 20:
            continue

        # Parse total
        total = _parse_score(total_text)
        if total is None:
            continue

        results.append(
            TeamResult(
                team_name=team_name,
                problem_scores=scores,
                total=total,
                rank=0,  # Placeholder, computed later
            )
        )

    if not results:
        raise ParserError(f"Could not find any results in HTML for year {year}")

    return results


def _extract_rows_from_pdf(pdf_path: Path, year: int) -> list[TeamResult]:
    """Parse PDF table and extract team results."""
    results = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if row is None:
                        continue

                    # Filter out None cells
                    cells = [c if c is not None else "" for c in row]

                    # Determine format: check if first cell looks like a rank number
                    # Try to detect and skip the rank column
                    start_idx = 0
                    if len(cells) >= 23:
                        # Has rank column
                        try:
                            int(cells[0].strip().rstrip(".").replace("-", ""))
                            start_idx = 1
                        except ValueError:
                            start_idx = 1  # Skip first column anyway for 23+ cells

                    if len(cells) - start_idx < 22:
                        continue

                    team_name = cells[start_idx].strip()
                    score_texts = cells[start_idx + 1 : start_idx + 21]
                    total_text = cells[start_idx + 21].strip()

                    # Skip headers and non-data rows
                    if not team_name or team_name.lower() in (
                        "average",
                        "team",
                        "total",
                        "",
                    ):
                        continue

                    # Skip if score_texts contain header-like values
                    if any(
                        s.strip().lower() in ("1.", "2.", "total", "team") for s in score_texts[:3]
                    ):
                        continue

                    # Parse scores
                    scores = []
                    valid_row = True
                    for st in score_texts:
                        score = _parse_score(st.strip())
                        if score is None:
                            valid_row = False
                            break
                        scores.append(score)

                    if not valid_row or len(scores) != 20:
                        continue

                    total = _parse_score(total_text)
                    if total is None:
                        continue

                    results.append(
                        TeamResult(
                            team_name=team_name,
                            problem_scores=scores,
                            total=total,
                            rank=0,
                        )
                    )

    if not results:
        raise ParserError(f"Could not find any results in PDF for year {year}")

    return results


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


def save_json(data: BWYearResults, filepath: Path) -> None:
    """Save results to JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(data.model_dump_json(indent=2))


def parse_year(year: int, raw_dir: Path, output_dir: Path, force: bool = False) -> Path:
    """Parse raw HTML/PDF for a single year and save as structured JSON.

    Args:
        year: The year to parse
        raw_dir: Directory containing raw HTML/PDF file
        output_dir: Directory to save parsed JSON
        force: If True, re-parse even if output file exists

    Returns:
        Path to the parsed JSON file

    Raises:
        ParserError: If parsing fails
        FileNotFoundError: If raw file doesn't exist
    """
    output_file = output_dir / get_parsed_filename()

    if output_file.exists() and not force:
        return output_file

    # Try PDF first, then HTML
    raw_pdf = raw_dir / "results.pdf"
    raw_html = raw_dir / "results.html"

    if raw_pdf.exists():
        results = _extract_rows_from_pdf(raw_pdf, year)
    elif raw_html.exists():
        html = raw_html.read_text(encoding="utf-8")
        results = _extract_rows_from_html(html, year)
    else:
        raise FileNotFoundError(
            f"No raw file found in {raw_dir} (expected results.html or results.pdf)"
        )

    # Compute ranks
    results = _compute_ranks(results)

    # Validate
    mismatches = validate_totals(results)

    year_results = BWYearResults(
        year=year,
        num_teams=len(results),
        results=results,
        validation=ValidationResult(
            all_totals_match=len(mismatches) == 0,
            mismatches=mismatches,
        ),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    save_json(year_results, output_file)

    return output_file
