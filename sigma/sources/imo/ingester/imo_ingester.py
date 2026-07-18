"""
IMO Ingest Module

Ingests parsed data into the normalized database.
This is the third stage of the data pipeline: download -> parse -> ingest.
"""

import json
import re
from pathlib import Path

import click

from sigma.country_codes import VALID_ISO_CODES
from sigma.database import (
    create_empty_database,
    get_or_create_country,
    load_database,
    save_database,
)
from sigma.matching import PersonMatcher
from sigma.schemas import (
    Award,
    Competition,
    Database,
    Participation,
    Source,
)
from sigma.sources.imo.parser import (
    MAX_SCORE_BY_YEAR,
    NUM_PROBLEMS_BY_YEAR,
    UNKNOWN_PERSON,
    ContestantResult,
    IMOYearResults,
)

# IMO started in 1959 (edition 1)
IMO_START_YEAR = 1959

# IMO-specific country code mappings
IMO_CODE_MAPPING: dict[str, str] = {
    # IOC -> ISO
    "sui": "che",  # Switzerland
    "ger": "deu",  # Germany
    "gre": "grc",  # Greece
    "ned": "nld",  # Netherlands
    "den": "dnk",  # Denmark
    "por": "prt",  # Portugal
    "chi": "chl",  # Chile
    "phi": "phl",  # Philippines
    "par": "pry",  # Paraguay
    "uae": "are",  # UAE
    "unk": "gbr",  # United Kingdom
    "hel": "grc",  # Greece (Hellas)
    "alg": "dza",  # Algeria
    "bah": "bhr",  # Bahrain
    "saf": "zaf",  # South Africa
    "mas": "mys",  # Malaysia
    "bru": "brn",  # Brunei
    # Historical codes
    "czs": "csk",  # Czechoslovakia
    "uss": "uss",  # Soviet Union
    "yug": "yug",  # Yugoslavia
    "scg": "scg",  # Serbia and Montenegro
    "gdr": "gdr",  # East Germany
    # Alternative codes
    "tpe": "twn",  # Taiwan (Chinese Taipei)
    "hko": "hkg",  # Hong Kong (alternative)
    "ksv": "xkx",  # Kosovo
}

# Pattern for individual participant codes (C01-C99)
INDIVIDUAL_PARTICIPANT_PATTERN = re.compile(r"^C\d{2}$")


def sanitize_name(name: str) -> str:
    """Sanitize a name by removing leading '? ' (unknown first name marker in IMO source)."""
    if name.startswith("? "):
        return name[2:]
    return name


def normalize_country_code(raw_code: str | None) -> str | None:
    """Normalize IMO country code to ISO 3166-1 alpha-3.

    Args:
        raw_code: Raw country code from IMO data, or None for individual
            participants who compete without a country (new website format).

    Returns:
        Normalized ISO country code (lowercase), or None for individual participants

    Raises:
        ValueError: If the code cannot be normalized
    """
    # Individual participants: legacy site used C01-C99 codes (handled below),
    # the redesigned site leaves the country blank (None).
    if raw_code is None:
        return None

    code = raw_code.upper()

    # Check for individual participants (C01-C99)
    if INDIVIDUAL_PARTICIPANT_PATTERN.match(code):
        return None  # Individual participant, no country

    code = raw_code.lower()

    # Check IMO-specific mappings first
    if code in IMO_CODE_MAPPING:
        return IMO_CODE_MAPPING[code]

    # Check if it's already a valid ISO code
    if code in VALID_ISO_CODES:
        return code

    raise ValueError(f"Unknown IMO country code: {raw_code!r}")


class IngestError(Exception):
    """Raised when ingestion fails."""

    pass


def imo_year_to_edition(year: int) -> int:
    """
    Convert year to IMO edition number.

    Note: IMO was not held in 1980 due to the Moscow Olympics boycott.
    """
    if year < 1980:
        return year - IMO_START_YEAR + 1
    else:
        # After 1979, subtract 1 to account for the missed year
        return year - IMO_START_YEAR


def convert_award(award_str: str | None) -> Award | None:
    """Convert IMO award string to normalized award format."""
    if award_str is None:
        return None
    award_lower = award_str.lower()
    if "gold" in award_lower:
        return Award.GOLD
    elif "silver" in award_lower:
        return Award.SILVER
    elif "bronze" in award_lower:
        return Award.BRONZE
    elif "honourable" in award_lower or "honorable" in award_lower:
        return Award.HONOURABLE_MENTION
    return None


def create_competition(db: Database, year_results: IMOYearResults) -> Competition:
    """Create a competition entry from year results."""
    year = year_results.year
    competition_id = f"imo-{year}"

    if competition_id in db.competitions:
        return db.competitions[competition_id]

    num_problems = NUM_PROBLEMS_BY_YEAR.get(year, 6)
    max_score = MAX_SCORE_BY_YEAR.get(year, 7)

    competition = Competition(
        id=competition_id,
        source=Source.IMO,
        year=year,
        edition=imo_year_to_edition(year),
        host_country_id=None,
        num_problems=num_problems,
        max_score_per_problem=max_score,
    )
    db.competitions[competition_id] = competition
    return competition


def scores_to_list(contestant: ContestantResult) -> list[int | None]:
    """Convert ProblemScores to a list."""
    scores = contestant.scores
    return [scores.p1, scores.p2, scores.p3, scores.p4, scores.p5, scores.p6, scores.p7]


def ingest_year_results(db: Database, year_results: IMOYearResults) -> dict:
    """
    Ingest a single IMO year's results into the database.

    Returns stats about the ingestion.
    """
    matcher = PersonMatcher(db)
    competition = create_competition(db, year_results)

    new_people = 0
    matched_people = 0
    skipped_unknown = 0

    for contestant in year_results.results:
        # Skip unknown persons (those without contestant IDs)
        if contestant.name == UNKNOWN_PERSON or contestant.contestant_id is None:
            skipped_unknown += 1
            continue

        # Normalize country code (returns None for individual participants like C01-C99)
        country_code = normalize_country_code(contestant.country_code)

        # Get country (may be None for individual participants)
        if country_code is not None:
            country = get_or_create_country(db, country_code)
            country_id = country.id
        else:
            country_id = None

        # Match or create person
        match_result = matcher.match_or_create(
            name=sanitize_name(contestant.name),
            country_id=country_id,
            source=Source.IMO,
            source_contestant_id=str(contestant.contestant_id),
        )

        if match_result.is_new:
            new_people += 1
        else:
            matched_people += 1

        # Create participation
        participation_id = f"{competition.id}-{match_result.person_id}"
        participation = Participation(
            id=participation_id,
            competition_id=competition.id,
            person_id=match_result.person_id,
            country_id=country_id,
            problem_scores=scores_to_list(contestant),
            total=contestant.total,
            rank=contestant.rank,
            regional_rank=None,
            award=convert_award(contestant.award),
            extra_awards=None,
            source_contestant_id=str(contestant.contestant_id),
        )
        db.participations[participation_id] = participation

    return {
        "competition_id": competition.id,
        "year": year_results.year,
        "contestants": len(year_results.results),
        "new_people": new_people,
        "matched_people": matched_people,
        "skipped_unknown": skipped_unknown,
    }


def load_year_results_from_file(path: Path) -> IMOYearResults:
    """Load IMO year results from a JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return IMOYearResults.model_validate(data)


def get_year_dir(base_dir: Path, year: int) -> Path:
    """Get the directory for a specific year."""
    return base_dir / str(year)


def get_parsed_json_path(base_dir: Path, year: int) -> Path:
    """Get the path to the parsed JSON file for a specific year."""
    return get_year_dir(base_dir, year) / "results.json"


def discover_years(input_dir: Path) -> list[int]:
    """
    Discover available years from yearly directory structure.

    Looks for directories like input_dir/2024/results.json
    """
    years = []
    for year_dir in input_dir.iterdir():
        if year_dir.is_dir() and year_dir.name.isdigit():
            json_path = year_dir / "results.json"
            if json_path.exists():
                years.append(int(year_dir.name))
    return sorted(years)


def ingest_years(
    input_dir: Path,
    db_path: Path | None = None,
    years: list[int] | None = None,
) -> Database:
    """
    Ingest parsed IMO data from JSON files into the normalized database.

    Expects yearly directory structure:
        imo/parsed/2024/results.json
        imo/parsed/2023/results.json
        ...

    Args:
        input_dir: Base directory containing yearly subdirectories with results.json
        db_path: Path to the database file (will be created if doesn't exist)
        years: Specific years to ingest (None = all available)

    Returns:
        The updated database
    """
    # Load or create database
    if db_path and db_path.exists():
        db = load_database(db_path)
    else:
        db = create_empty_database()

    # Discover available years
    available_years = discover_years(input_dir)

    if not available_years:
        raise IngestError(f"No yearly directories with results.json found in {input_dir}")

    # Filter to requested years
    target_years = available_years
    if years is not None:
        target_years = [y for y in available_years if y in years]

    results = []
    for year in target_years:
        json_path = get_parsed_json_path(input_dir, year)
        year_results = load_year_results_from_file(json_path)
        stats = ingest_year_results(db, year_results)
        results.append(stats)
        skipped_msg = f", {stats['skipped_unknown']} unknown" if stats["skipped_unknown"] else ""
        click.echo(
            f"  {stats['year']}: "
            f"{stats['contestants']} contestants "
            f"({stats['new_people']} new, {stats['matched_people']} matched{skipped_msg})"
        )

    # Save database
    if db_path:
        save_database(db, db_path)

    return db


def print_database_stats(db: Database) -> None:
    """Print database statistics."""
    click.echo()
    click.echo("Database contains:")
    click.echo(f"  - {len(db.countries)} countries")
    click.echo(f"  - {len(db.competitions)} competitions")
    click.echo(f"  - {len(db.people)} people")
    click.echo(f"  - {len(db.participations)} participations")
