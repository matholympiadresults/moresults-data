"""APMO (Asian Pacific Mathematical Olympiad) data processing."""

from data_processing.sources.apmo.apmo_downloader import (
    APMOScoreboard,
    Award,
    Contestant,
    download_apmo_year,
    download_raw_year,
    parse_raw_year,
    save_to_json,
)
from data_processing.sources.apmo.ingester import ingest_apmo_data

__all__ = [
    "APMOScoreboard",
    "Contestant",
    "Award",
    # 3-stage pipeline
    "download_raw_year",
    "parse_raw_year",
    "ingest_apmo_data",
    # Legacy
    "download_apmo_year",
    "save_to_json",
]
