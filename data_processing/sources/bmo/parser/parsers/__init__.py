"""Year-specific parsers for BalcanMO data sources."""

from .base import BaseParser
from .html_2018 import Parser2018
from .html_2023 import Parser2023
from .html_2024 import Parser2024
from .pdf_parser import PDFParser

__all__ = [
    "BaseParser",
    "Parser2024",
    "Parser2023",
    "Parser2018",
    "PDFParser",
]
