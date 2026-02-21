#!/usr/bin/env python3
"""
BalcanMO Results Scraper

Scrapes Balkan Mathematical Olympiad individual results from various sources.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from .models import BMOYearResults, ContestantResult, ValidationResult
from .parsers.base import BaseParser
from .parsers.html_2018 import Parser2018
from .parsers.html_2023 import Parser2023
from .parsers.html_2024 import Parser2024
from .parsers.pdf_parser import PDFParser

# Available years with their parser types
# Note: 2015 is excluded because the source only has contestant codes, not names
AVAILABLE_YEARS = [2018, 2020, 2021, 2022, 2023, 2024, 2025]

# Years that use PDF sources
PDF_YEARS = {2020, 2021, 2022, 2025}


class ScraperError(Exception):
    """Raised when scraping fails unexpectedly."""

    pass


def get_parser(year: int, raw_data_dir: Path) -> BaseParser:
    """Get the appropriate parser for a given year.

    Args:
        year: The competition year
        raw_data_dir: Directory to store raw data files

    Returns:
        A parser instance for the specified year

    Raises:
        ValueError: If no parser is available for the year
    """
    if year in PDF_YEARS:
        return PDFParser(year, raw_data_dir)

    parser_map = {
        2018: Parser2018,
        2023: Parser2023,
        2024: Parser2024,
    }

    if year not in parser_map:
        raise ValueError(f"No parser available for year {year}. Available years: {AVAILABLE_YEARS}")

    return parser_map[year](year, raw_data_dir)


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
        json.dump(data.model_dump(), f, indent=2, ensure_ascii=False)


def scrape_year(year: int, raw_data_dir: Path, force: bool = False) -> BMOYearResults:
    """Scrape results for a single year and return structured data.

    Args:
        year: The competition year
        raw_data_dir: Directory to store raw data files
        force: If True, re-download even if file exists

    Returns:
        BMOYearResults containing all contestant data

    Raises:
        ScraperError: If scraping fails
    """
    try:
        parser = get_parser(year, raw_data_dir)
    except ValueError as e:
        raise ScraperError(str(e)) from e

    try:
        raw_file = parser.download_raw(force=force)
    except Exception as e:
        raise ScraperError(f"Failed to download data for year {year}: {e}") from e

    try:
        results = parser.parse(raw_file)
    except Exception as e:
        raise ScraperError(f"Failed to parse data for year {year}: {e}") from e

    if not results:
        raise ScraperError(f"No results found for year {year}. The year may not have data yet.")

    mismatches = validate_totals(results)

    return BMOYearResults(
        year=year,
        scraped_at=datetime.now(UTC).isoformat(),
        source_url=parser.source_url,
        source_type=parser.source_type,
        total_contestants=len(results),
        results=results,
        validation=ValidationResult(
            all_totals_match=len(mismatches) == 0,
            mismatches=mismatches,
        ),
    )


def scrape_all_years(raw_data_dir: Path, force: bool = False) -> list[BMOYearResults]:
    """Scrape results for all available years.

    Args:
        raw_data_dir: Directory to store raw data files
        force: If True, re-download even if files exist

    Returns:
        List of BMOYearResults for all successfully scraped years
    """
    all_results = []
    for year in AVAILABLE_YEARS:
        try:
            result = scrape_year(year, raw_data_dir, force=force)
            all_results.append(result)
            print(f"Scraped BMO {year}: {result.total_contestants} contestants")
        except ScraperError as e:
            print(f"Failed to scrape BMO {year}: {e}")
    return all_results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 2:
        year = int(sys.argv[1])
        raw_dir = Path(sys.argv[2])
        result = scrape_year(year, raw_dir)
        print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    else:
        print(
            "Usage: python -m data_processing.sources.bmo.scraper.bmo_scraper <year> <raw_data_dir>"
        )
