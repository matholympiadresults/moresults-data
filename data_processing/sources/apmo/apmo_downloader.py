"""APMO Scoreboard Data Downloader

Downloads and parses APMO (Asian Pacific Mathematical Olympiad) scoreboard data
into structured Pydantic models.

3-stage pipeline:
1. download_raw() - Downloads HTML files to raw/{year}/
2. parse_raw() - Parses HTML to JSON in parsed/{year}/
3. ingest() - Ingests parsed JSON into database
"""

import re
from enum import Enum
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field


class Award(str, Enum):
    GOLD = "Gold Medal"
    SILVER = "Silver Medal"
    BRONZE = "Bronze Medal"
    HONOURABLE_MENTION = "Honourable Mention"


class Contestant(BaseModel):
    country_name: str = Field(..., description="Full country name")
    country_code: str = Field(..., description="3-letter country code")
    given_name: str
    family_name: str
    problem_scores: list[int | None] = Field(
        ..., description="Scores for each problem (P1-P5, None if missing)"
    )
    total: int = Field(..., description="Total score")
    award: Award | None = None
    rank: int | None = None

    @property
    def full_name(self) -> str:
        return f"{self.given_name} {self.family_name}"


class APMOScoreboard(BaseModel):
    year: int = Field(..., description="Competition year")
    contestants: list[Contestant]

    @property
    def num_problems(self) -> int:
        if self.contestants:
            return len(self.contestants[0].problem_scores)
        return 5  # APMO has 5 problems

    @property
    def countries(self) -> list[str]:
        return sorted(set(c.country_name for c in self.contestants))

    def get_by_award(self, award: Award) -> list[Contestant]:
        return [c for c in self.contestants if c.award == award]

    def get_by_country(self, country_code: str) -> list[Contestant]:
        return [c for c in self.contestants if c.country_code == country_code]


class ScraperError(Exception):
    """Raised when scraping fails unexpectedly."""

    pass


# =============================================================================
# Stage 1: Download raw HTML files
# =============================================================================


def download_raw_year(year: int, raw_dir: Path, force: bool = False) -> list[Path]:
    """Download raw HTML files for a given APMO year.

    Downloads:
    - year_report.html: Contains list of participating countries
    - {country_code}.html: Individual country result pages

    Args:
        year: Competition year
        raw_dir: Directory to save raw files (should be raw/{year}/)
        force: If True, overwrite existing files

    Returns:
        List of paths to downloaded files
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []

    # Download year report
    year_report_path = raw_dir / "year_report.html"
    if force or not year_report_path.exists():
        html = fetch_year_report(year)
        year_report_path.write_text(html, encoding="utf-8")
        downloaded.append(year_report_path)

    # Extract countries from year report
    year_html = year_report_path.read_text(encoding="utf-8")
    countries = extract_countries_from_year_report(year_html)

    if not countries:
        raise ScraperError(f"No countries found for APMO {year}")

    # Download each country report
    for country_code, _country_name in countries:
        country_path = raw_dir / f"{country_code}.html"
        if force or not country_path.exists():
            try:
                html = fetch_country_report(country_code, year)
                country_path.write_text(html, encoding="utf-8")
                downloaded.append(country_path)
            except Exception as e:
                print(f"  Warning: Failed to fetch {country_code}: {e}")

    return downloaded


# =============================================================================
# Stage 2: Parse raw HTML to structured data
# =============================================================================


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


def fetch_year_report(year: int) -> str:
    """Fetch the year report page to get list of participating countries."""
    url = f"https://www.apmo-official.org/year_report/{year}"
    with httpx.Client() as client:
        response = client.get(url, timeout=30)
        response.raise_for_status()
    return response.text


def fetch_country_report(country_code: str, year: int) -> str:
    """Fetch detailed results for a specific country."""
    url = f"https://www.apmo-official.org/country_report/{country_code}/{year}"
    with httpx.Client() as client:
        response = client.get(url, timeout=30)
        response.raise_for_status()
    return response.text


def extract_countries_from_year_report(html: str) -> list[tuple[str, str]]:
    """Extract country codes and names from year report page.

    Returns list of (country_code, country_name) tuples, deduplicated.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen = {}  # code -> name mapping to deduplicate

    # Find all country links in the ranking table
    # Pattern: /country_report/CODE/YEAR
    for link in soup.find_all("a", href=re.compile(r"/country_report/([A-Z]+)/\d+")):
        href = link.get("href", "")
        match = re.search(r"/country_report/([A-Z]+)/", href)
        if match:
            code = match.group(1)
            name = link.get_text(strip=True)
            if code and name and code not in seen:
                seen[code] = name

    return list(seen.items())


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
        raise ScraperError(f"Could not find results table for {country_code}")

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


def parse_raw_year(year: int, raw_dir: Path, parsed_dir: Path, force: bool = False) -> Path | None:
    """Parse raw HTML files into structured JSON format.

    Args:
        year: Competition year
        raw_dir: Directory containing raw HTML files (raw/{year}/)
        parsed_dir: Directory to save parsed JSON (parsed/{year}/)
        force: If True, overwrite existing parsed files

    Returns:
        Path to parsed JSON file, or None if already exists and not forced
    """
    parsed_dir.mkdir(parents=True, exist_ok=True)
    output_path = parsed_dir / f"apmo_{year}.json"

    if not force and output_path.exists():
        return None

    # Read year report to get countries
    year_report_path = raw_dir / "year_report.html"
    if not year_report_path.exists():
        raise ScraperError(f"Year report not found: {year_report_path}")

    year_html = year_report_path.read_text(encoding="utf-8")
    countries = extract_countries_from_year_report(year_html)

    if not countries:
        raise ScraperError(f"No countries found in year report for APMO {year}")

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
        raise ScraperError(f"No contestants found for APMO {year}")

    # Sort by total score (descending) and compute global ranks
    all_contestants.sort(key=lambda c: (-c.total, c.family_name, c.given_name))
    all_contestants = compute_global_ranks(all_contestants)

    scoreboard = APMOScoreboard(
        year=year,
        contestants=all_contestants,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(scoreboard.model_dump_json(indent=2))

    return output_path


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


# =============================================================================
# Legacy functions (kept for backwards compatibility)
# =============================================================================


def download_apmo_year(year: int) -> APMOScoreboard:
    """Download and parse APMO results for a given year.

    This scrapes the year report to get all participating countries,
    then fetches detailed results from each country's page.
    """
    # Get list of countries from year report
    year_html = fetch_year_report(year)
    countries = extract_countries_from_year_report(year_html)

    if not countries:
        raise ScraperError(f"No countries found for APMO {year}")

    all_contestants = []

    for country_code, country_name in countries:
        try:
            country_html = fetch_country_report(country_code, year)
            contestants = parse_country_results(country_html, country_code, country_name)
            all_contestants.extend(contestants)
        except Exception as e:
            print(f"  Warning: Failed to fetch {country_name} ({country_code}): {e}")

    if not all_contestants:
        raise ScraperError(f"No contestants found for APMO {year}")

    # Sort by total score (descending) and compute global ranks
    all_contestants.sort(key=lambda c: (-c.total, c.family_name, c.given_name))
    all_contestants = compute_global_ranks(all_contestants)

    return APMOScoreboard(
        year=year,
        contestants=all_contestants,
    )


def save_to_json(scoreboard: APMOScoreboard, output_dir: Path) -> Path:
    """Save scoreboard to JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"apmo_{scoreboard.year}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(scoreboard.model_dump_json(indent=2))

    return output_path
