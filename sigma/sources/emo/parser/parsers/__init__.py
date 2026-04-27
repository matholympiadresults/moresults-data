"""Year-specific parsers for EMO data sources."""

from .base import BaseParser
from .csv_2026 import Parser2026

__all__ = [
    "BaseParser",
    "Parser2026",
]
