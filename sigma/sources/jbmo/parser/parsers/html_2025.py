"""Parser for JBMO 2025 results (Excel-exported HTML).

The HTML file contains a single ``<table>`` exported from Excel with columns:

  Rank | Contestant | Team | Points | Award

Key details:
- 135 total contestants.
- No per-problem scores; only total points are available.
- Names are in "Given Surname" order (e.g. "Farhad Iskandar").
- Names may contain embedded newlines and extra spaces from the Excel export;
  all whitespace is collapsed to single spaces.
- Country codes are 3-letter (or with suffix, e.g. "MKD-B").
- Rank may be empty for tied contestants (sharing same rank as previous row).
- Award values: "Gold Medal", "Silver Medal", "Bronze Medal",
  "Honorable Mention", or empty.
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup

from ..models import ContestantResult
from .base import BaseParser


def _clean_text(text: str) -> str:
    """Collapse all whitespace (including newlines) to single spaces and strip."""
    return re.sub(r"\s+", " ", text).strip()


def _parse_int(value: str) -> int | None:
    """Parse an integer, returning None on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _split_name(full_name: str) -> tuple[str | None, str | None]:
    """Split a 'Given Surname' name into (given_name, family_name).

    The last token is treated as the family name; everything before it
    is the given name.
    """
    tokens = full_name.strip().split()
    if len(tokens) < 2:
        return None, None
    return " ".join(tokens[:-1]), tokens[-1]


def _is_header_row(cells: list[str]) -> bool:
    """Return True if this row looks like the header."""
    text = " ".join(cells).lower()
    return "rank" in text and "contestant" in text


class Parser2025(BaseParser):
    """Parser for JBMO 2025 (Excel-exported HTML, totals only, no per-problem scores)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        html = raw_file.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        table = soup.find("table")
        if not table:
            raise ValueError(f"Could not find results table for JBMO {self.year}")

        rows = table.find_all("tr")
        results: list[ContestantResult] = []
        last_rank: int | None = None

        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 5:
                continue

            cell_texts = [_clean_text(cell.get_text()) for cell in cells]

            if _is_header_row(cell_texts):
                continue

            result, last_rank = self._parse_row(cell_texts, last_rank)
            if result is not None:
                results.append(result)

        self.compute_ranks(results)
        return results

    def _parse_row(
        self,
        cells: list[str],
        last_rank: int | None,
    ) -> tuple[ContestantResult | None, int | None]:
        """Parse a single data row.

        Returns:
            Tuple of (result or None, updated last_rank).
        """
        # Columns: Rank(0), Contestant(1), Team(2), Points(3), Award(4)
        name = cells[1]
        if not name:
            return None, last_rank

        country = cells[2]
        if not country:
            return None, last_rank

        total = _parse_int(cells[3])
        if total is None:
            return None, last_rank

        # Rank may be empty for tied contestants
        rank_val = _parse_int(cells[0])
        if rank_val is not None:
            last_rank = rank_val

        award = self.normalize_award(cells[4]) if cells[4] else None

        given_name, family_name = _split_name(name)

        return (
            ContestantResult(
                name=name,
                country=country,
                problem_scores=[None, None, None, None],
                total=total,
                rank=None,  # Will be computed by compute_ranks
                award=award,
                given_name=given_name,
                family_name=family_name,
            ),
            last_rank,
        )
