"""Pydantic models for MEMO parsed data."""

from pydantic import BaseModel


class ContestantResult(BaseModel):
    """Individual contestant result from MEMO individual contest."""

    name: str
    country: str
    problem_scores: list[int]  # I-1 through I-4 (4 problems, 8 points each)
    total: int
    rank: int | None  # None when tied with previous rank
    award: str | None  # Gold, Silver, Bronze, or Honourable Mention


class ValidationResult(BaseModel):
    """Validation results for parsed data."""

    all_totals_match: bool
    mismatches: list[dict]


class MEMOYearResults(BaseModel):
    """Complete results for a single MEMO year (individual contest)."""

    year: int
    total_contestants: int
    results: list[ContestantResult]
    validation: ValidationResult
