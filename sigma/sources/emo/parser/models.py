"""Pydantic models for EMO scraper data."""

from pydantic import BaseModel


class ContestantResult(BaseModel):
    """Individual contestant result from EMO."""

    name: str
    country: str  # Country code as it appears in the source (e.g. "UKR A")
    contestant_number: int | None = None  # Per-team contestant number (CSV "#" column)
    problem_scores: list[int | None]  # P1..P8
    total: int
    rank: int | None
    award: str | None  # Gold, Silver, Bronze, Honourable Mention
    given_name: str | None = None
    family_name: str | None = None


class ValidationResult(BaseModel):
    """Validation results for scraped data."""

    all_totals_match: bool
    mismatches: list[dict]


class EMOYearResults(BaseModel):
    """Complete results for a single EMO year."""

    year: int
    source_url: str
    source_type: str  # "csv"
    total_contestants: int
    results: list[ContestantResult]
    validation: ValidationResult
