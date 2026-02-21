"""BMO data ingester - transforms BMO source data into normalized database format."""

import json
import re
from pathlib import Path

from data_processing.country_codes import VALID_ISO_CODES
from data_processing.database import get_or_create_country, load_database, save_database
from data_processing.matching import PersonMatcher
from data_processing.schemas import (
    Award,
    Competition,
    Database,
    Participation,
    Source,
)
from data_processing.sources.bmo.scraper.models import (
    BMOYearResults,
)

# BMO started in 1984 (edition 1)
BMO_START_YEAR = 1984

# B-team codes specific to BMO
B_TEAM_CODES = {"turb"}

# BMO-specific country code mappings
BMO_CODE_MAPPING: dict[str, str] = {
    # IOC -> ISO
    "gre": "grc",  # Greece
    "hel": "grc",  # Greece (Hellas)
    "cyp": "cyp",  # Cyprus
    "kyp": "cyp",  # Cyprus alternate
    "fyr": "mkd",  # FYR Macedonia
    "unk": "gbr",  # United Kingdom
    "alg": "dza",  # Algeria
    "sui": "che",  # Switzerland
    "mas": "mys",  # Malaysia
    # B-team codes
    "turb": "tur",  # Turkey B
}

# BMO country name mappings
BMO_NAME_MAPPING: dict[str, str] = {
    "serbia - b": "srb",
    "romania b": "rou",
    "roumania": "rou",
    "fyr macedonia": "mkd",
    "turkmanistan": "tkm",
    "bosnia&herzegovina": "bih",
    "bosnia and herzegovina": "bih",
    "greece": "grc",
    "cyprus": "cyp",
    "turkey": "tur",
    "türkiye": "tur",
    "romania": "rou",
    "bulgaria": "bgr",
    "serbia": "srb",
    "croatia": "hrv",
    "montenegro": "mne",
    "north macedonia": "mkd",
    "macedonia": "mkd",
    "albania": "alb",
    "moldova": "mda",
    "republic of moldova": "mda",
    "uzbekistan": "uzb",
    "kazakhstan": "kaz",
    "italy": "ita",
    "united kingdom": "gbr",
    "saudi arabia": "sau",
    "azerbaijan": "aze",
    "turkmenistan": "tkm",
    "kyrgyzstan": "kgz",
}


def normalize_country_code(raw_code: str) -> str:
    """Normalize BMO country code to ISO 3166-1 alpha-3.

    Args:
        raw_code: Raw country code or name from BMO data

    Returns:
        Normalized ISO country code (lowercase)

    Raises:
        ValueError: If the code cannot be normalized
    """
    # Strip trailing numbers/spaces (e.g., "ROU 1" -> "ROU", "BGR 2" -> "BGR")
    stripped = re.sub(r"\s*\d+$", "", raw_code).strip()
    code = stripped.lower()

    # Check BMO-specific code mappings first
    if code in BMO_CODE_MAPPING:
        return BMO_CODE_MAPPING[code]

    # Check if it's already a valid ISO code
    if code in VALID_ISO_CODES:
        return code

    # Try as a country name
    if code in BMO_NAME_MAPPING:
        return BMO_NAME_MAPPING[code]

    raise ValueError(f"Unknown BMO country code: {raw_code!r}")


def is_b_team(raw_code: str) -> bool:
    """Check if a country code represents a B-team.

    Only returns True for known B-team codes.
    Does NOT flag valid ISO codes like 'srb' (Serbia) as B-teams.
    """
    # Strip trailing numbers first
    stripped = re.sub(r"\s*\d+$", "", raw_code).strip()
    code = stripped.lower()

    # Check explicit B-team codes
    if code in B_TEAM_CODES:
        return True

    # Check for " - B" or " B" suffix in names
    if raw_code.lower().endswith(" - b") or raw_code.lower().endswith(" b"):
        return True

    return False


def bmo_year_to_edition(year: int) -> int:
    """Convert year to BMO edition number."""
    return year - BMO_START_YEAR + 1


def convert_award(award_str: str | None) -> Award | None:
    """Convert BMO award string to normalized award format."""
    if award_str is None:
        return None
    mapping = {
        "Gold": Award.GOLD,
        "GOLD": Award.GOLD,
        "Silver": Award.SILVER,
        "SILVER": Award.SILVER,
        "Bronze": Award.BRONZE,
        "BRONZE": Award.BRONZE,
        "Honourable Mention": Award.HONOURABLE_MENTION,
        "Honourable mention": Award.HONOURABLE_MENTION,
        "HONOURABLE MENTION": Award.HONOURABLE_MENTION,
        "HM": Award.HONOURABLE_MENTION,
    }
    return mapping.get(award_str)


def create_competition(db: Database, year_results: BMOYearResults) -> Competition:
    """Create a competition entry from year results."""
    year = year_results.year
    competition_id = f"bmo-{year}"

    if competition_id in db.competitions:
        return db.competitions[competition_id]

    competition = Competition(
        id=competition_id,
        source=Source.BMO,
        year=year,
        edition=bmo_year_to_edition(year),
        host_country_id=None,  # Would need additional data to determine host
        num_problems=4,  # BMO has 4 problems
        max_score_per_problem=10,  # Each problem is worth 10 points
    )
    db.competitions[competition_id] = competition
    return competition


def ingest_year_results(db: Database, year_results: BMOYearResults) -> dict:
    """
    Ingest a single BMO year's results into the database.

    Returns stats about the ingestion.
    """
    matcher = PersonMatcher(db)
    competition = create_competition(db, year_results)

    new_people = 0
    matched_people = 0

    for contestant in year_results.results:
        # Get or create country
        try:
            raw_country = contestant.country
            country_code = normalize_country_code(raw_country)
            country = get_or_create_country(db, country_code)
            secondary_team = is_b_team(raw_country)
        except ValueError as e:
            print(f"Warning: {e}, skipping contestant {contestant.name}")
            continue

        # Match or create person
        match_result = matcher.match_or_create(
            name=contestant.name,
            country_id=country.id,
            source=Source.BMO,
            source_contestant_id=None,  # BMO doesn't provide unique contestant IDs
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
            is_secondary_team=secondary_team,
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
        "year": year_results.year,
        "contestants": len(year_results.results),
        "new_people": new_people,
        "matched_people": matched_people,
    }


def load_year_results_from_file(path: Path) -> BMOYearResults:
    """Load BMO year results from a JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return BMOYearResults.model_validate(data)


def ingest_bmo_data(
    data_dir: Path,
    db_path: Path | None = None,
    years: list[int] | None = None,
) -> Database:
    """
    Ingest BMO data from JSON files into the normalized database.

    Args:
        data_dir: Directory containing bmo_YYYY.json files
        db_path: Path to the database file (will be created if doesn't exist)
        years: Specific years to ingest (None = all available)

    Returns:
        The updated database
    """
    # Load or create database
    if db_path and db_path.exists():
        db = load_database(db_path)
    else:
        from data_processing.database import create_empty_database

        db = create_empty_database()

    # Find all BMO files (support both flat and year-subdirectory structures)
    bmo_files = sorted(data_dir.glob("bmo_*.json"))
    if not bmo_files:
        # Try year subdirectories: parsed/{year}/bmo_{year}.json
        bmo_files = sorted(data_dir.glob("*/bmo_*.json"))

    if not bmo_files:
        raise ValueError(f"No BMO files found in {data_dir}")

    results = []
    for file_path in bmo_files:
        # Extract year from filename (bmo_2025.json -> 2025)
        year = int(file_path.stem.replace("bmo_", ""))

        if years is not None and year not in years:
            continue

        year_results = load_year_results_from_file(file_path)
        stats = ingest_year_results(db, year_results)
        results.append(stats)
        print(
            f"Ingested BMO {stats['year']}: "
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
