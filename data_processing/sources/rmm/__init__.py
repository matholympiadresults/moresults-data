"""RMM (Romanian Masters of Mathematics) data processing.

Three-stage pipeline:
- download: Downloads raw HTML from rmms.lbi.ro
- parse: Parses HTML into structured JSON format
- ingest: Ingests parsed data into the normalized database
"""

from .downloader import AVAILABLE_YEARS, download_year, fetch_page
from .ingester import ingest_rmm_data
from .parser import ParseError, parse_html, parse_year

__all__ = [
    "download_year",
    "fetch_page",
    "AVAILABLE_YEARS",
    "parse_html",
    "parse_year",
    "ParseError",
    "ingest_rmm_data",
]
