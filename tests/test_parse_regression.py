"""Regression tests for parsers.

Ensures that re-parsing raw data produces identical results to what's committed.
This catches unintended parser changes that would alter output.
"""

import json
import os
from pathlib import Path

import pytest

from data_processing.cli.sources import SOURCES


def find_json_files(directory: Path) -> list[Path]:
    """Find all JSON files in a directory tree."""
    return sorted(directory.rglob("*.json"))


def get_data_dir() -> Path:
    """Get the data directory path."""
    return Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def data_dir() -> Path:
    """Fixture providing the data directory."""
    return get_data_dir()


@pytest.mark.parametrize("source_name", list(SOURCES.keys()))
def test_parse_regression(source_name: str, data_dir: Path, tmp_path_factory):
    """Test that re-parsing produces identical output.

    For each source:
    1. Find all years with existing parsed data
    2. Re-parse raw data to a temp directory
    3. Compare each JSON file (ignoring timestamps)
    """
    adapter = SOURCES[source_name]

    parsed_years = adapter.find_available_parsed_years(data_dir)
    raw_years = adapter.find_available_raw_years(data_dir)
    years_to_test = [y for y in parsed_years if y in raw_years]

    # Create temp directory structure
    tmp_base = tmp_path_factory.mktemp(f"regression_{source_name}")
    tmp_data_dir = tmp_base / "data"
    tmp_data_dir.mkdir()

    # Symlink raw data to temp directory
    raw_base = adapter.get_raw_base_dir(data_dir)
    tmp_raw_base = tmp_data_dir / source_name / "raw"
    tmp_raw_base.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(raw_base, tmp_raw_base)

    # Parse to temp directory
    adapter.parse_raw(tmp_data_dir, years=years_to_test, force=True)

    # Compare each parsed year
    for year in years_to_test:
        expected_dir = adapter.get_parsed_dir(data_dir, year)
        actual_dir = adapter.get_parsed_dir(tmp_data_dir, year)

        assert actual_dir.exists(), f"{source_name}/{year}: re-parsed directory not created"

        expected_files = find_json_files(expected_dir)
        actual_files = find_json_files(actual_dir)

        expected_names = {f.name for f in expected_files}
        actual_names = {f.name for f in actual_files}
        assert expected_names == actual_names, f"{source_name}/{year}: file mismatch"

        for expected_file in expected_files:
            actual_file = actual_dir / expected_file.name

            with open(expected_file) as f:
                expected_data = json.load(f)
            with open(actual_file) as f:
                actual_data = json.load(f)

            assert expected_data == actual_data, f"{source_name}/{year}/{expected_file.name}"
