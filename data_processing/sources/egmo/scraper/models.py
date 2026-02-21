"""Pydantic models for EGMO scraper data."""

from pydantic import BaseModel


class ContestantResult(BaseModel):
    """Individual contestant result from EGMO."""

    person_id: int  # Unique person ID from egmo.org
    country_name: str
    country_code: str  # 3-letter country code
    contestant_code: str  # e.g., "BEL1", "USA2"
    given_name: str
    family_name: str
    problem_scores: list[int | None]  # P1-P8 (7 points each)
    total: int
    rank: int | None
    european_rank: int | None
    award: str | None  # "Gold Medal", "Silver Medal", etc.
    extra_awards: str | None

    @property
    def full_name(self) -> str:
        return f"{self.given_name} {self.family_name}"


class ValidationResult(BaseModel):
    """Validation results for scraped data."""

    all_totals_match: bool
    mismatches: list[dict]


class EGMOYearResults(BaseModel):
    """Complete results for a single EGMO year."""

    year: int
    edition: int  # EGMO edition number (e.g., 1 for 2012)
    scraped_at: str
    source_url: str
    total_contestants: int
    num_problems: int
    results: list[ContestantResult]
    validation: ValidationResult

    @property
    def countries(self) -> list[str]:
        return sorted(set(c.country_name for c in self.results))
