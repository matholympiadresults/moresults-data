"""Baltic Way data ingester - transforms parsed data into normalized database format.

Baltic Way is a team competition, so we create TeamParticipation records (not Participation/Person).
"""

import json
from pathlib import Path

from sigma.database import (
    create_empty_database,
    get_or_create_country,
    load_database,
    save_database,
)
from sigma.schemas import (
    Competition,
    CompetitionType,
    Database,
    Source,
    TeamParticipation,
)
from sigma.sources.balticway.parser.models import BWYearResults

# Baltic Way started in 1990 (edition 1), but results available from 1992
BW_START_YEAR = 1990

# Map raw team names to ISO 3166-1 alpha-3 codes
BW_NAME_MAPPING: dict[str, str] = {
    "denmark": "dnk",
    "estonia": "est",
    "finland": "fin",
    "germany": "deu",
    "iceland": "isl",
    "latvia": "lva",
    "lithuania": "ltu",
    "norway": "nor",
    "poland": "pol",
    "sweden": "swe",
    "ukraine": "ukr",
    "belarus": "blr",
    "valgevene": "blr",  # Estonian for Belarus
    "belgium": "bel",
    "holland": "nld",
    "ireland": "irl",
    "israel": "isr",
    "south africa": "zaf",
    "st. petersburg": "rus",
    "saint petersburg": "rus",
    "denamrk": "dnk",  # Typo in 2017 source
}


def normalize_team_name(raw_name: str) -> str:
    """Normalize a Baltic Way team name to ISO 3166-1 alpha-3 code.

    Args:
        raw_name: Raw team name from parsed data (e.g. "St. Petersburg", "Denmark")

    Returns:
        Normalized ISO country code (lowercase)

    Raises:
        ValueError: If the name cannot be mapped
    """
    name = raw_name.strip().lower()

    if name in BW_NAME_MAPPING:
        return BW_NAME_MAPPING[name]

    raise ValueError(f"Unknown Baltic Way team name: {raw_name!r}")


def create_competition(db: Database, year: int) -> Competition:
    """Create a competition entry for a Baltic Way year."""
    competition_id = f"balticway-{year}"

    if competition_id in db.competitions:
        return db.competitions[competition_id]

    competition = Competition(
        id=competition_id,
        source=Source.BALTICWAY,
        competition_type=CompetitionType.TEAM,
        year=year,
        edition=year - BW_START_YEAR + 1,
        num_problems=20,
        max_score_per_problem=5,
    )
    db.competitions[competition_id] = competition
    return competition


def ingest_year_results(db: Database, year_results: BWYearResults) -> dict:
    """Ingest a single year's results into the database.

    Returns stats about the ingestion.
    """
    competition = create_competition(db, year_results.year)
    teams_ingested = 0

    for team in year_results.results:
        country_code = normalize_team_name(team.team_name)
        country = get_or_create_country(db, country_code)

        participation_id = f"{competition.id}-{country.id}"
        participation = TeamParticipation(
            id=participation_id,
            competition_id=competition.id,
            country_id=country.id,
            problem_scores=team.problem_scores,
            total=team.total,
            rank=team.rank,
            award=None,  # Baltic Way has no awards
        )
        db.team_participations[participation_id] = participation
        teams_ingested += 1

    return {
        "competition_id": competition.id,
        "year": year_results.year,
        "teams": teams_ingested,
    }


def load_year_results_from_dir(parsed_dir: Path) -> BWYearResults:
    """Load Baltic Way year results from a parsed directory."""
    from sigma.sources.balticway.parser.bw_parser import get_parsed_filename

    json_file = parsed_dir / get_parsed_filename()
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)
    return BWYearResults.model_validate(data)


def ingest_balticway_data(
    source_dir: Path,
    db_path: Path | None = None,
    years: list[int] | None = None,
) -> Database:
    """Ingest Baltic Way data from parsed directories into the normalized database.

    Args:
        source_dir: Base directory containing balticway/parsed/{year}/scoreboard.json files
        db_path: Path to the database file (will be created if doesn't exist)
        years: Specific years to ingest (None = all available)

    Returns:
        The updated database
    """
    from sigma.sources.balticway.parser.bw_parser import get_parsed_filename

    # Load or create database
    if db_path and db_path.exists():
        db = load_database(db_path)
    else:
        db = create_empty_database()

    # Find all year directories with scoreboard.json
    parsed_base = source_dir / "balticway" / "parsed"
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
        raise ValueError(f"No parsed Baltic Way files found in {parsed_base}")

    results = []
    for year, year_dir in found_years:
        if years is not None and year not in years:
            continue

        year_results = load_year_results_from_dir(year_dir)
        stats = ingest_year_results(db, year_results)
        results.append(stats)
        print(f"Ingested Baltic Way {stats['year']}: {stats['teams']} teams")

    # Save database
    if db_path:
        save_database(db, db_path)

    print(f"\nTotal: {len(results)} competitions ingested")
    print("Database contains:")
    print(f"  - {len(db.countries)} countries")
    print(f"  - {len(db.competitions)} competitions")
    print(f"  - {len(db.team_participations)} team participations")

    return db
