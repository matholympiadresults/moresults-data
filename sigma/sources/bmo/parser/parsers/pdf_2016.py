"""Parser for BMO 2016 results (PDF).

Header: '' | First Name(s) | Last Name | Country | Code | Official |
        P1 | P2 | P3 | P4 | Total | Medal

Given and family names are already pre-split into separate columns, so no
surname-flip heuristics are needed. The ``Official`` column (``y``/``n``)
marks main-team vs invited/guest rows; the ingester infers B-team status
from the code alone (e.g. ``ALB-B3`` → ``ALBB3`` via ``canonical_team_code``).
"""

from pathlib import Path

from ..models import ContestantResult
from .base import BaseParser
from .code_utils import canonical_team_code
from .pdf_common import iter_pdf_rows, normalize_award, parse_int, parse_score

IDX_RANK = 0
IDX_FIRST = 1
IDX_LAST = 2
IDX_COUNTRY = 3
IDX_CODE = 4
IDX_OFFICIAL = 5
IDX_P1 = 6
IDX_TOTAL = 10
IDX_MEDAL = 11
MIN_COLS = 12


class Parser2016(BaseParser):
    """Parser for BMO 2016 (PDF, pre-split given/family name columns)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        results: list[ContestantResult] = []
        seen: set[tuple[str, str]] = set()

        for row in iter_pdf_rows(raw_file):
            if len(row) < MIN_COLS:
                continue
            # Skip the header row on each page.
            if not row[IDX_RANK].strip().isdigit():
                continue

            given_name = row[IDX_FIRST].strip()
            family_name = row[IDX_LAST].strip()
            raw_code = row[IDX_CODE].strip()
            if not given_name or not family_name or not raw_code:
                continue

            name = f"{given_name} {family_name}"
            canonical = canonical_team_code(raw_code)

            problem_scores = [parse_score(row[IDX_P1 + i]) for i in range(4)]

            total = parse_int(row[IDX_TOTAL])
            if total is None:
                total = sum(s for s in problem_scores if s is not None)

            key = (name, canonical)
            if key in seen:
                continue
            seen.add(key)

            results.append(
                ContestantResult(
                    name=name,
                    country=canonical,
                    problem_scores=problem_scores,
                    total=total,
                    rank=parse_int(row[IDX_RANK]),
                    award=normalize_award(row[IDX_MEDAL]),
                    given_name=given_name,
                    family_name=family_name,
                )
            )

        self.compute_ranks(results)
        return results
