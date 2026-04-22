"""Parser for JBMO 2015 results from HTML.

Source: http://www.dms.rs/jbmo/results/results.html
Excel-generated HTML table (MSO styling) with ~106 contestants.
Columns: Rank, First name(s), Last name, Team, Code, Official (y/n),
         P1, P2, P3, P4, SUM, Medal.

Names are split across two columns: given name and last name.
The "Team" column contains country names (e.g. "Serbia", "Romania").
The "Official" column distinguishes official vs guest contestants; all
contestants are included regardless.
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup

from ..models import ContestantResult
from .base import BaseParser

# Matches a numeric rank value (used to identify data rows).
_RANK_RE = re.compile(r"^\d+$")


def _parse_score(text: str) -> int | None:
    """Parse a problem score, returning None on failure."""
    try:
        return int(text.strip())
    except (ValueError, TypeError):
        return None


class Parser2015(BaseParser):
    """Parser for JBMO 2015 (Excel-generated HTML table from dms.rs)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        """Parse the HTML table and extract contestant results."""
        html = raw_file.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        table = soup.find("table")
        if not table:
            raise ValueError(f"Could not find table for JBMO {self.year}")

        results: list[ContestantResult] = []

        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 12:
                continue

            # Column 0: Rank — use it to identify data rows (skip header)
            rank_text = cells[0].get_text(strip=True)
            if not _RANK_RE.match(rank_text):
                continue

            # Column 1: First name(s)
            given_name = cells[1].get_text(strip=True)
            # Column 2: Last name
            family_name = cells[2].get_text(strip=True)

            if not given_name and not family_name:
                continue

            full_name = f"{given_name} {family_name}".strip()

            # Column 3: Team (country name) - normalize embedded whitespace
            country = " ".join(cells[3].get_text(strip=True).split())

            # Column 4: Code (contestant code) — not used for output
            # Column 5: Official (y/n) — include all contestants

            # Columns 6-9: P1-P4
            problem_scores = [_parse_score(cells[6 + i].get_text(strip=True)) for i in range(4)]

            # Column 10: SUM (total score)
            total = _parse_score(cells[10].get_text(strip=True))
            if total is None:
                total = sum(s for s in problem_scores if s is not None)

            # Column 11: Medal
            award_text = cells[11].get_text(strip=True)
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
