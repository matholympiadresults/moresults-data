"""EMO raw data parser.

Parses raw CSV files into structured EMOYearResults.
"""

from pathlib import Path

from ..downloader import get_source_type, get_source_url
from .models import ContestantResult, EMOYearResults, ValidationResult
from .parsers.base import BaseParser
from .parsers.csv_2026 import Parser2026


class ParseError(Exception):
    """Raised when parsing fails unexpectedly."""

    pass


_PARSER_MAP: dict[int, type[BaseParser]] = {
    2026: Parser2026,
}


def get_parser(year: int) -> BaseParser:
    """Get the appropriate parser for a given year."""
    if year not in _PARSER_MAP:
        from ..downloader import AVAILABLE_YEARS

        raise ValueError(f"No parser available for year {year}. Available years: {AVAILABLE_YEARS}")
    return _PARSER_MAP[year](year)


def validate_totals(results: list[ContestantResult]) -> list[dict]:
    """Validate that totals match sum of individual scores. Returns mismatches."""
    mismatches = []
    for r in results:
        valid_scores = [s for s in r.problem_scores if s is not None]
        calculated = sum(valid_scores)
        if calculated != r.total:
            mismatches.append(
                {
                    "name": r.name,
                    "country": r.country,
                    "calculated": calculated,
                    "reported": r.total,
                }
            )
    return mismatches


def save_json(data: EMOYearResults, filepath: str) -> None:
    """Save results to JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(data.model_dump_json(indent=2))


def parse_raw(year: int, raw_file: Path) -> EMOYearResults:
    """Parse a raw data file for a given year."""
    try:
        parser = get_parser(year)
    except ValueError as e:
        raise ParseError(str(e)) from e

    try:
        results = parser.parse(raw_file)
    except Exception as e:
        raise ParseError(f"Failed to parse data for year {year}: {e}") from e

    if not results:
        raise ParseError(f"No results found for year {year}.")

    mismatches = validate_totals(results)

    return EMOYearResults(
        year=year,
        source_url=get_source_url(year),
        source_type=get_source_type(year),
        total_contestants=len(results),
        results=results,
        validation=ValidationResult(
            all_totals_match=len(mismatches) == 0,
            mismatches=mismatches,
        ),
    )
