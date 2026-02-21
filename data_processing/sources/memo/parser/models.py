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


class TeamResult(BaseModel):
    """Team/country result from MEMO team contest."""

    country: str
    problem_scores: list[int]  # T-1 through T-8 (8 problems, 8 points each)
    total: int
    rank: int | None  # Inferred from row order
    award: str | None  # Gold, Silver, Bronze


class MEMOTeamYearResults(BaseModel):
    """Complete results for a single MEMO year (team contest)."""

    year: int
    total_teams: int
    results: list[TeamResult]
    validation: ValidationResult
