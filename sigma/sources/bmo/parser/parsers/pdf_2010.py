"""Parser for BMO 2010 results (Official Results PDF, math.md/bmo2010/).

The PDF is a single sorted ranking table:

  Rank | Code | Name | P1 | P2 | P3 | P4 | Total | Award

Names are printed ALL CAPS with **per-country ordering** — the organiser
copied each delegation's house style verbatim:

  - Surname-Given: BGR, CYP, HEL, ITA, KAZ, MDA (+ MDA B), MNE, SAU, SRB,
    TJK, TKM
  - Given-Surname: ALB, AZE, FRA, MKD, ROU, TUR, UNK

For countries in the surname-first set we flip to "Given Surname" so the
same contestant matches across editions. Particle cases ("VON BURG",
"AL SAEED") pull the particle into the family name.
"""

from pathlib import Path

from ..models import ContestantResult
from .base import BaseParser
from .code_utils import canonical_team_code, country_base, split_name
from .pdf_common import iter_pdf_rows, normalize_award, parse_int, parse_score

_SURNAME_FIRST_COUNTRIES = {
    "BGR",
    "CYP",
    "HEL",
    "ITA",
    "KAZ",
    "MDA",
    "MNE",
    "SAU",
    "SRB",
    "TJK",
    "TKM",
}


class Parser2010(BaseParser):
    """Parser for BMO 2010 (official PDF ranking)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        results: list[ContestantResult] = []

        for row in iter_pdf_rows(raw_file):
            if len(row) < 9:
                continue
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

            results.append(
                ContestantResult(
                    name=name,
                    country=canonical,
                    problem_scores=problem_scores,
                    total=total,
                    rank=parse_int(row[0]),
                    award=normalize_award(row[8]) if len(row) > 8 else None,
                    given_name=given_name,
                    family_name=family_name,
                )
            )

        self.compute_ranks(results)
        return results
