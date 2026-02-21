"""Regression tests for ingestors.

Ensures that re-ingesting parsed data produces identical database output.
This catches unintended ingester changes that would alter output.
"""

import json
from pathlib import Path

import pytest

from data_processing.cli.sources import SOURCES


def get_data_dir() -> Path:
    """Get the data directory path."""
    return Path(__file__).parent.parent / "data"


def get_database_path() -> Path:
    """Get the database file path."""
    return get_data_dir() / "olympiad_data.json"


def normalize_db(data: dict) -> dict:
    """Remove timestamp field for stable comparison."""
    return {k: v for k, v in data.items() if k != "last_updated"}


@pytest.fixture(scope="module")
def data_dir() -> Path:
    """Fixture providing the data directory."""
    return get_data_dir()


def test_ingest_regression(data_dir: Path, tmp_path: Path):
    """Test that re-ingesting produces identical database output."""
    expected_path = get_database_path()
    actual_path = tmp_path / "olympiad_data.json"

    # Re-ingest all sources
    for adapter in SOURCES.values():
        parsed_years = adapter.find_available_parsed_years(data_dir)
        if parsed_years:
            adapter.ingest(data_dir, actual_path, parsed_years)

    with open(expected_path) as f:
        expected_data = json.load(f)
    with open(actual_path) as f:
        actual_data = json.load(f)

    assert normalize_db(expected_data) == normalize_db(actual_data)
