"""Pydantic models for JBMO scraper data."""

from pydantic import BaseModel


class ContestantResult(BaseModel):
    """Individual contestant result from JBMO."""

    name: str
    country: str  # Country name or code (varies by source)
    problem_scores: list[int | None]  # P1-P4 (10 points each, max 40 total)
    total: int
    rank: int | None  # None when tied with previous rank
    award: str | None  # Gold, Silver, Bronze, Honourable Mention
    given_name: str | None = None
    family_name: str | None = None


class ValidationResult(BaseModel):
    """Validation results for scraped data."""

    all_totals_match: bool
    mismatches: list[dict]


class JBMOYearResults(BaseModel):
    """Complete results for a single JBMO year."""

    year: int
    source_url: str
    source_type: str  # "html" or "pdf"
    total_contestants: int
    results: list[ContestantResult]
    validation: ValidationResult
