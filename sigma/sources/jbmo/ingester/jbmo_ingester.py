"""JBMO data ingester - transforms JBMO source data into normalized database format."""

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
from sigma.sources.jbmo.parser.models import (
    JBMOYearResults,
)

# JBMO started in 1997 (edition 1)
JBMO_START_YEAR = 1997

# JBMO-specific country code mappings
JBMO_CODE_MAPPING: dict[str, str] = {
    # IOC -> ISO
    "bul": "bgr",  # Bulgaria (old IOC code)
    "gre": "grc",  # Greece
    "hel": "grc",  # Greece (Hellas)
    "cyp": "cyp",  # Cyprus
    "kyp": "cyp",  # Cyprus alternate
    "fyr": "mkd",  # FYR Macedonia
    "unk": "gbr",  # United Kingdom
    "sui": "che",  # Switzerland
    "mas": "mys",  # Malaysia
    "phi": "phl",  # Philippines
    "rom": "rou",  # Romania (old IOC code)
    "val": "rou",  # Romania guest team (Valachie) - JBMO 2010
    "rez": "rou",  # Romania reserve contestants - JBMO 2010
    "alt": "rou",  # Romania alternative team - JBMO 2016
    # B-team codes
    "mda(b)": "mda",  # Moldova B
    "rou(b)": "rou",  # Romania B
    "roub": "rou",  # Romania B (JBMO 2026 spelling)
    "tur(b)": "tur",  # Turkey B
    "mkd-b": "mkd",  # North Macedonia B
    "b&h": "bih",  # Bosnia & Herzegovina B
}

# JBMO country name mappings
JBMO_NAME_MAPPING: dict[str, str] = {
    "greece": "grc",
    "hellas": "grc",
    "cyprus": "cyp",
    "turkey": "tur",
    "türkiye": "tur",
    "turkiye": "tur",
    "turkyie": "tur",  # Typo in JBMO 2023 data
    "romania": "rou",
    "roumania": "rou",
    "bulgaria": "bgr",
    "serbia": "srb",
    "serbia b": "srb",  # Serbia B-team - JBMO 2015
    "croatia": "hrv",
    "montenegro": "mne",
    "north macedonia": "mkd",
    "northern macedonia": "mkd",
    "macedonia": "mkd",
    "n. macedonia": "mkd",
    "albania": "alb",
    "albania b": "alb",
    "moldova": "mda",
    "republic of moldova": "mda",
    "bosnia and herzegovina": "bih",
    "bosnia and hercegovina": "bih",  # Typo in JBMO 2023 data
    "bosnia & herzegovina": "bih",
    "bosnia&herzegovina": "bih",
    "azerbaijan": "aze",
    "kazakhstan": "kaz",
    "uzbekistan": "uzb",
    "turkmenistan": "tkm",
    "kyrgyzstan": "kgz",
    "tajikistan": "tjk",
    "indonesia": "idn",
    "iran": "irn",
    "iraq": "irq",
    "italy": "ita",
    "saudi arabia": "sau",
    "united kingdom": "gbr",
    "philippines": "phl",
    "syria": "syr",
    "jordan": "jor",
    "georgia": "geo",
    "kosovo": "xkx",
    "slovenia": "svn",
    "hungary": "hun",
    "ukraine": "ukr",
    "pakistan": "pak",
    "mongolia": "mng",
    "vietnam": "vnm",
    "viet nam": "vnm",
    "thailand": "tha",
    "bangladesh": "bgd",
    "armenia": "arm",
    "united arab emirates": "are",
    "qatar": "qat",
    "tunisia": "tun",
    "libya": "lby",
    "oman": "omn",
    "kuwait": "kwt",
    "bahrain": "bhr",
    "nigeria": "nga",
    "south africa": "zaf",
    "myanmar": "mmr",
    "nepal": "npl",
    "sri lanka": "lka",
    "egypt": "egy",
    "morocco": "mar",
    "portugal": "prt",
    "spain": "esp",
    "france": "fra",
    "germany": "deu",
    "austria": "aut",
    "belgium": "bel",
    "czech republic": "cze",
    "slovakia": "svk",
    "poland": "pol",
    "latvia": "lva",
    "lithuania": "ltu",
    "estonia": "est",
    "finland": "fin",
    "sweden": "swe",
    "norway": "nor",
    "denmark": "dnk",
    "iceland": "isl",
    "ireland": "irl",
    "netherlands": "nld",
    "luxembourg": "lux",
    "switzerland": "che",
    "liechtenstein": "lie",
    "san marino": "smr",
    "monaco": "mco",
    "andorra": "and",
    "malta": "mlt",
    "russia": "rus",
    "russian federation": "rus",
    "china": "chn",
    "japan": "jpn",
    "south korea": "kor",
    "republic of korea": "kor",
    "north korea": "prk",
    "taiwan": "twn",
    "hong kong": "hkg",
    "singapore": "sgp",
    "malaysia": "mys",
    "india": "ind",
    "australia": "aus",
    "new zealand": "nzl",
    "canada": "can",
    "united states": "usa",
    "mexico": "mex",
    "brazil": "bra",
    "argentina": "arg",
    "chile": "chl",
    "colombia": "col",
    "peru": "per",
    "venezuela": "ven",
    "ecuador": "ecu",
    "uruguay": "ury",
    "paraguay": "pry",
    "bolivia": "bol",
    "costa rica": "cri",
    "panama": "pan",
    "cuba": "cub",
    "dominican republic": "dom",
    "el salvador": "slv",
    "guatemala": "gtm",
    "honduras": "hnd",
    "nicaragua": "nic",
    "trinidad and tobago": "tto",
    "jamaica": "jam",
    "belarus": "blr",
    "israel": "isr",
    "palestine": "pse",
    "lebanon": "lbn",
    "cambodia": "khm",
    "laos": "lao",
    "brunei": "brn",
    "papua new guinea": "png",
    "fiji": "fji",
    "samoa": "wsm",
    "tonga": "ton",
}

# B-team codes specific to JBMO
B_TEAM_CODES: set[str] = {"mda(b)", "rou(b)", "roub", "tur(b)", "mkd-b", "b&h"}


def normalize_country_code(raw_code: str) -> str:
    """Normalize JBMO country code to ISO 3166-1 alpha-3.

    Args:
        raw_code: Raw country code or name from JBMO data

    Returns:
        Normalized ISO country code (lowercase)

    Raises:
        ValueError: If the code cannot be normalized
    """
    # Normalize whitespace (collapse newlines and multiple spaces)
    raw_code = re.sub(r"\s+", " ", raw_code).strip()
    # Strip trailing numbers/spaces (e.g., "ROU 1" -> "ROU", "BGR 2" -> "BGR")
    stripped = re.sub(r"\s*\d+$", "", raw_code).strip()
    code = stripped.lower()

    # Check JBMO-specific code mappings first
    if code in JBMO_CODE_MAPPING:
        return JBMO_CODE_MAPPING[code]

    # Check if it's already a valid ISO code
    if code in VALID_ISO_CODES:
        return code

    # Try as a country name
    if code in JBMO_NAME_MAPPING:
        return JBMO_NAME_MAPPING[code]

    raise ValueError(f"Unknown JBMO country code: {raw_code!r}")


def get_team_label(raw_code: str) -> str | None:
    """Extract team label from raw country code.

    Returns None for the country's primary team, "B" for known B-teams.
    """
    raw_code = re.sub(r"\s+", " ", raw_code).strip()
    stripped = re.sub(r"\s*\d+$", "", raw_code).strip()
    code = stripped.lower()

    if code in B_TEAM_CODES:
        return "B"

    # Check for " - B" or " B" suffix in names
    if raw_code.lower().endswith(" - b") or raw_code.lower().endswith(" b"):
        return "B"

    # Check for "-B" suffix (e.g., "MKD-B")
    if stripped.lower().endswith("-b"):
        return "B"

    return None


def jbmo_year_to_edition(year: int) -> int:
    """Convert year to JBMO edition number."""
    return year - JBMO_START_YEAR + 1


def convert_award(award_str: str | None) -> Award | None:
    """Convert JBMO award string to normalized award format."""
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


def create_competition(db: Database, year_results: JBMOYearResults) -> Competition:
    """Create a competition entry from year results."""
    year = year_results.year
    competition_id = f"jbmo-{year}"

    if competition_id in db.competitions:
        return db.competitions[competition_id]

    competition = Competition(
        id=competition_id,
        source=Source.JBMO,
        year=year,
        edition=jbmo_year_to_edition(year),
        host_country_id=None,
        num_problems=4,  # JBMO has 4 problems
        max_score_per_problem=10,  # Each problem is worth 10 points
    )
    db.competitions[competition_id] = competition
    return competition


def ingest_year_results(db: Database, year_results: JBMOYearResults) -> dict:
    """
    Ingest a single JBMO year's results into the database.

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
            team_label = get_team_label(raw_country)
        except ValueError as e:
            print(f"Warning: {e}, skipping contestant {contestant.name}")
            continue

        # Match or create person
        match_result = matcher.match_or_create(
            name=contestant.name,
            country_id=country.id,
            source=Source.JBMO,
            source_contestant_id=None,
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
        "contestants": len(year_results.results),
        "new_people": new_people,
        "matched_people": matched_people,
    }


def load_year_results_from_file(path: Path) -> JBMOYearResults:
    """Load JBMO year results from a JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return JBMOYearResults.model_validate(data)


def ingest_jbmo_data(
    data_dir: Path,
    db_path: Path | None = None,
    years: list[int] | None = None,
) -> Database:
    """
    Ingest JBMO data from JSON files into the normalized database.

    Args:
        data_dir: Directory containing jbmo_YYYY.json files
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

    # Find all JBMO files (support both flat and year-subdirectory structures)
    jbmo_files = sorted(data_dir.glob("jbmo_*.json"))
    if not jbmo_files:
        # Try year subdirectories: parsed/{year}/jbmo_{year}.json
        jbmo_files = sorted(data_dir.glob("*/jbmo_*.json"))

    if not jbmo_files:
        raise ValueError(f"No JBMO files found in {data_dir}")

    results = []
    for file_path in jbmo_files:
        # Extract year from filename (jbmo_2025.json -> 2025)
        year = int(file_path.stem.replace("jbmo_", ""))

        if years is not None and year not in years:
            continue

        year_results = load_year_results_from_file(file_path)
        stats = ingest_year_results(db, year_results)
        results.append(stats)
        print(
            f"Ingested JBMO {stats['year']}: "
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
