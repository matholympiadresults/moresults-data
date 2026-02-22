"""EGMO data ingester."""

from .egmo_ingester import ingest_egmo_data, ingest_results, load_results_from_file

__all__ = [
    "ingest_egmo_data",
    "ingest_results",
    "load_results_from_file",
]
