"""Parser for JBMO 2012 results from HTML.

Source: http://www.hms.gr/16jbmo2012/medals.htm (via Wayback Machine)
HTML table with 89 contestants.
Columns: ID (rank), Student (code), Prob.1, Prob.2, Prob.3, Prob.4, Total,
         Student Name, Medal.

Medal values use non-standard labels: "FIRST" (Gold), "SECOND" (Silver),
"THIRD" (Bronze).  Empty / whitespace-only means no medal.

Country codes are embedded in the Student column without spaces, e.g.
"ROU3" -> "ROU", "TUR5" -> "TUR".

Names are in a single column with mixed formats:
- Turkish names use comma: "Given, Surname" (e.g. "Emre, Girgin")
- Multi-space separated: "Surname    Given" (e.g. "Ploscaru    Ioan-Laurentiu")
- Single-space names: last word treated as family name
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup

from ..models import ContestantResult
from .base import BaseParser

# Matches letter prefix and trailing digit(s) in codes like "ROU3", "TUR5".
_CODE_RE = re.compile(r"^([A-Z]+?)(\d+)$")

# Non-standard medal mapping for JBMO 2012.
_MEDAL_MAP = {
    "first": "Gold",
    "second": "Silver",
    "third": "Bronze",
}


def _extract_country_code(code_text: str) -> str:
    """Extract country code from a contestant code like 'ROU3' or 'KAZ5'.

    All standard codes are 3 letters.
    """
    code_text = code_text.strip()
    m = _CODE_RE.match(code_text)
    if not m:
        return code_text
    return m.group(1)


def _parse_name(raw_name: str) -> tuple[str, str, str]:
    """Parse a student name into (display_name, given_name, family_name).

    Handles three formats found in the 2012 data:
    - Comma-separated (Turkish): "Halil Ibrahim, Gulluk" -> given="Halil Ibrahim", family="Gulluk"
    - Multi-space separated: "Ploscaru    Ioan-Laurentiu" -> given="Ioan-Laurentiu", family="Ploscaru"
    - Single-space: "Gledis Kallco" -> given="Gledis", family="Kallco"
    """
    # Clean up non-breaking spaces and other whitespace artifacts
    raw_name = raw_name.replace("\xa0", " ").strip()
    # Remove stray characters that appear in some names due to encoding
    raw_name = re.sub(r"\s+,", ",", raw_name)

    if "," in raw_name:
        # Turkish format: "Given, Surname"
        parts = raw_name.split(",", 1)
        given_name = parts[0].strip()
        family_name = parts[1].strip()
        display_name = f"{given_name} {family_name}"
        return display_name, given_name, family_name

    # Check for multi-space separator (3+ spaces) indicating "Surname    Given"
    if re.search(r"\s{3,}", raw_name):
        parts = re.split(r"\s{3,}", raw_name, maxsplit=1)
        family_name = parts[0].strip()
        given_name = parts[1].strip() if len(parts) > 1 else ""
        display_name = f"{given_name} {family_name}" if given_name else family_name
        return display_name, given_name, family_name

    # Single-space: treat last word as family name
    parts = raw_name.split()
    if len(parts) < 2:
        return raw_name, "", raw_name
    given_name = " ".join(parts[:-1])
    family_name = parts[-1]
    return raw_name, given_name, family_name


def _parse_score(text: str) -> int | None:
    """Parse a problem score, returning None on failure."""
    try:
        return int(text.strip())
    except (ValueError, TypeError):
        return None


class Parser2012(BaseParser):
    """Parser for JBMO 2012 (HTML table from hms.gr)."""

    def normalize_award(self, award: str | None) -> str | None:
        """Normalize award text, handling JBMO 2012's non-standard labels."""
        if not award:
            return None
        award_lower = award.lower().strip()
        if award_lower in _MEDAL_MAP:
            return _MEDAL_MAP[award_lower]
        # Fall back to base implementation for any other values
        return super().normalize_award(award)

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        """Parse the HTML table and extract contestant results."""
        html = raw_file.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        # The data table is the inner table with border="1"
        table = soup.find("table", attrs={"border": "1"})
        if not table:
            raise ValueError(f"Could not find data table for JBMO {self.year}")

        results: list[ContestantResult] = []

        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 9:
                continue

            # Column 1: Student code (e.g. "ROU3", "TUR5")
            code_text = cells[1].get_text(strip=True)
            if not _CODE_RE.match(code_text):
                continue  # Skip header / non-data rows

            country = _extract_country_code(code_text)

            # Column 7: Student Name
            raw_name = cells[7].get_text()
            if not raw_name or not raw_name.strip():
                continue

            display_name, given_name, family_name = _parse_name(raw_name)

            # Columns 2-5: Prob.1 - Prob.4
            problem_scores = [_parse_score(cells[2 + i].get_text(strip=True)) for i in range(4)]

            # Column 6: Total
            total = _parse_score(cells[6].get_text(strip=True))
            if total is None:
                total = sum(s for s in problem_scores if s is not None)

            # Column 8: Medal
            award_text = cells[8].get_text(strip=True)
            award = self.normalize_award(award_text) if award_text else None

            results.append(
                ContestantResult(
                    name=display_name,
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
