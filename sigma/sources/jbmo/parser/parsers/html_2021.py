"""Parser for JBMO 2021 results from per-country HTML pages.

JBMO 2021 was hosted online by Romania. Results are split across individual
country pages (e.g. ``jbmo_2021_france.html``).  Each page contains two tables:

- Table 0: Team information (leader / deputy-leader) -- skipped.
- Table 1: Contestants with columns:
  Code | Name | P1 | P2 | P3 | P4 | Total | Award

Names are in "Surname Given" order and must be flipped to "Given Surname".
Country codes are extracted from the Code column (e.g. "FRA 1" -> "FRA",
"MDA(B) 4" -> "MDA(B)").  Awards are GOLD / SILVER / BRONZE or a dash/empty
for no award.

The parser receives the primary file path (``jbmo_2021_participants.html``)
but discovers and parses all sibling ``jbmo_2021_*.html`` country files in the
same directory (excluding the participants page itself).
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup

from ..models import ContestantResult
from .base import BaseParser

# Matches the country-code prefix in the Code column, e.g. "FRA" or "MDA(B)".
# The code is everything before the last whitespace + contestant number.
_CODE_RE = re.compile(r"^(.+?)\s+\d+$")


def _extract_country_code(code_text: str) -> str:
    """Extract country code from a contestant code like 'FRA 1' or 'MDA(B) 4'."""
    m = _CODE_RE.match(code_text)
    if m:
        return m.group(1)
    return code_text


def _flip_name(raw_name: str) -> tuple[str, str, str]:
    """Flip 'Surname Given' to 'Given Surname'.

    Returns (display_name, given_name, family_name).
    For single-word names the word is treated as the family name.
    """
    parts = raw_name.split()
    if len(parts) < 2:
        return raw_name, "", raw_name
    family_name = parts[0]
    given_name = " ".join(parts[1:])
    display_name = f"{given_name} {family_name}"
    return display_name, given_name, family_name


def _parse_score(text: str) -> int | None:
    """Parse a problem score, returning None on failure."""
    try:
        return int(text)
    except (ValueError, TypeError):
        return None


class Parser2021(BaseParser):
    """Parser for JBMO 2021 (per-country HTML pages)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        directory = raw_file.parent
        country_files = sorted(
            f for f in directory.glob("jbmo_2021_*.html") if f.name != "jbmo_2021_participants.html"
        )

        results: list[ContestantResult] = []
        for country_file in country_files:
            results.extend(self._parse_country_file(country_file))

        self.compute_ranks(results)
        return results

    def _parse_country_file(self, path: Path) -> list[ContestantResult]:
        """Parse a single country HTML file and return its contestant results."""
        raw = path.read_bytes()
        # The source website double-encoded UTF-8: the HTML contains UTF-8 bytes
        # that were encoded as if they were Latin-1.  Undo the double-encoding.
        try:
            html = raw.decode("utf-8").encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            html = raw.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        tables = soup.find_all("table")
        if len(tables) < 2:
            return []

        # Table 0 is team info; table 1 is contestants
        contestant_table = tables[1]
        rows = contestant_table.find_all("tr")

        results: list[ContestantResult] = []
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 8:
                continue

            code_text = cells[0].get_text(strip=True)
            raw_name = cells[1].get_text(strip=True)
            if not raw_name:
                continue

            country = _extract_country_code(code_text)
            display_name, given_name, family_name = _flip_name(raw_name)

            problem_scores = [_parse_score(cells[2 + i].get_text(strip=True)) for i in range(4)]

            total_text = cells[6].get_text(strip=True)
            total = _parse_score(total_text)
            if total is None:
                total = sum(s for s in problem_scores if s is not None)

            award_text = cells[7].get_text(strip=True)
            award = self.normalize_award(award_text) if award_text and award_text != "-" else None

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

        return results
