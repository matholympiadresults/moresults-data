"""APMO ingester module."""

from sigma.sources.apmo.ingester.apmo_ingester import (
    ingest_apmo_data,
    ingest_scoreboard,
)

__all__ = ["ingest_apmo_data", "ingest_scoreboard"]
