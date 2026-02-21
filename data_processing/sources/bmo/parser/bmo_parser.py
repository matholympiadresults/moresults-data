"""BMO raw data parser.

Parses raw HTML and PDF files into structured BMOYearResults.
"""

from pathlib import Path

from ..downloader import get_source_type, get_source_url
from .models import BMOYearResults, ContestantResult, ValidationResult
from .parsers.base import BaseParser
from .parsers.html_2018 import Parser2018
from .parsers.html_2023 import Parser2023
from .parsers.html_2024 import Parser2024
from .parsers.pdf_parser import PDFParser

# Years that use PDF sources (imported from downloader for parser routing)
_PDF_YEARS = {2020, 2021, 2022, 2025}


class ParseError(Exception):
    """Raised when parsing fails unexpectedly."""

    pass


def get_parser(year: int) -> BaseParser:
    """Get the appropriate parser for a given year.

    Args:
        year: The competition year

    Returns:
        A parser instance for the specified year

    Raises:
        ValueError: If no parser is available for the year
    """
    if year in _PDF_YEARS:
        return PDFParser(year)

    parser_map = {
        2018: Parser2018,
        2023: Parser2023,
        2024: Parser2024,
    }

    if year not in parser_map:
        from ..downloader import AVAILABLE_YEARS

        raise ValueError(f"No parser available for year {year}. Available years: {AVAILABLE_YEARS}")

    return parser_map[year](year)


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


def save_json(data: BMOYearResults, filepath: str) -> None:
    """Save results to JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(data.model_dump_json(indent=2))


def parse_raw(year: int, raw_file: Path) -> BMOYearResults:
    """Parse a raw data file for a given year.

    Args:
        year: The competition year
        raw_file: Path to the raw data file

    Returns:
        BMOYearResults containing all contestant data

    Raises:
        ParseError: If parsing fails
    """
    try:
        parser = get_parser(year)
    except ValueError as e:
        raise ParseError(str(e)) from e

    try:
        results = parser.parse(raw_file)
    except Exception as e:
        raise ParseError(f"Failed to parse data for year {year}: {e}") from e

    if not results:
        raise ParseError(f"No results found for year {year}. The year may not have data yet.")

    mismatches = validate_totals(results)

    return BMOYearResults(
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
