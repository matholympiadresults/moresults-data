"""Parser for JBMO 2016 results from HTML.

Source: https://jbmo.ssmr.ro/results
HTML table with columns: Pos., Name, Country, P1, P2, P3, P4, Total, Medal.

Names are in Western order ("Given Surname"), e.g. "Ozan Kaymak".
Country codes are space-separated, e.g. "TUR 1", "ROU B 2".
B-team codes like "ROU B" are normalised to "ROU(B)".

The page contains two tables: individual results (9 columns per row)
and team standings (5 columns per row).  Only the individual table is parsed.
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup

from ..models import ContestantResult
from .base import BaseParser

# Matches a country code followed by a contestant number.
# Handles both "TUR 1" and "ROU B 2" formats.
_CODE_RE = re.compile(r"^(.+?)\s+\d+$")


def _extract_country_code(country_text: str) -> str:
    """Extract country code from a contestant label like 'TUR 1' or 'ROU B 2'.

    "ROU B 2" -> "ROU B" -> "ROU(B)"
    "TUR 1"   -> "TUR"
    """
    m = _CODE_RE.match(country_text)
    if not m:
        return country_text
    raw_code = m.group(1)
    # Convert "ROU B" style B-team codes to "ROU(B)"
    if raw_code.endswith(" B"):
        return f"{raw_code[:-2]}(B)"
    return raw_code


def _split_name(full_name: str) -> tuple[str, str]:
    """Split a Western-order name into (given_name, family_name).

    The last word is treated as the family name and all preceding words
    as the given name.  For example:
        "Ozan Kaymak"              -> ("Ozan", "Kaymak")
        "George Adrian Picu"       -> ("George Adrian", "Picu")
        "Andres Rico Iii M. Gonzales" -> ("Andres Rico Iii M.", "Gonzales")
    """
    parts = full_name.split()
    if len(parts) < 2:
        return "", full_name
    return " ".join(parts[:-1]), parts[-1]


def _parse_score(text: str) -> int | None:
    """Parse a problem score, returning None on failure."""
    try:
        return int(text.strip())
    except (ValueError, TypeError):
        return None


class Parser2016(BaseParser):
    """Parser for JBMO 2016 (HTML table from jbmo.ssmr.ro)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        """Parse the HTML table and extract contestant results."""
        html = raw_file.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        results: list[ContestantResult] = []

        # Iterate all tables to find the individual results table
        # (the one whose header row contains "Medal").
        for table in soup.find_all("table"):
            header_row = table.find("tr")
            if not header_row:
                continue
            header_text = header_row.get_text()
            if "Medal" not in header_text:
                continue

            # Found the individual results table
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) != 9:
                    continue

                # Column 0: Position (e.g. "1.")
                pos_text = cells[0].get_text(strip=True)
                if not pos_text or not pos_text.rstrip(".").isdigit():
                    continue

                # Column 1: Name
                full_name = cells[1].get_text(strip=True)
                if not full_name:
                    continue

                # Column 2: Country code (e.g. "TUR 1", "ROU B 2")
                country_text = cells[2].get_text(strip=True)
                country = _extract_country_code(country_text)

                # Columns 3-6: P1-P4
                problem_scores = [_parse_score(cells[3 + i].get_text(strip=True)) for i in range(4)]

                # Column 7: Total
                total = _parse_score(cells[7].get_text(strip=True))
                if total is None:
                    total = sum(s for s in problem_scores if s is not None)

                # Column 8: Medal (text inside <font> tag)
                award_text = cells[8].get_text(strip=True)
                award = self.normalize_award(award_text) if award_text else None

                given_name, family_name = _split_name(full_name)

                results.append(
                    ContestantResult(
                        name=full_name,
                        country=country,
                        problem_scores=problem_scores,
                        total=total,
                        rank=None,
                        award=award,
                        given_name=given_name or None,
                        family_name=family_name or None,
                    )
                )

            break  # Only parse the first table with "Medal" header

        self.compute_ranks(results)
        return results
