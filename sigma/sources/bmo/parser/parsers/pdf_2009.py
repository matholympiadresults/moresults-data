"""Parser for BMO 2009 results (PDF from the Serbian organiser).

The ``RESULTS_BMO_2009.pdf`` file contains two sections, "OFFICIAL PARTICIPANTS"
and "INVITED GUESTS", each with the same table layout:

  No. | Code | Name | P1 | P2 | P3 | P4 | SUM | PRIZES

Prize values are "FIRST PRIZE" / "SECOND PRIZE" / "THIRD PRIZE" (Gold / Silver /
Bronze by the usual BMO convention) or blank.

Names are mostly Given-Surname but BIH, HEL, ITA, and KAZ are printed
Surname-Given. We flip those so IMO cross-edition matching works.
"""

from pathlib import Path

from ..models import ContestantResult
from .base import BaseParser
from .code_utils import canonical_team_code, country_base, split_name
from .pdf_common import iter_pdf_rows, parse_int, parse_score

_PRIZE_MAP = {
    "first prize": "Gold",
    "second prize": "Silver",
    "third prize": "Bronze",
}

_SURNAME_FIRST_COUNTRIES = {"BIH", "HEL", "ITA", "KAZ"}


class Parser2009(BaseParser):
    """Parser for BMO 2009 (PDF, two sections with same shape)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        results: list[ContestantResult] = []

        for row in iter_pdf_rows(raw_file):
            if len(row) < 9:
                continue
            # Skip header rows ("No. | Code | Name | ... | PRIZES" / "PRIZE").
            if row[0].lower() == "no." and row[1].lower() == "code":
                continue
            # The PDF has a footnote after the last table row; skip anything that
            # doesn't start with a numeric position.
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

            problem_scores = [parse_score(row[3 + i]) for i in range(4)]

            total = parse_int(row[7])
            if total is None:
                total = sum(s for s in problem_scores if s is not None)

            prize = row[8].strip().lower() if len(row) > 8 else ""
            award = _PRIZE_MAP.get(prize)

            results.append(
                ContestantResult(
                    name=name,
                    country=canonical,
                    problem_scores=problem_scores,
                    total=total,
                    rank=None,
                    award=award,
                    given_name=given_name,
                    family_name=family_name,
                )
            )

        self.compute_ranks(results)
        return results
