"""Parser for BMO 2025 results (PDF).

Header: Given Name(s) | Surname | Code | P1..P4 | Total | M/G | Prize
This edition supplies given name and surname in separate columns, and has
no rank or country column — the country is encoded in the Code field.
Only "Member" rows count toward the official ranking; "Guest" rows are
secondary/B teams that compete off the podium.
"""

from pathlib import Path

from ..models import ContestantResult
from .base import BaseParser
from .pdf_common import (
    extract_country_from_code,
    iter_pdf_rows,
    normalize_award,
    parse_int,
    parse_score,
)

IDX_GIVEN = 0
IDX_SURNAME = 1
IDX_CODE = 2
IDX_P1 = 3
IDX_TOTAL = 7
IDX_MG = 8
IDX_PRIZE = 9
MIN_COLS = 10


class Parser2025(BaseParser):
    """Parser for BMO 2025 (PDF, separate given/surname columns)."""

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
        given_name = row[IDX_GIVEN] or None
        family_name = row[IDX_SURNAME] or None
        if not given_name and not family_name:
            return None
        name = f"{given_name or ''} {family_name or ''}".strip()

        country = extract_country_from_code(row[IDX_CODE]) or "UNK"

        problem_scores = [parse_score(row[IDX_P1 + i]) for i in range(4)]

        total = parse_int(row[IDX_TOTAL])
        if total is None:
            total = sum(s for s in problem_scores if s is not None)

        return ContestantResult(
            name=name,
            country=country,
            problem_scores=problem_scores,
            total=total,
            rank=None,  # No rank column; compute_ranks fills this in.
            award=normalize_award(row[IDX_PRIZE]),
            given_name=given_name,
            family_name=family_name,
        )


def _is_header_row(row: list[str]) -> bool:
    text = " ".join(row).lower()
    return "given name" in text or "surname" in text
