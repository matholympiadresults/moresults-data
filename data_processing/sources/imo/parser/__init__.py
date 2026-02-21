"""IMO parser - parses raw HTML to structured data."""

from .imo_parser import (
    ALLOW_EMPTY_NAMES_YEARS,
    ALLOW_EMPTY_RANKS_YEARS,
    ALLOW_EMPTY_SCORES_YEARS,
    ALLOW_UNKNOWN_PERSON_YEARS,
    MAX_SCORE_BY_YEAR,
    NUM_PROBLEMS_BY_YEAR,
    UNKNOWN_PERSON,
    ParseError,
    parse_html,
    parse_year,
    parse_years,
)
from .models import ContestantResult, IMOYearResults, ProblemScores, ValidationResult

__all__ = [
    "parse_html",
    "parse_year",
    "parse_years",
    "ParseError",
    "ProblemScores",
    "ContestantResult",
    "ValidationResult",
    "IMOYearResults",
    "MAX_SCORE_BY_YEAR",
    "NUM_PROBLEMS_BY_YEAR",
    "UNKNOWN_PERSON",
    "ALLOW_EMPTY_SCORES_YEARS",
    "ALLOW_EMPTY_NAMES_YEARS",
    "ALLOW_EMPTY_RANKS_YEARS",
    "ALLOW_UNKNOWN_PERSON_YEARS",
]
