"""Year-specific parsers for BalcanMO data sources."""

from .base import BaseParser
from .html_2018 import Parser2018
from .html_2023 import Parser2023
from .html_2024 import Parser2024
from .pdf_2020 import Parser2020
from .pdf_2021 import Parser2021
from .pdf_2022 import Parser2022
from .pdf_2025 import Parser2025

__all__ = [
    "BaseParser",
    "Parser2018",
    "Parser2020",
    "Parser2021",
    "Parser2022",
    "Parser2023",
    "Parser2024",
    "Parser2025",
]
