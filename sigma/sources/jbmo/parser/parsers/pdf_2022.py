"""Parser for JBMO 2022 results (PDF).

Header (repeated on each page):
  '' | Code | Given Name(s) | Surname | Problem 1..4 | Total | Medals

Only medalists (~81 of ~110 contestants) appear in the PDF.

Country codes like "FRA1", "B&H3" are stripped of trailing digits.
Names have separate Given Name and Surname columns; we store both and
combine them as "Given Surname".

Medal column may contain "Silver and Special Prize" which normalises to
Silver.
"""

import re
from pathlib import Path

from ..models import ContestantResult
from .base import BaseParser

IDX_RANK = 0
IDX_CODE = 1
IDX_GIVEN = 2
IDX_SURNAME = 3
IDX_P1 = 4
IDX_TOTAL = 8
IDX_MEDAL = 9
MIN_COLS = 10


class Parser2022(BaseParser):
    """Parser for JBMO 2022 (PDF with separate given-name / surname columns)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        results: list[ContestantResult] = []
        seen: set[tuple[str, str]] = set()

        for row in _iter_pdf_rows(raw_file):
            if len(row) < MIN_COLS:
                continue
            if _is_header_row(row):
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
        given = row[IDX_GIVEN].strip()
        surname = row[IDX_SURNAME].strip()

        # Both name parts are required
        if not given and not surname:
            return None

        name = f"{given} {surname}".strip()
        given_name = given or None
        family_name = surname or None

        country = _extract_country_from_code(row[IDX_CODE]) or "UNK"

        problem_scores = [_parse_score(row[IDX_P1 + i]) for i in range(4)]

        total = _parse_int(row[IDX_TOTAL])
        if total is None:
            total = sum(s for s in problem_scores if s is not None)

        return ContestantResult(
            name=name,
            country=country,
            problem_scores=problem_scores,
            total=total,
            rank=_parse_int(row[IDX_RANK]),
            award=self.normalize_award(row[IDX_MEDAL]),
            given_name=given_name,
            family_name=family_name,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    """Detect repeated header rows (appear on every page)."""
    text = " ".join(row).lower()
    return "code" in text and ("given name" in text or "surname" in text)


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _parse_score(value: str) -> int | None:
    score = _parse_int(value)
    if score is None or score < 0 or score > 10:
        return None
    return score


def _extract_country_from_code(code: str) -> str | None:
    """Extract country prefix from codes like 'FRA1', 'B&H3', 'MKD1'.

    Strips trailing digits, keeping letters and '&'.
    """
    match = re.match(r"^([A-Za-z&]+)\d*$", code.strip())
    return match.group(1).upper() if match else None
