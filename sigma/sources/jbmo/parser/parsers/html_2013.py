"""Parser for JBMO 2013 results from HTML.

Source: https://jbmo2013.tubitak.gov.tr/Results.html
HTML table inside <div id="stil2">.
Columns: Rank, Code, Name, Surname, P1, P2, P3, P4, ∑, Medal.

Names are split across two columns: given name and surname (UPPERCASE).
Country codes are embedded in the Code column without spaces, e.g.
"ROU1" -> "ROU", "TURB4" -> "TUR(B)".
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup

from ..models import ContestantResult
from .base import BaseParser

# Matches letter prefix and trailing digit(s) in codes like "ROU1", "TURB4".
_CODE_RE = re.compile(r"^([A-Z]+?)(\d+)$")


def _extract_country_code(code_text: str) -> str:
    """Extract country code from a contestant code like 'ROU1' or 'TURB4'.

    All standard codes are 3 letters. A 4-letter prefix ending with 'B'
    indicates a B-team, e.g. "TURB" -> "TUR(B)".
    """
    code_text = code_text.strip()
    m = _CODE_RE.match(code_text)
    if not m:
        return code_text
    letters = m.group(1)
    # 4+ letter prefix ending with B → B-team
    if len(letters) >= 4 and letters.endswith("B"):
        return f"{letters[:-1]}(B)"
    return letters


def _titlecase_surname(surname: str) -> str:
    """Convert an UPPERCASE surname to title case.

    Handles hyphenated names: "PLOSCARU" -> "Ploscaru",
    "LAGUMDŽIJA" -> "Lagumdžija".
    """
    return "-".join(part.capitalize() for part in surname.split("-"))


def _parse_score(text: str) -> int | None:
    """Parse a problem score, returning None on failure."""
    try:
        return int(text.strip())
    except (ValueError, TypeError):
        return None


class Parser2013(BaseParser):
    """Parser for JBMO 2013 (HTML table from jbmo2013.tubitak.gov.tr)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        """Parse the HTML table and extract contestant results."""
        html = raw_file.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        # Table is inside <div id="stil2">
        container = soup.find("div", id="stil2")
        if not container:
            raise ValueError(f"Could not find div#stil2 for JBMO {self.year}")

        table = container.find("table")
        if not table:
            raise ValueError(f"Could not find table for JBMO {self.year}")

        results: list[ContestantResult] = []

        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 10:
                continue

            # Column 0: Rank (we compute our own)
            # Column 1: Code (e.g. "ROU1", "TURB4")
            code_text = cells[1].get_text(strip=True)
            if not _CODE_RE.match(code_text):
                continue  # Skip header row
            country = _extract_country_code(code_text)

            # Column 2: Name (given name)
            given_name_raw = cells[2].get_text(strip=True)
            # Column 3: Surname (UPPERCASE)
            surname_raw = cells[3].get_text(strip=True)

            if not given_name_raw and not surname_raw:
                continue

            family_name = _titlecase_surname(surname_raw)
            given_name = given_name_raw
            full_name = f"{given_name} {family_name}"

            # Columns 4-7: P1-P4
            problem_scores = [_parse_score(cells[4 + i].get_text(strip=True)) for i in range(4)]

            # Column 8: Total
            total = _parse_score(cells[8].get_text(strip=True))
            if total is None:
                total = sum(s for s in problem_scores if s is not None)

            # Column 9: Medal
            award_text = cells[9].get_text(strip=True)
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
