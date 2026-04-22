"""Parser for BMO 2019 results (Chișinău, Moldova).

The ``results.html`` snapshot has exactly one table with the layout:

  Rank | Contestant | Country | P1 | P2 | P3 | P4 | Total | Award

The ``Contestant`` cell separates given and family names with a literal TAB
(``"JOVAN\tTOROMANOVIĆ"``). A handful of rows use a plain space instead
(Albania, Romania, and a few isolated contestants from other teams) but the
Given-Surname order is consistent across every delegation — including the
teams that historically printed surname-first (CYP, HEL, KAZ, MDA, ROU).
So no country needs to be flipped for this edition.

The ``Country`` column is a clean ISO/BMO code (``SRB``, ``ROU``, ``HEL``,
``UNK`` …). The only exception is Moldova's second team, which appears as
``MDA(B)``; we strip the parentheses so ``canonical_team_code`` produces
``MDAB`` — the form the ingester recognises as a B-team.
"""

from pathlib import Path

from bs4 import BeautifulSoup

from ..models import ContestantResult
from .base import BaseParser
from .code_utils import canonical_team_code, country_base, split_name
from .pdf_common import normalize_award, parse_int, parse_score

# No delegation printed surname-first in 2019 — every row is Given-Surname.
_SURNAME_FIRST_COUNTRIES: set[str] = set()


class Parser2019(BaseParser):
    """Parser for BMO 2019 (HTML single-table snapshot)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        html = raw_file.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        table = soup.find("table")
        if table is None:
            raise ValueError(f"Could not find results table for BMO {self.year}")

        results: list[ContestantResult] = []
        for row in table.find_all("tr"):
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) < 9:
                continue

            raw_name = cells[1]
            raw_code = cells[2]
            if not raw_name or not raw_code:
                continue
            if raw_name.lower() == "contestant" and raw_code.lower() == "country":
                continue

            # Normalise "MDA(B)" -> "MDAB" so canonical_team_code classifies it
            # as the B-team form the ingester understands.
            raw_code = raw_code.replace("(", " ").replace(")", " ")
            canonical = canonical_team_code(raw_code)

            # The contestant cell is TAB-separated "GIVEN\tFAMILY"; collapse any
            # runs of whitespace (tab + stray spaces) to a single space before
            # splitting so `split_name` tokenises cleanly.
            normalised_name = " ".join(raw_name.split())
            name, given_name, family_name = split_name(
                normalised_name,
                surname_first=country_base(canonical) in _SURNAME_FIRST_COUNTRIES,
            )

            problem_scores = [parse_score(cells[3 + i]) for i in range(4)]

            total = parse_int(cells[7])
            if total is None:
                total = sum(s for s in problem_scores if s is not None)

            award = normalize_award(cells[8]) if len(cells) > 8 else None

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
