"""EMO data ingester - transforms EMO source data into normalized database format."""

import json
import re
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
from sigma.sources.emo.parser.models import EMOYearResults

# EMO launched in 2026 (edition 1).
EMO_START_YEAR = 2026

# EMO-specific country code mappings (IOC -> ISO).
EMO_CODE_MAPPING: dict[str, str] = {
    "sui": "che",  # Switzerland
    "ger": "deu",  # Germany
    "gre": "grc",  # Greece
    "ned": "nld",  # Netherlands
    "ksv": "xkx",  # Kosovo
}


def normalize_country_code(raw_code: str) -> str:
    """Normalize EMO country code to ISO 3166-1 alpha-3.

    Strips A/B team suffixes (e.g. "UKR A" -> "ukr", "LTU B" -> "ltu").
    """
    cleaned = re.sub(r"\s+", " ", raw_code).strip()
    # Drop trailing " A" / " B" / " 1" / " 2" team or contestant suffixes.
    stripped = re.sub(r"\s+[A-Za-z0-9]+$", "", cleaned).strip() or cleaned
    code = stripped.lower()

    if code in EMO_CODE_MAPPING:
        return EMO_CODE_MAPPING[code]
    if code in VALID_ISO_CODES:
        return code

    # Fall back to the raw code (without suffix stripping) in case the
    # country itself was a multi-word string we shouldn't have split.
    raw_lower = cleaned.lower()
    if raw_lower in EMO_CODE_MAPPING:
        return EMO_CODE_MAPPING[raw_lower]
    if raw_lower in VALID_ISO_CODES:
        return raw_lower

    raise ValueError(f"Unknown EMO country code: {raw_code!r}")


def is_b_team(raw_code: str) -> bool:
    """Check if a country code represents a B-team."""
    cleaned = re.sub(r"\s+", " ", raw_code).strip().lower()
    return cleaned.endswith(" b") or cleaned.endswith("-b")


def emo_year_to_edition(year: int) -> int:
    """Convert year to EMO edition number."""
    return year - EMO_START_YEAR + 1


def convert_award(award_str: str | None) -> Award | None:
    """Convert EMO award string to normalized award format."""
    if award_str is None:
        return None
    mapping = {
        "Gold": Award.GOLD,
        "Silver": Award.SILVER,
        "Bronze": Award.BRONZE,
        "Honourable Mention": Award.HONOURABLE_MENTION,
        "HM": Award.HONOURABLE_MENTION,
    }
    return mapping.get(award_str)


def create_competition(db: Database, year_results: EMOYearResults) -> Competition:
    """Create a competition entry from year results."""
    year = year_results.year
    competition_id = f"emo-{year}"

    if competition_id in db.competitions:
        return db.competitions[competition_id]

    competition = Competition(
        id=competition_id,
        source=Source.EMO,
        year=year,
        edition=emo_year_to_edition(year),
        host_country_id=None,
        num_problems=8,
        max_score_per_problem=7,
    )
    db.competitions[competition_id] = competition
    return competition


def ingest_year_results(db: Database, year_results: EMOYearResults) -> dict:
    """Ingest a single EMO year's results into the database."""
    matcher = PersonMatcher(db)
    competition = create_competition(db, year_results)

    new_people = 0
    matched_people = 0

    for contestant in year_results.results:
        try:
            raw_country = contestant.country
            country_code = normalize_country_code(raw_country)
            country = get_or_create_country(db, country_code)
            secondary_team = is_b_team(raw_country)
        except ValueError as e:
            print(f"Warning: {e}, skipping contestant {contestant.name}")
            continue

        match_result = matcher.match_or_create(
            name=contestant.name,
            country_id=country.id,
            source=Source.EMO,
            source_contestant_id=None,
            given_name=contestant.given_name,
            family_name=contestant.family_name,
        )

        if match_result.is_new:
            new_people += 1
        else:
            matched_people += 1

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


def load_year_results_from_file(path: Path) -> EMOYearResults:
    """Load EMO year results from a JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return EMOYearResults.model_validate(data)


def ingest_emo_data(
    data_dir: Path,
    db_path: Path | None = None,
    years: list[int] | None = None,
) -> Database:
    """Ingest EMO data from JSON files into the normalized database."""
    if db_path and db_path.exists():
        db = load_database(db_path)
    else:
        from sigma.database import create_empty_database

        db = create_empty_database()

    emo_files = sorted(data_dir.glob("emo_*.json"))
    if not emo_files:
        emo_files = sorted(data_dir.glob("*/emo_*.json"))

    if not emo_files:
        raise ValueError(f"No EMO files found in {data_dir}")

    results = []
    for file_path in emo_files:
        year = int(file_path.stem.replace("emo_", ""))

        if years is not None and year not in years:
            continue

        year_results = load_year_results_from_file(file_path)
        stats = ingest_year_results(db, year_results)
        results.append(stats)
        print(
            f"Ingested EMO {stats['year']}: "
            f"{stats['contestants']} contestants "
            f"({stats['new_people']} new, {stats['matched_people']} matched)"
        )

    if db_path:
        save_database(db, db_path)

    print(f"\nTotal: {len(results)} competitions ingested")
    print("Database contains:")
    print(f"  - {len(db.countries)} countries")
    print(f"  - {len(db.competitions)} competitions")
    print(f"  - {len(db.people)} people")
    print(f"  - {len(db.participations)} participations")

    return db
