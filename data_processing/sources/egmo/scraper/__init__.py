"""EGMO data scraper.

Three-stage pipeline:
1. download - Downloads raw HTML and CSV files from egmo.org
2. parse - Parses raw files into structured JSON
3. ingest - Ingests parsed JSON into the normalized database (via ingester module)
"""

from .egmo_scraper import (
    FIRST_EGMO_YEAR,
    ScraperError,
    download_raw,
    edition_to_year,
    get_available_years,
    get_latest_edition,
    parse_raw,
    save_json,
    scrape_year,
    year_to_edition,
)
from .models import ContestantResult, EGMOYearResults, ValidationResult

__all__ = [
    # Constants
    "FIRST_EGMO_YEAR",
    # Errors
    "ScraperError",
    # Functions
    "download_raw",
    "parse_raw",
    "save_json",
    "scrape_year",
    "year_to_edition",
    "edition_to_year",
    "get_available_years",
    "get_latest_edition",
    # Models
    "ContestantResult",
    "EGMOYearResults",
    "ValidationResult",
]
