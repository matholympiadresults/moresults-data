"""RMM data ingester - transforms RMM source data into normalized database format."""

import json
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
from sigma.sources.rmm.parser.models import (
    RMMYearResults,
)

# RMM started in 2008 (edition 1)
RMM_START_YEAR = 2008

# Romanian secondary teams (B team, F team, school teams)
# These are excluded by default, only ROU (main team) is ingested
ROMANIAN_SECONDARY_TEAMS = {"roub", "rouf", "vianu", "vianu2"}

# B-team codes: 4-letter codes ending in 'b' that represent B-teams
# Excludes valid 3-letter ISO codes that happen to end in 'b' (srb, alb, uzb)
B_TEAM_CODES = {"roub", "blrb", "hunb", "geob", "itab", "ukrb", "svnb", "nldb", "ksvb", "suib"}

# RMM-specific country code mappings
RMM_CODE_MAPPING: dict[str, str] = {
    # Legacy/alternative codes
    "brz": "bra",  # Brazil
    "bul": "bgr",  # Bulgaria
    "rom": "rou",  # Romania
    "roma": "rou",  # Romania A team (2009)
    "unk": "gbr",  # United Kingdom
    # Regional/school teams
    "sofia": "bgr",  # Sofia, Bulgaria
    "varna": "bgr",  # Varna, Bulgaria
    "irkutsk": "rus",  # Irkutsk, Russia
    "yakutsk": "rus",  # Yakutsk, Russia (2008)
    # B-team codes -> base country
    "roub": "rou",
    "romb": "rou",
    "romf": "rou",
    "rouf": "rou",
    "blrb": "blr",
    "hunb": "hun",
    "geob": "geo",
    "itab": "ita",
    "ukrb": "ukr",
    "svnb": "svn",
    "nldb": "nld",
    "ksvb": "xkx",
    "suib": "che",
    "turb": "tur",
    # Special teams (resolved per-contestant via COMBINED_TEAM_MEMBERS)
    "vianu": "unknown",  # Tudor Vianu National College (school team)
    "vianu2": "unknown",  # Tudor Vianu secondary team (2010)
}

# Combined team (TND/TBT) members mapped to their actual country.
# Keyed by (year, lowercase name).
COMBINED_TEAM_MEMBERS: dict[tuple[int, str], str] = {
    # TND - The Nordic Team
    (2020, "andreas alberg"): "nor",
    (2020, "fredrik ekholm"): "swe",
    (2020, "jingdan hua"): "dnk",
    (2020, "daniel arone"): "fin",
    (2021, "andreas alberg"): "nor",
    (2021, "manja rönngren"): "swe",
    (2021, "magnus olsen"): "dnk",
    (2021, "juho arala"): "fin",
    (2023, "daniel pham nguyen"): "dnk",
    (2023, "benedikt vilji magnússon"): "isl",
    (2023, "aino aulanko"): "fin",
    (2023, "mikael häglund"): "swe",
    (2024, "daniil akimov"): "fin",
    (2024, "maia reffs vistisen"): "dnk",
    (2024, "vebjorn holm-gjerde"): "nor",
    (2024, "mingdao zou"): "swe",
    (2025, "ruiming zhang"): "swe",
    (2025, "andreas arnfred nielsen"): "dnk",
    (2025, "zhongyi li"): "fin",
    (2025, "lénárd dániel virág"): "fin",
    (2025, "justin jia"): "nor",
    (2025, "jiachen mi"): "swe",
    (2026, "skomantas urbonas"): "nor",
    (2026, "theo karlin"): "swe",
    (2026, "ohto katila"): "fin",
    (2026, "ziyi xiao"): "dnk",
    (2026, "vladyslav levchenko"): "swe",
    # TBT - The Baltic Team
    (2025, "kiryl krutsko"): "ltu",
    (2025, "armands tidrikis"): "lva",
    (2025, "bronislav shatil"): "est",
    (2025, "kaarel toomet"): "est",
    (2026, "kaarel toomet"): "est",
    (2026, "petr shvab"): "lva",
    (2026, "kristjan lepp"): "est",
    (2026, "adomas juodis"): "ltu",
    (2026, "luka vladimirovs"): "lva",
    (2026, "pijus piekus"): "ltu",
}

COMBINED_TEAM_CODES = {"tbt", "tnd"}


def normalize_country_code(raw_code: str) -> str:
    """Normalize RMM country code to ISO 3166-1 alpha-3.

    Args:
        raw_code: Raw country code from RMM data

    Returns:
        Normalized ISO country code (lowercase)

    Raises:
        ValueError: If the code cannot be normalized
    """
    code = raw_code.lower()

    # Check RMM-specific mappings first
    if code in RMM_CODE_MAPPING:
        return RMM_CODE_MAPPING[code]

    # Check if it's already a valid ISO code
    if code in VALID_ISO_CODES:
        return code

    raise ValueError(f"Unknown RMM country code: {raw_code!r}")


def get_team_label(raw_code: str) -> str | None:
    """Extract team label from raw country code.

    Returns None for the country's primary team. Returns a label like "B", "F",
    or "VIANU" for known secondary teams. Does NOT flag valid ISO codes like
    'srb' (Serbia) as B-teams.
    """
    code = raw_code.lower()
    if code in B_TEAM_CODES:
        return "B"
    if code == "rouf":
        return "F"
    if code == "vianu":
        return "VIANU"
    if code == "vianu2":
        return "VIANU2"
    return None


def rmm_year_to_edition(year: int) -> int:
    """Convert year to RMM edition number."""
    return year - RMM_START_YEAR + 1


def convert_award(award_str: str | None) -> Award | None:
    """Convert RMM award string to normalized award format."""
    if award_str is None:
        return None
    mapping = {
        "GOLD": Award.GOLD,
        "SILVER": Award.SILVER,
        "BRONZE": Award.BRONZE,
        "HON. MEN.": Award.HONOURABLE_MENTION,
    }
    return mapping.get(award_str)


def create_competition(db: Database, year_results: RMMYearResults) -> Competition:
    """Create a competition entry from year results."""
    year = year_results.year
    competition_id = f"rmm-{year}"

    if competition_id in db.competitions:
        return db.competitions[competition_id]

    # 2008 and 2009 used 4 problems; 2010 onwards used 6.
    num_problems = len(year_results.results[0].problem_scores) if year_results.results else 6
    competition = Competition(
        id=competition_id,
        source=Source.RMM,
        year=year,
        edition=rmm_year_to_edition(year),
        host_country_id=None,  # Would need additional data to determine host
        num_problems=num_problems,
        max_score_per_problem=7,
    )
    db.competitions[competition_id] = competition
    return competition


def ingest_year_results(
    db: Database,
    year_results: RMMYearResults,
    include_all_romanian_teams: bool = False,
) -> dict:
    """
    Ingest a single RMM year's results into the database.

    Only ingests actual participants (is_online=False), not online contestants.
    By default, only ingests ROU (main Romanian team), not secondary teams.

    Args:
        db: Database to ingest into
        year_results: Year results to ingest
        include_all_romanian_teams: If True, include ROUB, ROUF, VIANU teams

    Returns stats about the ingestion.
    """
    matcher = PersonMatcher(db)
    competition = create_competition(db, year_results)

    new_people = 0
    matched_people = 0
    skipped_online = 0
    skipped_secondary_teams = 0

    for contestant in year_results.results:
        # Skip online contestants - only ingest actual participants
        if contestant.is_online:
            skipped_online += 1
            continue

        # Skip contestants with invalid country codes (like "-")
        if contestant.country == "-":
            continue

        # Resolve combined team members (TBT/TND) to their actual country
        raw_code = contestant.country
        if raw_code.lower() in COMBINED_TEAM_CODES:
            key = (year_results.year, contestant.name.lower())
            if key not in COMBINED_TEAM_MEMBERS:
                raise ValueError(
                    f"Unknown combined team member: {contestant.name} "
                    f"({raw_code}) in {year_results.year}"
                )
            country_code = COMBINED_TEAM_MEMBERS[key]
        else:
            country_code = normalize_country_code(raw_code)

        # Skip Romanian secondary teams unless explicitly included
        if not include_all_romanian_teams and raw_code.lower() in ROMANIAN_SECONDARY_TEAMS:
            skipped_secondary_teams += 1
            continue

        # Get or create country
        country = get_or_create_country(db, country_code)
        team_label = get_team_label(raw_code)

        # Match or create person (RMM doesn't have separate given/family names or source IDs)
        match_result = matcher.match_or_create(
            name=contestant.name,
            country_id=country.id,
            source=Source.RMM,
            source_contestant_id=None,  # RMM doesn't provide unique contestant IDs
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
            team_label=team_label,
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
        "contestants": new_people + matched_people,
        "new_people": new_people,
        "matched_people": matched_people,
        "skipped_online": skipped_online,
        "skipped_secondary_teams": skipped_secondary_teams,
    }


def load_year_results_from_file(path: Path) -> RMMYearResults:
    """Load RMM year results from a JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return RMMYearResults.model_validate(data)


def ingest_rmm_data(
    data_dir: Path,
    db_path: Path | None = None,
    years: list[int] | None = None,
    include_all_romanian_teams: bool = False,
) -> Database:
    """
    Ingest RMM data from JSON files into the normalized database.

    Args:
        data_dir: Directory containing rmm_YYYY.json files
        db_path: Path to the database file (will be created if doesn't exist)
        years: Specific years to ingest (None = all available)
        include_all_romanian_teams: If True, include ROUB, ROUF, VIANU teams
            (default: False, only ROU main team is ingested)

    Returns:
        The updated database
    """
    # Load or create database
    if db_path and db_path.exists():
        db = load_database(db_path)
    else:
        from sigma.database import create_empty_database

        db = create_empty_database()

    # Find all RMM files
    rmm_files = sorted(data_dir.glob("rmm_*.json"))

    if not rmm_files:
        raise ValueError(f"No RMM files found in {data_dir}")

    results = []
    for file_path in rmm_files:
        # Extract year from filename (rmm_2025.json -> 2025)
        year = int(file_path.stem.replace("rmm_", ""))

        if years is not None and year not in years:
            continue

        year_results = load_year_results_from_file(file_path)
        stats = ingest_year_results(db, year_results, include_all_romanian_teams)
        results.append(stats)
        skipped_parts = []
        if stats["skipped_online"]:
            skipped_parts.append(f"{stats['skipped_online']} online")
        if stats["skipped_secondary_teams"]:
            skipped_parts.append(f"{stats['skipped_secondary_teams']} secondary ROU teams")
        skipped_str = f", skipped: {', '.join(skipped_parts)}" if skipped_parts else ""
        print(
            f"  {stats['year']}: "
            f"{stats['contestants']} contestants "
            f"({stats['new_people']} new, {stats['matched_people']} matched{skipped_str})"
        )

    # Save database
    if db_path:
        save_database(db, db_path)

    return db
