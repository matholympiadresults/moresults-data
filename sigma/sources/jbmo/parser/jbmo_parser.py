"""JBMO raw data parser.

Parses raw HTML and PDF files into structured JBMOYearResults.
"""

from pathlib import Path

from ..downloader import get_source_type, get_source_url
from .models import ContestantResult, JBMOYearResults, ValidationResult
from .parsers.base import BaseParser
from .parsers.html_2012 import Parser2012
from .parsers.html_2013 import Parser2013
from .parsers.html_2014 import Parser2014
from .parsers.html_2015 import Parser2015
from .parsers.html_2016 import Parser2016
from .parsers.html_2021 import Parser2021
from .parsers.html_2024 import Parser2024
from .parsers.pdf_2010 import Parser2010
from .parsers.pdf_2023 import Parser2023


class ParseError(Exception):
    """Raised when parsing fails unexpectedly."""

    pass


_PARSER_MAP: dict[int, type[BaseParser]] = {
    2010: Parser2010,
    2012: Parser2012,
    2013: Parser2013,
    2014: Parser2014,
    2015: Parser2015,
    2016: Parser2016,
    2021: Parser2021,
    2023: Parser2023,
    2024: Parser2024,
}


def get_parser(year: int) -> BaseParser:
    """Get the appropriate parser for a given year.

    Args:
        year: The competition year

    Returns:
        A parser instance for the specified year

    Raises:
        ValueError: If no parser is available for the year
    """
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


def save_json(data: JBMOYearResults, filepath: str) -> None:
    """Save results to JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(data.model_dump_json(indent=2))


def parse_raw(year: int, raw_file: Path) -> JBMOYearResults:
    """Parse a raw data file for a given year.

    Args:
        year: The competition year
        raw_file: Path to the raw data file

    Returns:
        JBMOYearResults containing all contestant data

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

    return JBMOYearResults(
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
