"""Pydantic models for PAMO parsed data."""

from pydantic import BaseModel


class ContestantResult(BaseModel):
    """Individual contestant result from PAMO."""

    name: str
    country: str  # 3-letter country code (e.g., "TUN", "ZAF", "NGA")
    problem_scores: list[int | None]  # P1 through P6 (6 problems, 7 points each, None if missing)
    total: int
    rank: int | None  # None when tied with previous rank
    award: str | None  # GOLD, SILVER, BRONZE, or HM
    pamo_g_award: str | None  # PAMO-G award (for girls), if any


class ValidationResult(BaseModel):
    """Validation results for parsed data."""

    all_totals_match: bool
    mismatches: list[dict]


class PAMOYearResults(BaseModel):
    """Complete results for a single PAMO year."""

    year: int
    edition: int | None = None
    total_contestants: int
    results: list[ContestantResult]
    validation: ValidationResult
