"""Pydantic models for Baltic Way parsed data."""

from pydantic import BaseModel


class TeamResult(BaseModel):
    """A single team's result from Baltic Way."""

    team_name: str  # Raw name from source (e.g. "St. Petersburg", "Denmark")
    problem_scores: list[int]  # Always length 20, scores 0-5
    total: int
    rank: int  # Computed from totals, competition-style ties


class ValidationResult(BaseModel):
    """Validation results for parsed data."""

    all_totals_match: bool
    mismatches: list[dict]


class BWYearResults(BaseModel):
    """Complete results for a single Baltic Way year."""

    year: int
    num_teams: int
    results: list[TeamResult]
    validation: ValidationResult
