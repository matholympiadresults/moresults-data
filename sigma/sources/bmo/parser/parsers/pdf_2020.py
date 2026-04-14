"""Parser for BMO 2020 results (PDF).

Header: RANK | NAME AND SURNAME | COUNTRY | COD | P1 | P2 | P3 | P4 | TOTAL | MEDAL
Names are printed in SURNAME GIVEN order and ALL CAPS. We flip them to
"Given Surname" so the same contestant matches across editions.
"""

from pathlib import Path

from sigma.matching.person_matcher import capitalize_name

from ..models import ContestantResult
from .base import BaseParser
from .pdf_common import (
    extract_country_from_code,
    iter_pdf_rows,
    normalize_award,
    parse_int,
    parse_score,
)

IDX_RANK = 0
IDX_NAME = 1
IDX_COUNTRY = 2
IDX_CODE = 3
IDX_P1 = 4
IDX_P4 = 7
IDX_TOTAL = 8
IDX_MEDAL = 9
MIN_COLS = 10


class Parser2020(BaseParser):
    """Parser for BMO 2020 (PDF, surname-first ALL CAPS)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        results: list[ContestantResult] = []
        seen: set[tuple[str, str]] = set()

        for row in iter_pdf_rows(raw_file):
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
        raw_name = row[IDX_NAME]
        if not raw_name:
            return None

        # Title-case the uppercase source, then flip "Surname Given" to "Given Surname".
        titled = capitalize_name(raw_name)
        tokens = titled.split()
        if len(tokens) < 2:
            family_name = None
            given_name = None
            name = titled
        else:
            family_name = tokens[0]
            given_name = " ".join(tokens[1:])
            name = f"{given_name} {family_name}"

        country = row[IDX_COUNTRY] or extract_country_from_code(row[IDX_CODE]) or "UNK"

        problem_scores = [parse_score(row[IDX_P1 + i]) for i in range(4)]

        total = parse_int(row[IDX_TOTAL])
        if total is None:
            total = sum(s for s in problem_scores if s is not None)

        return ContestantResult(
            name=name,
            country=country,
            problem_scores=problem_scores,
            total=total,
            rank=parse_int(row[IDX_RANK]),
            award=normalize_award(row[IDX_MEDAL]),
            given_name=given_name,
            family_name=family_name,
        )


def _is_header_row(row: list[str]) -> bool:
    text = " ".join(row).lower()
    return "name" in text and "surname" in text
