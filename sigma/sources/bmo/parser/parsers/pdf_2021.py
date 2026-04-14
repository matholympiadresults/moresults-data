"""Parser for BMO 2021 results (PDF).

Header: RANK | STUDENT NAME&SURNAME | COUNTRY | CODE | PROBLEM 1..4 | TOTAL | MEDAL
Names are already printed in "Given Surname" order, just ALL CAPS. We only
normalize the case.
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
IDX_TOTAL = 8
IDX_MEDAL = 9
MIN_COLS = 10


class Parser2021(BaseParser):
    """Parser for BMO 2021 (PDF, given-first ALL CAPS)."""

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
        name = capitalize_name(row[IDX_NAME])
        if not name:
            return None

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
        )


def _is_header_row(row: list[str]) -> bool:
    text = " ".join(row).lower()
    return "student" in text or ("name" in text and "surname" in text)
