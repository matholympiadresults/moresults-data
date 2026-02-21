"""
RMM HTML Parser

Parses raw HTML from rmms.lbi.ro into structured data format.
"""

from pathlib import Path

from bs4 import BeautifulSoup

from .models import ContestantResult, RMMYearResults, ValidationResult


class ParseError(Exception):
    """Raised when parsing fails unexpectedly."""

    pass


def parse_html(html: str, year: int) -> list[ContestantResult]:
    """Parse the HTML and extract contestant results from both tables.

    Args:
        html: Raw HTML content
        year: The competition year (for error messages)

    Returns:
        List of contestant results

    Raises:
        ParseError: If unexpected data is encountered
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Find all h2 headers that indicate result sections
    # - "Individual Results (Provisional)" - main competition (most years)
    # - "Individual Results (Online contestants)" - online competition
    # - "Mathematics - Individual Results" - 2011 format
    headers = soup.find_all("h2", class_="title_content")

    for header in headers:
        header_text = header.get_text(strip=True)

        # Determine if this is online or main competition
        is_online = "Online" in header_text

        # Skip headers that aren't individual results
        # Handle both "Individual Results" and "Mathematics - Individual Results"
        if "Individual Results" not in header_text:
            continue

        # Skip non-math results (physics, chemistry, computer science from 2011)
        if any(subj in header_text for subj in ["Physics", "Chemistry", "Computer Science"]):
            continue

        # Find the table that follows this header
        # Navigate to the parent td and find the table within inside_content
        parent = header.find_parent("tr")
        if not parent:
            continue

        # Find the next sibling rows to locate the table
        table = None
        for sibling in parent.find_next_siblings("tr"):
            td = sibling.find("td", id="inside_content")
            if td:
                table = td.find("table")
                if table:
                    break

        if not table:
            continue

        # Parse the table
        table_results = _parse_table(table, year, is_online)
        results.extend(table_results)

    if not results:
        raise ParseError(f"Could not find any results in HTML for year {year}")

    return results


def _detect_table_format(table) -> int:
    """Detect table format based on number of columns in header row.

    Returns:
        11 for standard format (Name in single column)
        12 for 2011 format (First name, Last name in separate columns)
    """
    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 11 and cells[0].find("b"):
            # This is a header row
            return len(cells)
    return 11  # Default to standard format


def _parse_table(table, year: int, is_online: bool) -> list[ContestantResult]:
    """Parse a single results table.

    Handles two formats:
    - Standard (11 cols): Pos, Name, Country, P1-P6, Total, Award
    - 2011 format (12 cols): Nr, First name, Last name, Country, P1-P6, Total, Medal
    """
    results = []
    rows = table.find_all("tr")

    # Detect table format
    num_cols = _detect_table_format(table)
    is_split_name_format = num_cols == 12

    # Track current rank for handling tied ranks (empty rank cells)
    current_rank: int | None = None

    for row_idx, row in enumerate(rows):
        cells = row.find_all("td")

        # Skip rows with wrong number of cells
        if len(cells) != num_cols:
            continue

        # Check if this is a header row (contains <b> tags in first cell)
        first_cell_text = cells[0].get_text(strip=True)
        if first_cell_text in ("Pos.", "Nr.") or cells[0].find("b"):
            continue

        # Skip footer rows (Grand Total, Average)
        if first_cell_text in ("", "Grand Total", "Average"):
            continue

        # Extract rank (cell 0) - can be empty for tied ranks
        rank_text = cells[0].get_text(strip=True)
        if rank_text:
            try:
                current_rank = int(rank_text)
            except ValueError:
                # Skip non-numeric ranks (like empty or special rows)
                continue
        # If rank_text is empty, current_rank remains from previous row

        # Extract name - format depends on table structure
        if is_split_name_format:
            # 2011 format: First name (cell 1), Last name (cell 2)
            first_name = cells[1].get_text(strip=True)
            last_name = cells[2].get_text(strip=True)
            name_text = f"{first_name} {last_name}"
            country_cell_idx = 3
            score_start_idx = 4
        else:
            # Standard format: Name (cell 1)
            name_text = cells[1].get_text(strip=True)
            country_cell_idx = 2
            score_start_idx = 3

        if not name_text.strip():
            continue

        # Check if official team member (marked with *)
        is_official_team = name_text.endswith("*")
        name = name_text.rstrip("*").strip()

        # Extract country code
        country = cells[country_cell_idx].get_text(strip=True)
        if not country:
            raise ParseError(f"Year {year}, row {row_idx}: Empty country for {name}")
        # Extract just the country code:
        # - "CHN 1" -> "CHN" (newer format with space)
        # - "CHN1" -> "CHN" (older format without space)
        # - "-" stays as "-" (online contestants)
        # - "VIANU" / "Vianu1" -> "VIANU" (special team names)
        country_code = country.split()[0] if " " in country else country
        # Strip trailing digits (e.g., "CHN1" -> "CHN", "ROMB1" -> "ROMB")
        country_code = country_code.rstrip("0123456789").upper()

        # Extract problem scores (P1-P6)
        problem_scores = []
        for i in range(6):
            score_text = cells[score_start_idx + i].get_text(strip=True)
            if not score_text:
                raise ParseError(
                    f"Year {year}, row {row_idx}: Empty score for P{i + 1}, contestant {name}"
                )
            try:
                score = int(score_text)
            except ValueError as e:
                raise ParseError(
                    f"Year {year}, row {row_idx}: Invalid score '{score_text}' for P{i + 1}, contestant {name}"
                ) from e
            if score < 0 or score > 7:
                raise ParseError(
                    f"Year {year}, row {row_idx}: Score {score} out of range [0-7] for P{i + 1}, contestant {name}"
                )
            problem_scores.append(score)

        # Extract total points
        total_idx = score_start_idx + 6
        total_text = cells[total_idx].get_text(strip=True)
        if not total_text:
            raise ParseError(f"Year {year}, row {row_idx}: Empty total for contestant {name}")
        try:
            total = int(total_text)
        except ValueError as e:
            raise ParseError(
                f"Year {year}, row {row_idx}: Invalid total '{total_text}' for contestant {name}"
            ) from e

        # Extract award/medal
        award_idx = total_idx + 1
        award_text = cells[award_idx].get_text(strip=True)
        award = award_text if award_text else None

        results.append(
            ContestantResult(
                name=name,
                country=country_code,
                problem_scores=problem_scores,
                total=total,
                rank=current_rank,
                award=award,
                is_official_team=is_official_team,
                is_online=is_online,
            )
        )

    return results


def _validate_totals(results: list[ContestantResult]) -> list[dict]:
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


def parse_year(html: str, year: int) -> RMMYearResults:
    """Parse HTML for a single year and return structured data.

    Args:
        html: Raw HTML content
        year: The competition year

    Returns:
        Structured year results

    Raises:
        ParseError: If parsing fails
    """
    results = parse_html(html, year)

    if not results:
        raise ParseError(f"No results found for year {year}. The year may not have data yet.")

    mismatches = _validate_totals(results)

    return RMMYearResults(
        year=year,
        total_contestants=len(results),
        results=results,
        validation=ValidationResult(
            all_totals_match=len(mismatches) == 0,
            mismatches=mismatches,
        ),
    )


def save_json(data: RMMYearResults, filepath: Path) -> None:
    """Save results to JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(data.model_dump_json(indent=2))


def load_html(filepath: Path) -> str:
    """Load raw HTML from file."""
    return filepath.read_text(encoding="utf-8")
