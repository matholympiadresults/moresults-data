"""Parser for JBMO 2010 results PDF.

JBMO 2010 (14th edition) was held in Chişinău, Moldova. The results PDF
has 2 pages with 93 contestants: 60 official, 31 invited, and 2 reserve.

Columns: No. | Contestant Name | Gender | Country | Code | P1 | P2 | P3 | P4 | Total | Prize

Country codes use old-style abbreviations (e.g. "ROMa", "BUL", "FYR", "GRE").
The Code column holds a per-team contestant number (1-6), not a full country code.
"""

import re
from pathlib import Path

from ..models import ContestantResult
from .base import BaseParser

# Column indices matching the PDF table layout
# No. | Contestant Name | Gender | Country | Code | P1 | P2 | P3 | P4 | Total | Prize
IDX_NAME = 1
IDX_COUNTRY = 3
IDX_CODE = 4
IDX_P1 = 5
IDX_TOTAL = 9
IDX_PRIZE = 10
MIN_COLS = 11


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


def _is_header_row(row: list[str]) -> bool:
    """Return True for header rows that should be skipped."""
    text = " ".join(row).lower()
    return "contestant" in text or ("country" in text and "code" in text)


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


def _normalize_country_code(raw: str) -> str:
    """Normalize old-style country codes by stripping trailing lowercase letters.

    Examples: "ROMa" -> "ROM", "ROMb" -> "ROM", "BULa" -> "BUL",
              "BUL" -> "BUL", "FYR" -> "FYR", "REZ" -> "REZ"
    """
    return re.sub(r"[a-z]+$", "", raw)


def _split_name(full_name: str) -> tuple[str, str]:
    """Split a full name into (given_name, family_name).

    The PDF mixes name formats:
    - "UPPERCASE FIRSTNAME LASTNAME" (all-caps, given-first)
    - "Titlecase Given Family" (title-case, given-first)

    We title-case the result and treat the last token as the family name.
    """
    # Normalize whitespace
    name = re.sub(r"\s+", " ", full_name.strip())

    # Title-case if entirely uppercase
    if name == name.upper():
        name = name.title()

    tokens = name.split()
    if len(tokens) < 2:
        return name, name

    family_name = tokens[-1]
    given_name = " ".join(tokens[:-1])
    return given_name, family_name


class Parser2010(BaseParser):
    """Parser for JBMO 2010 results PDF (single PDF with all contestants)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        results: list[ContestantResult] = []
        seen_numbers: set[str] = set()

        for row in _iter_pdf_rows(raw_file):
            if len(row) < MIN_COLS:
                continue
            if _is_header_row(row):
                continue

            # Skip rows without a valid contestant number
            contestant_no = row[0].strip()
            if not contestant_no or _parse_int(contestant_no) is None:
                continue

            # Deduplicate
            if contestant_no in seen_numbers:
                continue
            seen_numbers.add(contestant_no)

            result = self._parse_row(row)
            if result is not None:
                results.append(result)

        self.compute_ranks(results)
        return results

    def _parse_row(self, row: list[str]) -> ContestantResult | None:
        full_name = row[IDX_NAME].strip()
        if not full_name:
            return None

        country = _normalize_country_code(row[IDX_COUNTRY].strip())
        if not country:
            return None

        given_name, family_name = _split_name(full_name)
        display_name = f"{given_name} {family_name}" if given_name else family_name

        problem_scores = [_parse_score(row[IDX_P1 + i]) for i in range(4)]

        total = _parse_int(row[IDX_TOTAL])
        if total is None:
            total = sum(s for s in problem_scores if s is not None)

        # Skip non-participants (all scores None)
        if all(s is None for s in problem_scores):
            return None

        award = self.normalize_award(row[IDX_PRIZE]) if row[IDX_PRIZE] else None

        # PDF omits awards for reserve (REZ) contestants.
        # Chirac Cristian (score 35) is within the Silver range (25-37).
        # Neacsu Vlad (score 19) is within the Bronze range (11-24).
        if country == "REZ" and award is None:
            if full_name.upper() == "CHIRAC CRISTIAN":
                award = "Silver"
            elif full_name.upper() == "NEACSU VLAD":
                award = "Bronze"

        return ContestantResult(
            name=display_name,
            country=country,
            problem_scores=problem_scores,
            total=total,
            rank=None,
            award=award,
            given_name=given_name,
            family_name=family_name,
        )
