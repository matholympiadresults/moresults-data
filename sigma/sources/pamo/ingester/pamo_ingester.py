"""PAMO data ingester - transforms PAMO parsed data into normalized database format."""

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
from sigma.sources.pamo.parser.models import (
    PAMOYearResults,
)

# PAMO started in 1987 (edition 1)
PAMO_START_YEAR = 1987

# PAMO-specific country code mappings
# PAMO uses 3-letter codes that are usually ISO, but some need mapping
PAMO_CODE_MAPPING: dict[str, str] = {
    # IOC -> ISO
    "ngr": "nga",  # Nigeria
    "alg": "dza",  # Algeria
    "saf": "zaf",  # South Africa
    "zim": "zwe",  # Zimbabwe
    "mor": "mar",  # Morocco
    "tan": "tza",  # Tanzania
    "tog": "tgo",  # Togo
    "les": "lso",  # Lesotho
    "bot": "bwa",  # Botswana
    "mlw": "mwi",  # Malawi
    "drc": "cod",  # DR Congo
    "con": "cog",  # Republic of Congo
    "cob": "cog",  # Republic of Congo (alternative)
    "sie": "sle",  # Sierra Leone
    "gam": "gmb",  # Gambia
    "esw": "swz",  # Eswatini
    "mtn": "mrt",  # Mauritania
    "mau": "mus",  # Mauritius
    "cam": "cmr",  # Cameroon
    "ivc": "civ",  # Ivory Coast (Côte d'Ivoire)
    "mts": "mus",  # Mauritius (alternative code)
    "lea": "lbr",  # Liberia
}


def normalize_country_code(raw_code: str) -> str:
    """Normalize PAMO country code to ISO 3166-1 alpha-3.

    Args:
        raw_code: Raw country code from PAMO data

    Returns:
        Normalized ISO country code (lowercase)

    Raises:
        ValueError: If the code cannot be normalized
    """
    code = raw_code.lower()

    # Check PAMO-specific mappings first
    if code in PAMO_CODE_MAPPING:
        return PAMO_CODE_MAPPING[code]

    # Check if it's already a valid ISO code
    if code in VALID_ISO_CODES:
        return code

    raise ValueError(f"Unknown PAMO country code: {raw_code!r}")


def pamo_year_to_edition(year: int) -> int:
    """Convert year to PAMO edition number."""
    return year - PAMO_START_YEAR + 1


def convert_award(award_str: str | None) -> Award | None:
    """Convert PAMO award string to normalized award format."""
    if award_str is None:
        return None
    mapping = {
        "GOLD": Award.GOLD,
        "SILVER": Award.SILVER,
        "BRONZE": Award.BRONZE,
        "HM": Award.HONOURABLE_MENTION,
    }
    return mapping.get(award_str)


def create_competition(db: Database, year_results: PAMOYearResults) -> Competition:
    """Create a competition entry from year results."""
    year = year_results.year
    competition_id = f"pamo-{year}"

    if competition_id in db.competitions:
        return db.competitions[competition_id]

    competition = Competition(
        id=competition_id,
        source=Source.PAMO,
        year=year,
        edition=pamo_year_to_edition(year),
        host_country_id=None,  # Would need additional data to determine host
        num_problems=6,  # PAMO has 6 problems
        max_score_per_problem=7,
    )
    db.competitions[competition_id] = competition
    return competition


def ingest_year_results(
    db: Database,
    year_results: PAMOYearResults,
) -> dict:
    """
    Ingest a single PAMO year's results into the database.

    Returns stats about the ingestion.
    """
    matcher = PersonMatcher(db)
    competition = create_competition(db, year_results)

    new_people = 0
    matched_people = 0

    for contestant in year_results.results:
        # Normalize country code and get or create country
        country_code = normalize_country_code(contestant.country)
        country = get_or_create_country(db, country_code)

        # Match or create person (PAMO doesn't have separate given/family names or source IDs)
        match_result = matcher.match_or_create(
            name=contestant.name,
            country_id=country.id,
            source=Source.PAMO,
            source_contestant_id=None,  # PAMO doesn't provide unique contestant IDs
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
            extra_awards=contestant.pamo_g_award,  # Store PAMO-G award as extra
            source_contestant_id=None,
        )
        db.participations[participation_id] = participation

    return {
        "competition_id": competition.id,
        "year": year_results.year,
        "contestants": new_people + matched_people,
        "new_people": new_people,
        "matched_people": matched_people,
    }


def load_year_results_from_dir(parsed_dir: Path) -> PAMOYearResults:
    """Load PAMO year results from a parsed directory containing scoreboard.json."""
    from sigma.sources.pamo.parser.pamo_parser import get_parsed_filename

    json_file = parsed_dir / get_parsed_filename()
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)
    return PAMOYearResults.model_validate(data)


def ingest_pamo_data(
    source_dir: Path,
    db_path: Path | None = None,
    years: list[int] | None = None,
) -> Database:
    """
    Ingest PAMO data from parsed directories into the normalized database.

    Args:
        source_dir: Base directory containing pamo/parsed/{year}/scoreboard.json files
        db_path: Path to the database file (will be created if doesn't exist)
        years: Specific years to ingest (None = all available)

    Returns:
        The updated database
    """
    from sigma.sources.pamo.parser.pamo_parser import get_parsed_filename

    # Load or create database
    if db_path and db_path.exists():
        db = load_database(db_path)
    else:
        db = create_empty_database()

    # Find all year directories with scoreboard.json
    parsed_base = source_dir / "pamo" / "parsed"
    year_dirs = sorted(parsed_base.glob("*/"))

    found_years = []
    for year_dir in year_dirs:
        if not year_dir.is_dir():
            continue
        scoreboard_file = year_dir / get_parsed_filename()
        if scoreboard_file.exists():
            try:
                year = int(year_dir.name)
                found_years.append((year, year_dir))
            except ValueError:
                continue

    if not found_years:
        raise ValueError(f"No parsed PAMO files found in {parsed_base}")

    results = []
    for year, year_dir in found_years:
        if years is not None and year not in years:
            continue

        year_results = load_year_results_from_dir(year_dir)
        stats = ingest_year_results(db, year_results)
        results.append(stats)
        print(
            f"Ingested PAMO {stats['year']}: "
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
