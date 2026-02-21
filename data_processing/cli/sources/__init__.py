"""Source adapters for different olympiad data sources."""

from pathlib import Path

from .apmo import APMOAdapter
from .balticway import BalticWayAdapter
from .bmo import BMOAdapter
from .egmo import EGMOAdapter
from .imo import IMOAdapter
from .memo import MEMOAdapter
from .pamo import PAMOAdapter
from .rmm import RMMAdapter

SOURCES = {
    "apmo": APMOAdapter(),
    "balticway": BalticWayAdapter(),
    "bmo": BMOAdapter(),
    "egmo": EGMOAdapter(),
    "imo": IMOAdapter(),
    "memo": MEMOAdapter(),
    "pamo": PAMOAdapter(),
    "rmm": RMMAdapter(),
}


def get_source(name: str):
    """Get a source adapter by name."""
    if name not in SOURCES:
        raise ValueError(f"Unknown source: {name}. Available: {list(SOURCES.keys())}")
    return SOURCES[name]


def get_all_sources():
    """Get all source adapters."""
    return list(SOURCES.values())


def ingest_all_sources(data_dir: Path, output: Path, verbose: bool = True) -> Path:
    """
    Ingest all sources from scratch into the database.

    Deletes any existing database file and re-ingests all parsed data.

    Args:
        data_dir: Base data directory containing source subdirectories
        output: Path to output database file
        verbose: If True, print progress messages

    Returns:
        Path to the output database file
    """
    # Delete existing database to start fresh
    if output.exists():
        output.unlink()

    for adapter in get_all_sources():
        parsed_base = adapter.get_parsed_base_dir(data_dir)

        if not parsed_base.exists():
            if verbose:
                print(f"\nSkipping {adapter.display_name}: {parsed_base} not found")
            continue

        if verbose:
            print(f"\n{'=' * 50}")
            print(f"Ingesting {adapter.display_name}")
            print(f"{'=' * 50}")
            print(f"Parsed directory: {parsed_base}/<year>/")
            print()

        adapter.ingest(data_dir, output, None)

    if verbose:
        print()
        print(f"Database saved to {output}")

    return output
