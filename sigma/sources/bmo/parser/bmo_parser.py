"""BMO raw data parser.

Parses raw HTML and PDF files into structured BMOYearResults.
"""

from pathlib import Path

from ..downloader import get_source_type, get_source_url
from .models import BMOYearResults, ContestantResult, ValidationResult
from .parsers.base import BaseParser
from .parsers.html_2011 import Parser2011
from .parsers.html_2015 import Parser2015
from .parsers.html_2017 import Parser2017
from .parsers.html_2018 import Parser2018
from .parsers.html_2019 import Parser2019
from .parsers.html_2023 import Parser2023
from .parsers.html_2024 import Parser2024
from .parsers.pdf_2008 import Parser2008
from .parsers.pdf_2009 import Parser2009
from .parsers.pdf_2010 import Parser2010
from .parsers.pdf_2014 import Parser2014
from .parsers.pdf_2016 import Parser2016
from .parsers.pdf_2020 import Parser2020
from .parsers.pdf_2021 import Parser2021
from .parsers.pdf_2022 import Parser2022
from .parsers.pdf_2025 import Parser2025
from .parsers.xls_2005 import Parser2005


class ParseError(Exception):
    """Raised when parsing fails unexpectedly."""

    pass


_PARSER_MAP: dict[int, type[BaseParser]] = {
    2005: Parser2005,
    2008: Parser2008,
    2009: Parser2009,
    2010: Parser2010,
    2011: Parser2011,
    2014: Parser2014,
    2015: Parser2015,
    2016: Parser2016,
    2017: Parser2017,
    2018: Parser2018,
    2019: Parser2019,
    2020: Parser2020,
    2021: Parser2021,
    2022: Parser2022,
    2023: Parser2023,
    2024: Parser2024,
    2025: Parser2025,
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
