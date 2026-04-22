"""Parser for JBMO 2014 results from HTML.

Source: http://www.jbmo2014.smm.com.mk/results/total (via Wayback Machine)
HTML table inside the page body.
Columns: Rank (empty), Name and Surname, Code, P1, P2, P3, P4, Total, Medal.

Names are in a single column in Western order ("Given Surname"), with
surnames sometimes in UPPERCASE (e.g. "Alexandru MIHALCU") and sometimes
in mixed case (e.g. "Mahammad Shirinov").  Some names are entirely
uppercase (e.g. "OMAR TAWFIG ALRABIAH").  Country codes are embedded in
the Code column, e.g. "ROU2" -> "ROU".
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup

from ..models import ContestantResult
from .base import BaseParser

# Matches letter prefix and trailing digit(s) in codes like "ROU1", "IRN3".
_CODE_RE = re.compile(r"^([A-Z]+?)(\d+)$")


def _extract_country_code(code_text: str) -> str:
    """Extract country code from a contestant code like 'ROU2' or 'IRN3'.

    All standard codes are 3 letters.  A 4-letter prefix ending with 'B'
    indicates a B-team, e.g. "TURB" -> "TUR(B)".
    """
    code_text = code_text.strip()
    m = _CODE_RE.match(code_text)
    if not m:
        return code_text
    letters = m.group(1)
    if len(letters) >= 4 and letters.endswith("B"):
        return f"{letters[:-1]}(B)"
    return letters


def _split_name(full_name: str) -> tuple[str, str]:
    """Split a Western-order name into (given_name, family_name).

    The last word is treated as the family name, and all preceding words
    as the given name.  If the surname is fully uppercase, it is
    title-cased.  Examples::

        "Alexandru MIHALCU"      -> ("Alexandru", "Mihalcu")
        "Mahammad Shirinov"      -> ("Mahammad", "Shirinov")
        "OMAR TAWFIG ALRABIAH"   -> ("Omar Tawfig", "Alrabiah")
        "Ciprian-Mircea BONCIOCAT" -> ("Ciprian-Mircea", "Bonciocat")
    """
    # Collapse multiple spaces
    parts = full_name.split()
    if len(parts) < 2:
        return "", full_name

    family_name = parts[-1]
    given_parts = parts[:-1]

    # Title-case parts that are fully uppercase
    family_name = _titlecase_word(family_name)
    given_parts = [_titlecase_word(p) for p in given_parts]

    return " ".join(given_parts), family_name


def _titlecase_word(word: str) -> str:
    """Title-case a word if it is fully uppercase.

    Handles hyphenated names: "BONCIOCAT" -> "Bonciocat",
    preserves already mixed-case: "Félix" -> "Félix".
    """
    if word.isupper():
        return "-".join(part.capitalize() for part in word.split("-"))
    return word


def _parse_score(text: str) -> int | None:
    """Parse a problem score, returning None on failure."""
    try:
        return int(text.strip())
    except (ValueError, TypeError):
        return None


class Parser2014(BaseParser):
    """Parser for JBMO 2014 (HTML table from jbmo2014.smm.com.mk via Wayback Machine)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        """Parse the HTML table and extract contestant results."""
        html = raw_file.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        # Find the results table (there is one main table in the page body)
        table = soup.find("table")
        if not table:
            raise ValueError(f"Could not find results table for JBMO {self.year}")

        results: list[ContestantResult] = []

        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 9:
                continue

            # Column 0: Rank (empty in source, we compute our own)
            # Column 1: Name and Surname
            full_name_raw = cells[1].get_text(strip=True)
            if not full_name_raw:
                continue

            # Column 2: Code (e.g. "ROU2", "IRN3")
            code_text = cells[2].get_text(strip=True)
            if not _CODE_RE.match(code_text):
                continue  # Skip non-data rows
            country = _extract_country_code(code_text)

            # Normalize whitespace in name
            full_name = " ".join(full_name_raw.split())
            given_name, family_name = _split_name(full_name)

            # Build display name from normalized parts
            display_name = f"{given_name} {family_name}" if given_name else family_name

            # Columns 3-6: P1-P4
            problem_scores = [_parse_score(cells[3 + i].get_text(strip=True)) for i in range(4)]

            # Column 7: Total
            total = _parse_score(cells[7].get_text(strip=True))
            if total is None:
                total = sum(s for s in problem_scores if s is not None)

            # Column 8: Medal (GOLD, SILVER, BRONZE, or empty)
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
