"""Year-specific parsers for JBMO data sources."""

from .base import BaseParser
from .html_2012 import Parser2012
from .html_2013 import Parser2013
from .html_2014 import Parser2014
from .html_2015 import Parser2015
from .html_2016 import Parser2016
from .html_2021 import Parser2021
from .html_2024 import Parser2024
from .html_2025 import Parser2025
from .pdf_2010 import Parser2010
from .pdf_2020 import Parser2020
from .pdf_2022 import Parser2022
from .pdf_2023 import Parser2023

__all__ = [
    "BaseParser",
    "Parser2010",
    "Parser2012",
    "Parser2013",
    "Parser2014",
    "Parser2015",
    "Parser2016",
    "Parser2020",
    "Parser2021",
    "Parser2022",
    "Parser2023",
    "Parser2024",
    "Parser2025",
]
