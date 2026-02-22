"""APMO data ingester - transforms APMO source data into normalized database format."""

import json
from pathlib import Path

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
from sigma.sources.apmo.parser.models import (
    APMOScoreboard,
)
from sigma.sources.apmo.parser.models import (
    Award as APMOAward,
)

# APMO started in 1989 (edition 1)
APMO_START_YEAR = 1989

# APMO-specific country code mappings
APMO_CODE_MAPPING: dict[str, str] = {
    # IOC -> ISO
    "tpe": "twn",  # Taiwan (Chinese Taipei)
    "hko": "hkg",  # Hong Kong (alternative)
    "ksv": "xkx",  # Kosovo
    "phi": "phl",  # Philippines
    "mas": "mys",  # Malaysia
}


def normalize_country_code(raw_code: str) -> str:
    """Normalize APMO country code to ISO 3166-1 alpha-3.

    Args:
        raw_code: Raw country code from APMO data

    Returns:
        Normalized ISO country code (lowercase)

    Raises:
        ValueError: If the code cannot be normalized
    """
    code = raw_code.lower()

    # Check APMO-specific mappings first
    if code in APMO_CODE_MAPPING:
        return APMO_CODE_MAPPING[code]

    # Check if it's already a valid ISO code
    if code in VALID_ISO_CODES:
        return code

    raise ValueError(f"Unknown APMO country code: {raw_code!r}")


def apmo_year_to_edition(year: int) -> int:
    """Convert year to APMO edition number."""
    return year - APMO_START_YEAR + 1


def convert_award(apmo_award: APMOAward | None) -> Award | None:
    """Convert APMO award format to normalized award format."""
    if apmo_award is None:
        return None
    mapping = {
        APMOAward.GOLD: Award.GOLD,
        APMOAward.SILVER: Award.SILVER,
        APMOAward.BRONZE: Award.BRONZE,
        APMOAward.HONOURABLE_MENTION: Award.HONOURABLE_MENTION,
    }
    return mapping.get(apmo_award)


def create_competition(db: Database, scoreboard: APMOScoreboard) -> Competition:
    """Create a competition entry from a scoreboard."""
    year = scoreboard.year
    competition_id = f"apmo-{year}"

    if competition_id in db.competitions:
        return db.competitions[competition_id]

    competition = Competition(
        id=competition_id,
        source=Source.APMO,
        year=year,
        edition=apmo_year_to_edition(year),
        host_country_id=None,
        num_problems=scoreboard.num_problems,
        max_score_per_problem=7,
    )
    db.competitions[competition_id] = competition
    return competition


def ingest_scoreboard(db: Database, scoreboard: APMOScoreboard) -> dict:
    """
    Ingest a single APMO scoreboard into the database.

    Returns stats about the ingestion.
    """
    matcher = PersonMatcher(db)
    competition = create_competition(db, scoreboard)

    new_people = 0
    matched_people = 0

    for contestant in scoreboard.contestants:
        # Normalize country code and get or create country
        country_code = normalize_country_code(contestant.country_code)
        country = get_or_create_country(db, country_code)

        # Match or create person
        full_name = f"{contestant.given_name} {contestant.family_name}"
        match_result = matcher.match_or_create(
            name=full_name,
            country_id=country.id,
            source=Source.APMO,
            source_contestant_id=None,  # APMO doesn't have unique contestant IDs
            given_name=contestant.given_name,
            family_name=contestant.family_name,
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
            country_id=country.id,
            problem_scores=contestant.problem_scores,
            total=contestant.total,
            rank=contestant.rank,
            regional_rank=None,
            award=convert_award(contestant.award),
            extra_awards=None,
            source_contestant_id=None,
        )
        db.participations[participation_id] = participation

    return {
        "competition_id": competition.id,
        "year": scoreboard.year,
        "contestants": len(scoreboard.contestants),
        "new_people": new_people,
        "matched_people": matched_people,
    }


def load_scoreboard_from_file(path: Path) -> APMOScoreboard:
    """Load an APMO scoreboard from a JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return APMOScoreboard.model_validate(data)


def ingest_apmo_data(
    data_dir: Path,
    db_path: Path | None = None,
    years: list[int] | None = None,
) -> Database:
    """
    Ingest APMO data from JSON files into the normalized database.

    Args:
        data_dir: Directory containing apmo_YYYY.json files (supports both flat
                  and year-subdirectory structures)
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

    # Find all APMO files (support both flat and year-subdirectory structures)
    apmo_files = sorted(data_dir.glob("apmo_*.json"))
    if not apmo_files:
        # Try year subdirectories: parsed/{year}/apmo_{year}.json
        apmo_files = sorted(data_dir.glob("*/apmo_*.json"))

    if not apmo_files:
        raise ValueError(f"No APMO files found in {data_dir}")

    results = []
    for file_path in apmo_files:
        # Extract year from filename (apmo_2024.json -> 2024)
        year = int(file_path.stem.replace("apmo_", ""))

        if years is not None and year not in years:
            continue

        scoreboard = load_scoreboard_from_file(file_path)
        stats = ingest_scoreboard(db, scoreboard)
        results.append(stats)
        print(
            f"Ingested APMO {stats['year']}: "
            f"{stats['contestants']} contestants "
            f"({stats['new_people']} new, {stats['matched_people']} matched)"
        )

    # Save database
    if db_path:
        save_database(db, db_path)

    print(f"\nTotal: {len(results)} competitions ingested")
    print("Database contains:")
    print(f"  - {len(db.countries)} countries")
    print(f"  - {len(db.competitions)} competitions")
    print(f"  - {len(db.people)} people")
    print(f"  - {len(db.participations)} participations")

    return db
