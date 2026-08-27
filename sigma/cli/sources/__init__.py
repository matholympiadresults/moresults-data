"""Source adapters for different olympiad data sources."""

from pathlib import Path

from .apmo import APMOAdapter
from .balticway import BalticWayAdapter
from .bmo import BMOAdapter
from .egmo import EGMOAdapter
from .emo import EMOAdapter
from .imo import IMOAdapter
from .jbmo import JBMOAdapter
from .memo import MEMOAdapter
from .pamo import PAMOAdapter
from .rmm import RMMAdapter

SOURCES = {
    "apmo": APMOAdapter(),
    "balticway": BalticWayAdapter(),
    "bmo": BMOAdapter(),
    "egmo": EGMOAdapter(),
    "emo": EMOAdapter(),
    "imo": IMOAdapter(),
    "jbmo": JBMOAdapter(),
    "memo": MEMOAdapter(),
    "pamo": PAMOAdapter(),
    "rmm": RMMAdapter(),
}

# Fixed competition ordering for full ingestion. ``ingest_all_sources`` iterates
# YEAR-first, then walks competitions in this exact order within each year. This
# makes the person-matching sequence deterministic and stable over time: adding a
# later year never touches earlier years, and appending a new competition to the
# end never changes how the competitions before it match within a year.
# The "memo" adapter ingests individual results then team results, covering both
# MEMO and MEMO Team.
INGEST_ORDER = (
    "rmm",
    "apmo",
    "egmo",
    "emo",
    "bmo",
    "jbmo",
    "pamo",
    "imo",
    "memo",
    "balticway",
)


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

    Ingestion is ordered YEAR-first, then by competition in ``INGEST_ORDER``
    within each year. This fixed traversal keeps person matching deterministic
    and stable as new years and competitions are added over time.

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

    adapters = [SOURCES[name] for name in INGEST_ORDER]

    # Every year that any competition has parsed data for.
    all_years = sorted(
        {year for adapter in adapters for year in adapter.find_available_parsed_years(data_dir)}
    )

    # Ingest year-by-year, walking competitions in INGEST_ORDER within each year.
    # Each adapter.ingest loads the existing DB, adds the requested year, and
    # saves, so these per-year calls accumulate into one database.
    for year in all_years:
        for adapter in adapters:
            if year in adapter.find_available_parsed_years(data_dir):
                adapter.ingest(data_dir, output, [year])

    if verbose:
        print()
        print(f"Database saved to {output}")

    return output
