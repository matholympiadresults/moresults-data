"""Pydantic models for RMM parsed data."""

from pydantic import BaseModel


class ContestantResult(BaseModel):
    """Individual contestant result from RMM."""

    name: str
    country: str  # 3-letter country code (e.g., "CHN", "USA", "ROU")
    problem_scores: list[int]  # P1 through P6 (6 problems, 7 points each)
    total: int
    rank: int | None  # None when tied with previous rank
    award: str | None  # GOLD, SILVER, BRONZE, or HON. MEN.
    is_official_team: bool  # True if contestant is part of official team (marked with *)
    is_online: bool  # True if contestant is from online competition


class ValidationResult(BaseModel):
    """Validation results for parsed data."""

    all_totals_match: bool
    mismatches: list[dict]


class RMMYearResults(BaseModel):
    """Complete results for a single RMM year."""

    year: int
    parsed_at: str
    total_contestants: int
    results: list[ContestantResult]
    validation: ValidationResult
