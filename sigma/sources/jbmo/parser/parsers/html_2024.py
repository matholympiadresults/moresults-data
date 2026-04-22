"""Parser for JBMO 2024 results from HTML.

Source: https://jbmo2024.tubitak.gov.tr/results
HTML table with id="contestansResultsTable".
Columns: #, Contestant, Name-Surname, P1, P2, P3, P4, Total, Medal.

Names are in Western order ("Given Surname"), e.g. "Nina Šušić".
Country codes are extracted from the Contestant column, e.g. "SRB 1" -> "SRB",
"TUR(B) 2" -> "TUR(B)".
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup

from ..models import ContestantResult
from .base import BaseParser

# Matches the country-code prefix in the Contestant column.
# Everything before the last whitespace + contestant number.
_CODE_RE = re.compile(r"^(.+?)\s+\d+$")


def _extract_country_code(contestant_text: str) -> str:
    """Extract country code from a contestant label like 'SRB 1' or 'TUR(B) 2'."""
    m = _CODE_RE.match(contestant_text)
    if m:
        return m.group(1)
    return contestant_text


def _split_name(full_name: str) -> tuple[str, str]:
    """Split a Western-order name into (given_name, family_name).

    The last word is treated as the family name and all preceding words
    as the given name.  For example:
        "Nina Šušić"          -> ("Nina", "Šušić")
        "Umut Kağan Yazgan"   -> ("Umut Kağan", "Yazgan")
    """
    parts = full_name.split()
    if len(parts) < 2:
        return "", full_name
    given_name = " ".join(parts[:-1])
    family_name = parts[-1]
    return given_name, family_name


def _parse_score(text: str) -> int | None:
    """Parse a problem score, returning None on failure."""
    try:
        return int(text)
    except (ValueError, TypeError):
        return None


class Parser2024(BaseParser):
    """Parser for JBMO 2024 (HTML table from jbmo2024.tubitak.gov.tr)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        """Parse the HTML table and extract contestant results."""
        html = raw_file.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        table = soup.find("table", id="contestansResultsTable")
        if not table:
            raise ValueError(f"Could not find contestansResultsTable for JBMO {self.year}")

        results: list[ContestantResult] = []

        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 9:
                continue

            # Column 1: Contestant code (e.g. "SRB 1", "TUR(B) 2")
            contestant_text = cells[1].get_text(strip=True)
            country = _extract_country_code(contestant_text)

            # Column 2: Name-Surname in Western order
            full_name = cells[2].get_text(strip=True)
            if not full_name:
                continue

            given_name, family_name = _split_name(full_name)

            # Columns 3-6: P1-P4
            problem_scores = [_parse_score(cells[3 + i].get_text(strip=True)) for i in range(4)]

            # Column 7: Total
            total = _parse_score(cells[7].get_text(strip=True))
            if total is None:
                total = sum(s for s in problem_scores if s is not None)

            # Column 8: Medal
            award_text = cells[8].get_text(strip=True)
            award = self.normalize_award(award_text) if award_text else None

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

        self.compute_ranks(results)
        return results
