"""EGMO parse module - parses raw HTML and CSV into structured data."""

from .egmo_parser import ParseError, parse_raw, save_json, scrape_person_ids
from .models import ContestantResult, EGMOYearResults, ValidationResult

__all__ = [
    "ParseError",
    "parse_raw",
    "save_json",
    "scrape_person_ids",
    "ContestantResult",
    "EGMOYearResults",
    "ValidationResult",
]
