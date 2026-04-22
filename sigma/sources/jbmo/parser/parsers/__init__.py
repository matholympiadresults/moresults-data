"""Year-specific parsers for JBMO data sources."""

from .base import BaseParser
from .html_2021 import Parser2021
from .html_2024 import Parser2024
from .html_2025 import Parser2025
from .pdf_2020 import Parser2020
from .pdf_2022 import Parser2022
from .pdf_2023 import Parser2023

__all__ = [
    "BaseParser",
    "Parser2020",
    "Parser2021",
    "Parser2022",
    "Parser2023",
    "Parser2024",
    "Parser2025",
]
