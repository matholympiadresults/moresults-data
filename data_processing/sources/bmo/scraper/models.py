"""Pydantic models for BalcanMO scraper data."""

from pydantic import BaseModel


class ContestantResult(BaseModel):
    """Individual contestant result from BalcanMO."""

    name: str
    country: str  # Country name or code (varies by source)
    problem_scores: list[int | None]  # P1-P4 (10 points each, max 40 total)
    total: int
    rank: int | None  # None when tied with previous rank
    award: str | None  # Gold, Silver, Bronze, Honourable Mention


class ValidationResult(BaseModel):
    """Validation results for scraped data."""

    all_totals_match: bool
    mismatches: list[dict]


class BMOYearResults(BaseModel):
    """Complete results for a single BalcanMO year."""

    year: int
    source_url: str
    source_type: str  # "html" or "pdf"
    total_contestants: int
    results: list[ContestantResult]
    validation: ValidationResult
