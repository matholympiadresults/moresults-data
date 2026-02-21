"""APMO parser - parses raw HTML files into structured data.

Stage 2 of the pipeline: reads raw HTML files, parses contestant data,
computes global ranks, and returns structured APMOScoreboard.
"""

from pathlib import Path

from bs4 import BeautifulSoup

from ..downloader import extract_countries_from_year_report
from .models import APMOScoreboard, Award, Contestant


class ParseError(Exception):
    """Raised when parsing fails unexpectedly."""

    pass


def parse_award(value: str) -> Award | None:
    """Parse award string to Award enum."""
    value = value.strip().lower()
    if not value:
        return None
    if "gold" in value:
        return Award.GOLD
    if "silver" in value:
        return Award.SILVER
    if "bronze" in value:
        return Award.BRONZE
    if "hon" in value:  # "Hon. Men." or "Honorable Mention"
        return Award.HONOURABLE_MENTION
    return None


def parse_int(value: str) -> int | None:
    """Parse a string to int, returning None for empty strings.

    Handles float strings like '7.0' by converting to int.
    """
    value = value.strip()
    if not value:
        return None
    # Handle float strings like "7.0" or "35.0"
    try:
        return int(float(value))
    except ValueError:
        return None


def parse_country_results(html: str, country_code: str, country_name: str) -> list[Contestant]:
    """Parse contestant results from a country report page."""
    soup = BeautifulSoup(html, "html.parser")
    contestants = []

    # Find the desktop table (d-lg-table has all columns separated)
    # The mobile table (d-lg-none) has scores combined in one column
    table = soup.find("table", class_="d-lg-table")
    if not table:
        # Fallback to any table with P1-P5 columns
        tables = soup.find_all("table", class_="table")
        for t in tables:
            header = t.find("tr")
            if header and "P1" in header.get_text() and "P5" in header.get_text():
                table = t
                break

    if not table:
        raise ParseError(f"Could not find results table for {country_code}")

    rows = table.find_all("tr")

    for row in rows:
        cells = row.find_all("td")
        if not cells:
            continue

        # Expected columns: Rank, Last Name, First Name, P1, P2, P3, P4, P5, Total, Award
        if len(cells) < 10:
            continue

        try:
            rank = parse_int(cells[0].get_text(strip=True))
            family_name = cells[1].get_text(strip=True)
            given_name = cells[2].get_text(strip=True)

            # Problem scores P1-P5 (columns 3-7)
            problem_scores = []
            for i in range(3, 8):
                score_text = cells[i].get_text(strip=True)
                problem_scores.append(parse_int(score_text))

            total = parse_int(cells[8].get_text(strip=True))
            if total is None:
                continue  # Skip rows without valid total

            award_text = cells[9].get_text(strip=True) if len(cells) > 9 else ""
            award = parse_award(award_text)

            contestant = Contestant(
                country_name=country_name,
                country_code=country_code,
                given_name=given_name,
                family_name=family_name,
                problem_scores=problem_scores,
                total=total,
                award=award,
                rank=rank,
            )
            contestants.append(contestant)

        except (ValueError, IndexError):
            # Skip invalid rows
            continue

    return contestants


def compute_global_ranks(contestants: list[Contestant]) -> list[Contestant]:
    """Compute global ranks based on total scores.

    Contestants with the same total score receive the same rank.
    The list should already be sorted by total score descending.
    """
    if not contestants:
        return contestants

    ranked = []
    current_rank = 1
    prev_total = None

    for i, contestant in enumerate(contestants):
        if prev_total is not None and contestant.total < prev_total:
            current_rank = i + 1
        prev_total = contestant.total

        # Create a new contestant with updated rank
        ranked.append(
            Contestant(
                country_name=contestant.country_name,
                country_code=contestant.country_code,
                given_name=contestant.given_name,
                family_name=contestant.family_name,
                problem_scores=contestant.problem_scores,
                total=contestant.total,
                award=contestant.award,
                rank=current_rank,
            )
        )

    return ranked


def parse_raw_year(year: int, raw_dir: Path) -> APMOScoreboard:
    """Parse raw HTML files into structured APMOScoreboard.

    Args:
        year: Competition year
        raw_dir: Directory containing raw HTML files (raw/{year}/)

    Returns:
        Parsed APMOScoreboard
    """
    # Read year report to get countries
    year_report_path = raw_dir / "year_report.html"
    if not year_report_path.exists():
        raise ParseError(f"Year report not found: {year_report_path}")

    year_html = year_report_path.read_text(encoding="utf-8")
    countries = extract_countries_from_year_report(year_html)

    if not countries:
        raise ParseError(f"No countries found in year report for APMO {year}")

    all_contestants = []

    for country_code, country_name in countries:
        country_path = raw_dir / f"{country_code}.html"
        if not country_path.exists():
            print(f"  Warning: Country file not found: {country_path}")
            continue

        try:
            country_html = country_path.read_text(encoding="utf-8")
            contestants = parse_country_results(country_html, country_code, country_name)
            all_contestants.extend(contestants)
        except Exception as e:
            print(f"  Warning: Failed to parse {country_name} ({country_code}): {e}")

    if not all_contestants:
        raise ParseError(f"No contestants found for APMO {year}")

    # Sort by total score (descending) and compute global ranks
    all_contestants.sort(key=lambda c: (-c.total, c.family_name, c.given_name))
    all_contestants = compute_global_ranks(all_contestants)

    return APMOScoreboard(
        year=year,
        contestants=all_contestants,
    )


def save_json(scoreboard: APMOScoreboard, filepath: Path) -> None:
    """Save scoreboard to a JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(scoreboard.model_dump_json(indent=2))
