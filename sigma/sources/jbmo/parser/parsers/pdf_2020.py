"""Parser for JBMO 2020 results (PDF).

JBMO 2020 was held online due to COVID-19. The PDF contains only medalists
(~70 of 108 contestants) and uses anonymous codes (e.g. BGR4) instead of
real names.

Header: rank | COUNTRY | NAME (code) | P1 | P2 | P3 | P4 | TOTAL | MEDALS
Note: The header misspells COUNTRY as "C0UNTRY" (zero instead of O).
Ranks may be multiline (multiple tied positions) or empty for ties.
Country names may contain newlines for multi-word names.
"""

import re
from pathlib import Path

from ..models import ContestantResult
from .base import BaseParser


def _iter_pdf_rows(raw_file: Path):
    """Yield all table rows from the PDF as lists of stripped strings."""
    import pdfplumber

    with pdfplumber.open(raw_file) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table:
                    continue
                for row in table:
                    if row is None:
                        continue
                    yield [str(cell).strip() if cell else "" for cell in row]


def _is_header_or_title_row(row: list[str]) -> bool:
    """Return True for header rows or title rows that should be skipped."""
    text = " ".join(row).lower()
    # Title row: "JBMO 2020-RESULTS" or similar
    if "jbmo" in text and "result" in text:
        return True
    # Header row: "C0UNTRY" (with zero) or "COUNTRY" and "NAME"
    if ("c0untry" in text or "country" in text) and "name" in text:
        return True
    return False


def _normalize_country(raw: str) -> str:
    """Normalize a country name by collapsing newlines and extra whitespace."""
    return re.sub(r"\s+", " ", raw.replace("\n", " ")).strip()


def _parse_int(value: str) -> int | None:
    """Parse an integer, returning None on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _parse_score(value: str) -> int | None:
    """Parse a problem score in [0, 10], returning None if out of range or invalid."""
    score = _parse_int(value)
    if score is None or score < 0 or score > 10:
        return None
    return score


def _normalize_award(award: str | None) -> str | None:
    """Normalize award text to standard format."""
    if not award:
        return None
    award_lower = award.lower().strip()
    if "gold" in award_lower:
        return "Gold"
    if "silver" in award_lower:
        return "Silver"
    if "bronze" in award_lower:
        return "Bronze"
    if "honourable" in award_lower or "honorable" in award_lower or "hm" in award_lower:
        return "Honourable Mention"
    return award if award else None


# Column indices for the JBMO 2020 PDF table layout
IDX_RANK = 0
IDX_COUNTRY = 1
IDX_NAME = 2
IDX_P1 = 3
IDX_P4 = 6
IDX_TOTAL = 7
IDX_MEDAL = 8
MIN_COLS = 9


class Parser2020(BaseParser):
    """Parser for JBMO 2020 (PDF, anonymous codes, medalists only)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        results: list[ContestantResult] = []
        seen: set[tuple[str, str]] = set()

        for row in _iter_pdf_rows(raw_file):
            if len(row) < MIN_COLS:
                continue
            if _is_header_or_title_row(row):
                continue

            result = self._parse_row(row)
            if result is None:
                continue

            key = (result.name, result.country)
            if key in seen:
                continue
            seen.add(key)
            results.append(result)

        self.compute_ranks(results)
        return results

    def _parse_row(self, row: list[str]) -> ContestantResult | None:
        raw_name = row[IDX_NAME]
        if not raw_name:
            return None

        # The "name" is an anonymous code like "BGR4" -- skip if it doesn't
        # look like a valid contestant code.
        name = raw_name.strip()
        if not re.match(r"^[A-Z]{2,4}\d+$", name):
            return None

        country = _normalize_country(row[IDX_COUNTRY])
        if not country:
            return None

        problem_scores = [_parse_score(row[IDX_P1 + i]) for i in range(4)]

        total = _parse_int(row[IDX_TOTAL])
        if total is None:
            total = sum(s for s in problem_scores if s is not None)

        award = _normalize_award(row[IDX_MEDAL])

        return ContestantResult(
            name=name,
            country=country,
            problem_scores=problem_scores,
            total=total,
            rank=None,  # Will be computed by compute_ranks
            award=award,
            given_name=None,
            family_name=None,
        )
