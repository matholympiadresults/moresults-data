"""MEMO data ingester - transforms MEMO parsed data into normalized database format."""

import json
from pathlib import Path

from data_processing.country_codes import VALID_ISO_CODES
from data_processing.database import get_or_create_country, load_database, save_database
from data_processing.matching import PersonMatcher
from data_processing.schemas import (
    Award,
    Competition,
    CompetitionType,
    Database,
    Participation,
    Source,
    TeamParticipation,
)
from data_processing.sources.memo.parser.models import (
    MEMOTeamYearResults,
    MEMOYearResults,
)

# MEMO started in 2007 (edition 1), but online results start from 2016 (edition 10)
MEMO_START_YEAR = 2007

# MEMO uses full country names, mapping to ISO codes
MEMO_NAME_MAPPING: dict[str, str] = {
    "austria": "aut",
    "belarus": "blr",
    "bosnia and herzegovina": "bih",
    "croatia": "hrv",
    "czechia": "cze",
    "czech republic": "cze",
    "germany": "deu",
    "hungary": "hun",
    "lithuania": "ltu",
    "poland": "pol",
    "slovakia": "svk",
    "slovenia": "svn",
    "switzerland": "che",
    "ukraine": "ukr",
    "united kingdom": "gbr",
}


def normalize_country_code(raw_name: str) -> str:
    """Normalize MEMO country name to ISO 3166-1 alpha-3.

    Args:
        raw_name: Raw country name from MEMO data (e.g., "Germany", "Belarus B")

    Returns:
        Normalized ISO country code (lowercase)

    Raises:
        ValueError: If the name cannot be normalized
    """
    name = raw_name.lower()

    # Check MEMO-specific name mappings
    if name in MEMO_NAME_MAPPING:
        return MEMO_NAME_MAPPING[name]

    # Check if it's already a valid ISO code (unlikely for MEMO)
    if name in VALID_ISO_CODES:
        return name

    raise ValueError(f"Unknown MEMO country name: {raw_name!r}")


def memo_year_to_edition(year: int) -> int:
    """Convert year to MEMO edition number."""
    return year - MEMO_START_YEAR + 1


def convert_award(award_str: str | None) -> Award | None:
    """Convert MEMO award string to normalized award format."""
    if award_str is None:
        return None
    mapping = {
        "Gold": Award.GOLD,
        "Silver": Award.SILVER,
        "Bronze": Award.BRONZE,
        "Honourable Mention": Award.HONOURABLE_MENTION,
        "Honourable mention": Award.HONOURABLE_MENTION,
        "Hon. Men.": Award.HONOURABLE_MENTION,
    }
    return mapping.get(award_str)


def create_competition(db: Database, year_results: MEMOYearResults) -> Competition:
    """Create a competition entry from year results."""
    year = year_results.year
    competition_id = f"memo-{year}"

    if competition_id in db.competitions:
        return db.competitions[competition_id]

    competition = Competition(
        id=competition_id,
        source=Source.MEMO,
        year=year,
        edition=memo_year_to_edition(year),
        host_country_id=None,  # Would need additional data to determine host
        num_problems=4,  # MEMO individual has 4 problems
        max_score_per_problem=8,
    )
    db.competitions[competition_id] = competition
    return competition


def ingest_year_results(db: Database, year_results: MEMOYearResults) -> dict:
    """
    Ingest a single MEMO year's results into the database.

    Returns stats about the ingestion.
    """
    matcher = PersonMatcher(db)
    competition = create_competition(db, year_results)

    new_people = 0
    matched_people = 0

    for contestant in year_results.results:
        # Normalize country (MEMO uses full names like "Germany", "Switzerland")
        country_code = normalize_country_code(contestant.country)
        country = get_or_create_country(db, country_code)

        # Match or create person (MEMO doesn't have separate given/family names or source IDs)
        match_result = matcher.match_or_create(
            name=contestant.name,
            country_id=country.id,
            source=Source.MEMO,
            source_contestant_id=None,  # MEMO doesn't provide unique contestant IDs
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
        "year": year_results.year,
        "contestants": len(year_results.results),
        "new_people": new_people,
        "matched_people": matched_people,
    }


def load_year_results_from_dir(parsed_dir: Path) -> MEMOYearResults:
    """Load MEMO year results from a parsed directory containing scoreboard.json."""
    from data_processing.sources.memo.parser.memo_parser import get_parsed_filename

    json_file = parsed_dir / get_parsed_filename()
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)
    return MEMOYearResults.model_validate(data)


def ingest_memo_data(
    source_dir: Path,
    db_path: Path | None = None,
    years: list[int] | None = None,
) -> Database:
    """
    Ingest MEMO data from parsed directories into the normalized database.

    Args:
        source_dir: Base directory containing memo/parsed/{year}/scoreboard.json files
        db_path: Path to the database file (will be created if doesn't exist)
        years: Specific years to ingest (None = all available)

    Returns:
        The updated database
    """
    from data_processing.database import create_empty_database
    from data_processing.sources.memo.parser.memo_parser import get_parsed_filename

    # Load or create database
    if db_path and db_path.exists():
        db = load_database(db_path)
    else:
        db = create_empty_database()

    # Find all year directories with scoreboard.json
    parsed_base = source_dir / "memo" / "parsed"
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
        raise ValueError(f"No parsed MEMO files found in {parsed_base}")

    results = []
    for year, year_dir in found_years:
        if years is not None and year not in years:
            continue

        year_results = load_year_results_from_dir(year_dir)
        stats = ingest_year_results(db, year_results)
        results.append(stats)
        print(
            f"Ingested MEMO {stats['year']}: "
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


def create_team_competition(db: Database, year: int) -> Competition:
    """Create a team competition entry."""
    competition_id = f"memo-team-{year}"

    if competition_id in db.competitions:
        return db.competitions[competition_id]

    competition = Competition(
        id=competition_id,
        source=Source.MEMO_TEAM,
        year=year,
        edition=memo_year_to_edition(year),
        host_country_id=None,
        competition_type=CompetitionType.TEAM,
        num_problems=8,  # MEMO team has 8 problems
        max_score_per_problem=8,
    )
    db.competitions[competition_id] = competition
    return competition


def ingest_team_year_results(db: Database, team_results: MEMOTeamYearResults) -> dict:
    """
    Ingest a single MEMO team year's results into the database.

    Returns stats about the ingestion.
    """
    competition = create_team_competition(db, team_results.year)

    for team in team_results.results:
        # Normalize country
        country_code = normalize_country_code(team.country)
        country = get_or_create_country(db, country_code)

        # Create team participation
        participation_id = f"{competition.id}-{country.id}"
        team_participation = TeamParticipation(
            id=participation_id,
            competition_id=competition.id,
            country_id=country.id,
            problem_scores=team.problem_scores,
            total=team.total,
            rank=team.rank,
            award=convert_award(team.award),
            extra_awards=None,
        )
        db.team_participations[participation_id] = team_participation

    return {
        "competition_id": competition.id,
        "year": team_results.year,
        "teams": len(team_results.results),
    }


def load_team_year_results_from_dir(parsed_dir: Path) -> MEMOTeamYearResults:
    """Load MEMO team year results from a parsed directory."""
    from data_processing.sources.memo.parser.memo_team_parser import (
        get_team_parsed_filename,
    )

    json_file = parsed_dir / get_team_parsed_filename()
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)
    return MEMOTeamYearResults.model_validate(data)


def ingest_memo_team_data(
    source_dir: Path,
    db_path: Path | None = None,
    years: list[int] | None = None,
) -> Database:
    """
    Ingest MEMO team data from parsed directories into the normalized database.

    Args:
        source_dir: Base directory containing memo/parsed/{year}/team_scoreboard.json files
        db_path: Path to the database file (will be created if doesn't exist)
        years: Specific years to ingest (None = all available)

    Returns:
        The updated database
    """
    from data_processing.database import create_empty_database
    from data_processing.sources.memo.parser.memo_team_parser import (
        get_team_parsed_filename,
    )

    # Load or create database
    if db_path and db_path.exists():
        db = load_database(db_path)
    else:
        db = create_empty_database()

    # Find all year directories with team_scoreboard.json
    parsed_base = source_dir / "memo" / "parsed"
    year_dirs = sorted(parsed_base.glob("*/"))

    found_years = []
    for year_dir in year_dirs:
        if not year_dir.is_dir():
            continue
        team_file = year_dir / get_team_parsed_filename()
        if team_file.exists():
            try:
                year = int(year_dir.name)
                found_years.append((year, year_dir))
            except ValueError:
                continue

    if not found_years:
        print(f"No parsed MEMO team files found in {parsed_base}")
        return db

    results = []
    for year, year_dir in found_years:
        if years is not None and year not in years:
            continue

        team_results = load_team_year_results_from_dir(year_dir)
        stats = ingest_team_year_results(db, team_results)
        results.append(stats)
        print(f"Ingested MEMO Team {stats['year']}: {stats['teams']} teams")

    # Save database
    if db_path:
        save_database(db, db_path)

    print(f"\nTotal: {len(results)} team competitions ingested")
    print("Database contains:")
    print(f"  - {len(db.countries)} countries")
    print(f"  - {len(db.competitions)} competitions")
    print(f"  - {len(db.team_participations)} team participations")

    return db
