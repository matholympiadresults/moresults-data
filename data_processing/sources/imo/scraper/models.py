"""Pydantic models for IMO scraper data."""

from pydantic import BaseModel


class ProblemScores(BaseModel):
    """Scores for IMO problems (typically 6, but some years have 7)."""

    p1: int | None
    p2: int | None
    p3: int | None
    p4: int | None
    p5: int | None
    p6: int | None
    p7: int | None = None  # Only used in 1960


class ContestantResult(BaseModel):
    """Individual contestant result."""

    contestant_id: int | None
    name: str | None
    country_code: str
    scores: ProblemScores
    total: int
    rank: int | None
    award: str | None


class ValidationResult(BaseModel):
    """Validation results for scraped data."""

    all_totals_match: bool
    mismatches: list[dict]


class IMOYearResults(BaseModel):
    """Complete results for a single IMO year."""

    year: int
    scraped_at: str
    total_contestants: int
    results: list[ContestantResult]
    validation: ValidationResult
