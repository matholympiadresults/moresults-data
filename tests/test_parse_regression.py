"""Regression tests for parsers.

Ensures that re-parsing raw data produces identical results to what's committed.
This catches unintended parser changes that would alter output.
"""

import json
import os
from pathlib import Path

import pytest

from data_processing.cli.sources import SOURCES

# Fields that are expected to change between parse runs
TIMESTAMP_FIELDS = {"parsed_at", "scraped_at"}


def normalize_json(data: dict | list, path: str = "") -> dict | list:
    """Remove timestamp fields that are expected to differ between runs."""
    if isinstance(data, dict):
        return {
            k: normalize_json(v, f"{path}.{k}")
            for k, v in data.items()
            if k not in TIMESTAMP_FIELDS
        }
    elif isinstance(data, list):
        return [normalize_json(item, f"{path}[{i}]") for i, item in enumerate(data)]
    return data


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
    mismatches = []
    for year in years_to_test:
        expected_dir = adapter.get_parsed_dir(data_dir, year)
        actual_dir = adapter.get_parsed_dir(tmp_data_dir, year)

        if not actual_dir.exists():
            mismatches.append(f"{source_name}/{year}: re-parsed directory not created")
            continue

        expected_files = find_json_files(expected_dir)
        actual_files = find_json_files(actual_dir)

        # Check same files exist
        expected_names = {f.name for f in expected_files}
        actual_names = {f.name for f in actual_files}

        if expected_names != actual_names:
            mismatches.append(
                f"{source_name}/{year}: file mismatch - "
                f"expected {expected_names}, got {actual_names}"
            )
            continue

        # Compare each file
        for expected_file in expected_files:
            actual_file = actual_dir / expected_file.name

            with open(expected_file) as f:
                expected_data = json.load(f)
            with open(actual_file) as f:
                actual_data = json.load(f)

            expected_normalized = normalize_json(expected_data)
            actual_normalized = normalize_json(actual_data)

            if expected_normalized != actual_normalized:
                # Find specific differences for better error messages
                diff = find_diff(expected_normalized, actual_normalized)
                mismatches.append(
                    f"{source_name}/{year}/{expected_file.name}: content mismatch\n{diff}"
                )

    if mismatches:
        pytest.fail("\n".join(mismatches))


def find_diff(expected, actual, path: str = "root") -> str:
    """Find and describe differences between two data structures."""
    diffs = []

    if type(expected) != type(actual):
        return f"  {path}: type mismatch - expected {type(expected).__name__}, got {type(actual).__name__}"

    if isinstance(expected, dict):
        all_keys = set(expected.keys()) | set(actual.keys())
        for key in sorted(all_keys):
            if key not in expected:
                diffs.append(f"  {path}.{key}: unexpected key in actual")
            elif key not in actual:
                diffs.append(f"  {path}.{key}: missing key in actual")
            elif expected[key] != actual[key]:
                sub_diff = find_diff(expected[key], actual[key], f"{path}.{key}")
                diffs.append(sub_diff)
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            diffs.append(
                f"  {path}: length mismatch - expected {len(expected)}, got {len(actual)}"
            )
        else:
            for i, (e, a) in enumerate(zip(expected, actual)):
                if e != a:
                    sub_diff = find_diff(e, a, f"{path}[{i}]")
                    diffs.append(sub_diff)
    else:
        if expected != actual:
            exp_str = str(expected)[:50]
            act_str = str(actual)[:50]
            diffs.append(f"  {path}: expected {exp_str!r}, got {act_str!r}")

    return "\n".join(diffs) if diffs else ""
