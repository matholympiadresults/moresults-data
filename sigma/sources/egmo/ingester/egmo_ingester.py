"""EGMO data ingester - transforms parsed EGMO data into normalized database format."""

from pathlib import Path

from sigma.country_codes import VALID_ISO_CODES
from sigma.database import get_or_create_country, load_database, save_database
from sigma.matching import PersonMatcher
from sigma.schemas import (
    Award,
    Competition,
    Database,
    Participation,
    Source,
)

from ..parser.models import EGMOYearResults

# EGMO B-team codes (4-letter codes ending in 'b')
EGMO_B_TEAM_CODES = {
    "blrb",
    "geob",
    "hunb",
    "itab",
    "ksvb",
    "nldb",
    "roub",
    "suib",
    "svnb",
    "turb",
    "ukrb",
}

# EGMO-specific country code mappings (IOC -> ISO)
EGMO_CODE_MAPPING: dict[str, str] = {
    # IOC codes used by EGMO
    "sui": "che",  # Switzerland
    "ger": "deu",  # Germany
    "gre": "grc",  # Greece
    "ned": "nld",  # Netherlands
    "den": "dnk",  # Denmark
    "por": "prt",  # Portugal
    "unk": "gbr",  # United Kingdom
    "hel": "grc",  # Greece (Hellas)
    "chi": "chl",  # Chile
    "ksv": "xkx",  # Kosovo
    "alg": "dza",  # Algeria
    "saf": "zaf",  # South Africa
    # B-team codes -> base country
    "blrb": "blr",
    "geob": "geo",
    "hunb": "hun",
    "itab": "ita",
    "ksvb": "xkx",
    "nldb": "nld",
    "roub": "rou",
    "suib": "che",
    "svnb": "svn",
    "turb": "tur",
    "ukrb": "ukr",
}


def normalize_country_code(raw_code: str) -> str:
    """Normalize EGMO country code to ISO 3166-1 alpha-3.

    Args:
        raw_code: Raw country code from EGMO data

    Returns:
        Normalized ISO country code (lowercase)

    Raises:
        ValueError: If the code cannot be normalized
    """
    code = raw_code.lower()

    # Check EGMO-specific mappings first
    if code in EGMO_CODE_MAPPING:
        return EGMO_CODE_MAPPING[code]

    # Check if it's already a valid ISO code
    if code in VALID_ISO_CODES:
        return code

    raise ValueError(f"Unknown EGMO country code: {raw_code!r}")


def is_b_team(raw_code: str) -> bool:
    """Check if a country code represents a B-team."""
    return raw_code.lower() in EGMO_B_TEAM_CODES


def convert_award(award_str: str | None) -> Award | None:
    """Convert EGMO award string to normalized award format."""
    if award_str is None:
        return None
    mapping = {
        "Gold Medal": Award.GOLD,
        "Silver Medal": Award.SILVER,
        "Bronze Medal": Award.BRONZE,
        "Honourable Mention": Award.HONOURABLE_MENTION,
    }
    return mapping.get(award_str)


def create_competition(db: Database, data: EGMOYearResults) -> Competition:
    """Create a competition entry from parsed data."""
    competition_id = f"egmo-{data.year}"

    if competition_id in db.competitions:
        return db.competitions[competition_id]

    competition = Competition(
        id=competition_id,
        source=Source.EGMO,
        year=data.year,
        edition=data.edition,
        host_country_id=None,  # Would need additional data to determine host
        num_problems=data.num_problems,
        max_score_per_problem=7,
    )
    db.competitions[competition_id] = competition
    return competition


def ingest_results(db: Database, data: EGMOYearResults) -> dict:
    """
    Ingest parsed EGMO data into the database.

    Returns stats about the ingestion.
    """
    matcher = PersonMatcher(db)
    competition = create_competition(db, data)

    new_people = 0
    matched_people = 0

    for contestant in data.results:
        # Normalize country code and get or create country
        raw_code = contestant.country_code
        country_code = normalize_country_code(raw_code)
        country = get_or_create_country(db, country_code)
        secondary_team = is_b_team(raw_code)

        full_name = f"{contestant.given_name} {contestant.family_name}"
        match_result = matcher.match_or_create(
            name=full_name,
            country_id=country.id,
            source=Source.EGMO,
            source_contestant_id=str(contestant.person_id),
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
            is_secondary_team=secondary_team,
            problem_scores=contestant.problem_scores,
            total=contestant.total,
            rank=contestant.rank,
            regional_rank=contestant.european_rank,
            award=convert_award(contestant.award),
            extra_awards=contestant.extra_awards,
            source_contestant_id=str(contestant.person_id),
        )
        db.participations[participation_id] = participation

    return {
        "competition_id": competition.id,
        "year": data.year,
        "contestants": len(data.results),
        "new_people": new_people,
        "matched_people": matched_people,
    }


def load_results_from_file(path: Path) -> EGMOYearResults:
    """Load parsed EGMO data from a JSON file."""
    import json

    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return EGMOYearResults.model_validate(data)


def find_parsed_files(parsed_base_dir: Path) -> list[tuple[int, Path]]:
    """Find all parsed EGMO files in yearly subdirectories.

    Args:
        parsed_base_dir: Base directory containing year subdirectories

    Returns:
        List of (year, file_path) tuples, sorted by year
    """
    files = []

    if not parsed_base_dir.exists():
        return files

    for year_dir in parsed_base_dir.iterdir():
        if year_dir.is_dir() and year_dir.name.isdigit():
            year = int(year_dir.name)
            # Look for egmo_YYYY.json in the year directory
            json_file = year_dir / f"egmo_{year}.json"
            if json_file.exists():
                files.append((year, json_file))

    return sorted(files, key=lambda x: x[0])


def ingest_egmo_data(
    data_dir: Path,
    db_path: Path | None = None,
    years: list[int] | None = None,
) -> Database:
    """
    Ingest EGMO data from parsed JSON files into the normalized database.

    Args:
        data_dir: Base directory containing year subdirectories with egmo_YYYY.json files
        db_path: Path to the database file (will be created if doesn't exist)
        years: Specific years to ingest (None = all available)

    Returns:
        The updated database
    """
    # Load or create database
    if db_path and db_path.exists():
        db = load_database(db_path)
    else:
        from sigma.database import create_empty_database

        db = create_empty_database()

    # Find all EGMO files in yearly directories
    all_files = find_parsed_files(data_dir)

    if not all_files:
        raise ValueError(f"No EGMO files found in {data_dir}")

    results = []
    for year, file_path in all_files:
        if years is not None and year not in years:
            continue

        data = load_results_from_file(file_path)
        stats = ingest_results(db, data)
        results.append(stats)
        print(
            f"Ingested EGMO {stats['year']}: "
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
