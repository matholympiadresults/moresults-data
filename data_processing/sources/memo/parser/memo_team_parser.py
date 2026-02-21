#!/usr/bin/env python3
"""
MEMO Team Parser

Parses raw HTML pages for MEMO team contest results.
"""

from pathlib import Path

from bs4 import BeautifulSoup

from .models import MEMOTeamYearResults, TeamResult, ValidationResult


class TeamParserError(Exception):
    """Raised when team parsing fails unexpectedly."""

    pass


def get_team_parsed_filename() -> str:
    """Get the filename for a parsed team JSON file."""
    return "team_scoreboard.json"


def parse_team_html_2015(html: str, year: int) -> list[TeamResult]:
    """Parse the 2015 MEMO team results from the combined results page.

    The 2015 page has two tables: first is individual, second is team.
    Team table format: rank, country, CODE, T-1 to T-8, sum (no medal column)
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    tables = soup.find_all("table", class_="schedule")
    if len(tables) < 2:
        raise TeamParserError(f"Could not find team results table in HTML for year {year}")

    # Second table is team results
    table = tables[1]
    rows = table.find_all("tr")

    for row_idx, row in enumerate(rows):
        cells = row.find_all("td")

        # Skip header row
        if len(cells) == 0:
            continue

        # 2015 team format: 12 cells (rank, country, CODE, T-1 to T-8, sum)
        if len(cells) != 12:
            raise TeamParserError(
                f"Year {year}, row {row_idx}: Expected 12 cells, got {len(cells)}. "
                f"Row content: {row.get_text(strip=True)[:100]}"
            )

        # Extract rank (cell 0)
        rank_text = cells[0].get_text(strip=True)
        try:
            rank = int(rank_text) if rank_text else row_idx
        except ValueError:
            rank = row_idx

        # Extract country (cell 1)
        country = cells[1].get_text(strip=True)
        if not country:
            raise TeamParserError(f"Year {year}, row {row_idx}: Empty country name")

        # Skip cell 2 (CODE)

        # Extract problem scores (cells 3-10: T-1 to T-8)
        problem_scores = []
        for i in range(8):
            score_text = cells[3 + i].get_text(strip=True)
            if not score_text:
                raise TeamParserError(
                    f"Year {year}, row {row_idx}: Empty score for T-{i + 1}, country {country}"
                )
            try:
                score = int(score_text)
            except ValueError as err:
                raise TeamParserError(
                    f"Year {year}, row {row_idx}: Invalid score '{score_text}' for T-{i + 1}"
                ) from err
            if score < 0 or score > 8:
                raise TeamParserError(
                    f"Year {year}, row {row_idx}: Score {score} out of range [0-8] for T-{i + 1}"
                )
            problem_scores.append(score)

        # Extract total points (cell 11)
        total_text = cells[11].get_text(strip=True)
        if not total_text:
            raise TeamParserError(f"Year {year}, row {row_idx}: Empty total for {country}")
        try:
            total = int(total_text)
        except ValueError as err:
            raise TeamParserError(
                f"Year {year}, row {row_idx}: Invalid total '{total_text}' for {country}"
            ) from err

        # No medal column in 2015 format
        award = None

        results.append(
            TeamResult(
                country=country,
                problem_scores=problem_scores,
                total=total,
                rank=rank,
                award=award,
            )
        )

    return results


def parse_team_html_standard(html: str, year: int) -> list[TeamResult]:
    """Parse the standard MEMO team HTML format from memo-official.org (2016+).

    This format has 12 cells: rank, country, T-1 to T-8, points, prize
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    table = soup.find("table", class_="table")
    if not table:
        raise TeamParserError(f"Could not find team results table in HTML for year {year}")

    rows = table.find_all("tr")

    for row_idx, row in enumerate(rows):
        cells = row.find_all("td")

        # Skip header row
        if len(cells) == 0:
            continue

        # Standard team format: 12 cells (rank, country, T-1 to T-8, points, prize)
        if len(cells) != 12:
            raise TeamParserError(
                f"Year {year}, row {row_idx}: Expected 12 cells, got {len(cells)}. "
                f"Row content: {row.get_text(strip=True)[:100]}"
            )

        # Extract rank (cell 0)
        rank_text = cells[0].get_text(strip=True)
        try:
            rank = int(rank_text) if rank_text else row_idx
        except ValueError:
            rank = row_idx

        # Extract country (cell 1)
        country = cells[1].get_text(strip=True)
        if not country:
            raise TeamParserError(f"Year {year}, row {row_idx}: Empty country name")

        # Extract problem scores (cells 2-9: T-1 to T-8)
        problem_scores = []
        for i in range(8):
            score_text = cells[2 + i].get_text(strip=True)
            if not score_text:
                raise TeamParserError(
                    f"Year {year}, row {row_idx}: Empty score for T-{i + 1}, country {country}"
                )
            try:
                score = int(score_text)
            except ValueError as err:
                raise TeamParserError(
                    f"Year {year}, row {row_idx}: Invalid score '{score_text}' for T-{i + 1}"
                ) from err
            if score < 0 or score > 8:
                raise TeamParserError(
                    f"Year {year}, row {row_idx}: Score {score} out of range [0-8] for T-{i + 1}"
                )
            problem_scores.append(score)

        # Extract total points (cell 10)
        total_text = cells[10].get_text(strip=True)
        if not total_text:
            raise TeamParserError(f"Year {year}, row {row_idx}: Empty total for {country}")
        try:
            total = int(total_text)
        except ValueError as err:
            raise TeamParserError(
                f"Year {year}, row {row_idx}: Invalid total '{total_text}' for {country}"
            ) from err

        # Extract award (cell 11)
        award_text = cells[11].get_text(strip=True)
        award = award_text if award_text else None

        results.append(
            TeamResult(
                country=country,
                problem_scores=problem_scores,
                total=total,
                rank=rank,
                award=award,
            )
        )

    return results


def parse_team_html(html: str, year: int) -> list[TeamResult]:
    """Parse team HTML and extract team results.

    Dispatches to the appropriate parser based on year.
    """
    if year == 2015:
        return parse_team_html_2015(html, year)
    else:
        return parse_team_html_standard(html, year)


def validate_team_totals(results: list[TeamResult]) -> list[dict]:
    """Validate that totals match sum of problem scores."""
    mismatches = []
    for r in results:
        calculated = sum(r.problem_scores)
        if calculated != r.total:
            mismatches.append(
                {
                    "country": r.country,
                    "calculated": calculated,
                    "reported": r.total,
                }
            )
    return mismatches


def save_team_json(data: MEMOTeamYearResults, filepath: Path) -> None:
    """Save team results to JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(data.model_dump_json(indent=2))


def parse_team_year(year: int, raw_dir: Path, output_dir: Path, force: bool = False) -> Path:
    """
    Parse raw team data for a single year and save as structured JSON.

    Args:
        year: The year to parse
        raw_dir: Directory containing raw file (year subdirectory)
        output_dir: Directory to save parsed JSON (year subdirectory)
        force: If True, re-parse even if output file exists

    Returns:
        Path to the parsed JSON file

    Raises:
        TeamParserError: If parsing fails
        FileNotFoundError: If raw file doesn't exist
    """
    from data_processing.sources.memo.downloader.memo_downloader import get_team_raw_filename

    raw_file = raw_dir / get_team_raw_filename()
    output_file = output_dir / get_team_parsed_filename()

    if output_file.exists() and not force:
        return output_file

    if not raw_file.exists():
        raise FileNotFoundError(f"Team raw HTML file not found: {raw_file}")

    html = raw_file.read_text(encoding="utf-8")
    results = parse_team_html(html, year)

    if not results:
        raise TeamParserError(f"No team results found for year {year}")

    mismatches = validate_team_totals(results)

    team_results = MEMOTeamYearResults(
        year=year,
        total_teams=len(results),
        results=results,
        validation=ValidationResult(
            all_totals_match=len(mismatches) == 0,
            mismatches=mismatches,
        ),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    save_team_json(team_results, output_file)

    return output_file
