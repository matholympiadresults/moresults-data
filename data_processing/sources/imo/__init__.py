"""
IMO Data Source

Pipeline: download -> parse -> ingest
"""

from data_processing.sources.imo.downloader import (
    DownloadError,
    download_year,
    download_years,
)
from data_processing.sources.imo.ingester import (
    IngestError,
    ingest_year_results,
    ingest_years,
    load_year_results_from_file,
)
from data_processing.sources.imo.parser import (
    ContestantResult,
    IMOYearResults,
    ParseError,
    ProblemScores,
    parse_html,
    parse_year,
    parse_years,
)

__all__ = [
    # Download
    "DownloadError",
    "download_year",
    "download_years",
    # Parse
    "ParseError",
    "ProblemScores",
    "ContestantResult",
    "IMOYearResults",
    "parse_html",
    "parse_year",
    "parse_years",
    # Ingest
    "IngestError",
    "ingest_year_results",
    "ingest_years",
    "load_year_results_from_file",
]
