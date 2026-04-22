"""Parser for BMO 2014 results (individual-results.pdf).

The 3-page PDF is a single sorted ranking table with columns:

  Rank | Code | Name | Total | P1 | P2 | P3 | P4

Note the column order: Total precedes the per-problem scores, and there is
**no Medal/Award column** — awards cannot be derived from this source, so
every ``ContestantResult`` has ``award=None``.

Names are Given-Surname for every delegation except CYP, which is printed
Surname-Given (e.g. "Voskou Marios", "Economou Andreas"). We flip the CYP
rows so the same contestant matches across editions.
"""

from pathlib import Path

from ..models import ContestantResult
from .base import BaseParser
from .code_utils import canonical_team_code, country_base, split_name
from .pdf_common import iter_pdf_rows, parse_int, parse_score

_SURNAME_FIRST_COUNTRIES = {"CYP"}


class Parser2014(BaseParser):
    """Parser for BMO 2014 (individual-results.pdf)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        results: list[ContestantResult] = []

        for row in iter_pdf_rows(raw_file):
            if len(row) < 8:
                continue
            # Skip the decorative header row (['', '', '', '', '1', '2', '3', '4'])
            # and any other non-data rows by requiring a numeric rank in column 0.
            if not row[0].strip().isdigit():
                continue

            code = row[1].strip()
            raw_name = row[2].strip()
            if not code or not raw_name:
                continue

            canonical = canonical_team_code(code)
            name, given_name, family_name = split_name(
                raw_name,
                surname_first=country_base(canonical) in _SURNAME_FIRST_COUNTRIES,
            )

            problem_scores = [parse_score(row[4 + i]) for i in range(4)]

            total = parse_int(row[3])
            if total is None:
                total = sum(s for s in problem_scores if s is not None)

            results.append(
                ContestantResult(
                    name=name,
                    country=canonical,
                    problem_scores=problem_scores,
                    total=total,
                    rank=parse_int(row[0]),
                    award=None,
                    given_name=given_name,
                    family_name=family_name,
                )
            )

        self.compute_ranks(results)
        return results
