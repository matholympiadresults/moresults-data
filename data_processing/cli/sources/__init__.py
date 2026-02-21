"""Source adapters for different olympiad data sources."""

from .apmo import APMOAdapter
from .bmo import BMOAdapter
from .egmo import EGMOAdapter
from .imo import IMOAdapter
from .memo import MEMOAdapter
from .pamo import PAMOAdapter
from .rmm import RMMAdapter

SOURCES = {
    "apmo": APMOAdapter(),
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
