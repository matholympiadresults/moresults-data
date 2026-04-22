"""Pydantic models for normalized olympiad data."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from sigma.country_codes import ISOCountryCode


class CompetitionType(str, Enum):
    """Whether a competition has individual or team-level results."""

    INDIVIDUAL = "individual"
    TEAM = "team"


class Source(str, Enum):
    """Olympiad data sources."""

    IMO = "IMO"
    EGMO = "EGMO"
    MEMO = "MEMO"
    MEMO_TEAM = "MEMO_TEAM"
    RMM = "RMM"
    APMO = "APMO"
    BMO = "BMO"
    PAMO = "PAMO"
    BALTICWAY = "BALTICWAY"
    JBMO = "JBMO"


class Award(str, Enum):
    """Standardized award types."""

    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"
    HONOURABLE_MENTION = "honourable_mention"


class Country(BaseModel):
    """A country or territory."""

    id: str  # Format: country-{code}
    code: ISOCountryCode  # Normalized ISO 3166-1 alpha-3 code
    name: str


class Competition(BaseModel):
    """A specific olympiad event (e.g., IMO 2024)."""

    id: str  # Format: {source}-{year}
    source: Source
    year: int
    edition: int | None = None  # Edition number (e.g., 65th IMO)
    host_country_id: str | None = None  # FK to countries
    competition_type: CompetitionType = CompetitionType.INDIVIDUAL
    num_problems: int
    max_score_per_problem: int = 7


class Person(BaseModel):
    """A unique individual who can participate in multiple competitions."""

    id: str  # Auto-generated unique ID
    name: str  # Full name (always present)
    given_name: str | None = None
    family_name: str | None = None
    country_id: str | None = (
        None  # Primary/representing country (FK to countries), None for individual participants
    )
    aliases: list[str] = []  # Known name variations
    source_ids: dict[str, str | None] = {}  # IDs from each source (imo, egmo, memo)


class Participation(BaseModel):
    """A person's result at a specific competition."""

    id: str  # Format: {competition_id}-{person_id}
    competition_id: str  # FK to competitions
    person_id: str  # FK to people
    country_id: str | None = (
        None  # Country represented (may differ from person's primary), None for individual participants
    )
    is_secondary_team: bool = False  # True if competing for B-team, school team, etc.

    # Scores
    problem_scores: list[int | None]  # Array of scores (None for missing)
    total: int

    # Rankings
    rank: int | None = None  # Overall rank
    regional_rank: int | None = None  # e.g., european_rank for EGMO

    # Awards
    award: Award | None = None
    extra_awards: str | None = None  # Special prizes

    # Source metadata
    source_contestant_id: str | None = None  # Original ID from source


class TeamParticipation(BaseModel):
    """A team/country's result at a team competition."""

    id: str  # Format: {competition_id}-{country_id}
    competition_id: str  # FK to competitions
    country_id: str  # FK to countries
    problem_scores: list[int | None]  # Array of scores (None for missing)
    total: int
    rank: int | None = None
    award: Award | None = None
    extra_awards: str | None = None  # Special prizes


class Database(BaseModel):
    """The complete olympiad database."""

    version: str = "1.0"
    last_updated: datetime
    countries: dict[str, Country] = {}
    competitions: dict[str, Competition] = {}
    people: dict[str, Person] = {}
    participations: dict[str, Participation] = {}
    team_participations: dict[str, TeamParticipation] = {}
