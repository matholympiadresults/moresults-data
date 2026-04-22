"""Parser for BMO 2013 results (two PDFs: members + guests).

The 2013 source is **medalists-only**: two PDFs with identical schemas
(``Medals_BMO_2013__Members_.pdf`` for the official/member delegations and
``Medals_BMO_2013__Guests_.pdf`` for invited delegations). Each PDF has a
single table with columns:

  RANK | CODE | COUNTRY | NAME | MEDAL

There are **no per-problem scores and no totals** in the source. To keep
the schema happy we store:

  - ``problem_scores = [None, None, None, None]``
  - ``total = 0`` — placeholder; there is no honest value
  - ``rank`` = value from the RANK column (meaningful: source ranks medalists)
  - ``award`` = normalised MEDAL column (Gold / Silver / Bronze)

Non-medalists are **not present** in the source and are therefore not
emitted. Cross-edition person matching still works (the key use case),
but score queries on 2013 are meaningless.

Names are ALL-CAPS. In 2013 only Greek delegation (``HEL``) is printed
surname-first — every other delegation (CYP, ITA, KAZ, BIH, MDA, …) is
given-first, verified by inspecting the rows (see file header comment in
``pdf_2009`` for the equivalent 2009 handling).
"""

from pathlib import Path

from ..models import ContestantResult
from .base import BaseParser
from .code_utils import canonical_team_code, country_base, split_name
from .pdf_common import iter_pdf_rows, normalize_award, parse_int

_SURNAME_FIRST_COUNTRIES = {"HEL"}

_GUESTS_FILENAME = "Medals_BMO_2013__Guests_.pdf"


class Parser2013(BaseParser):
    """Parser for BMO 2013 (medalists-only; two PDFs combined).

    ``parse(raw_file)`` expects the members PDF and also reads the guests
    PDF from the same directory, returning a single combined list.
    """

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        results: list[ContestantResult] = []

        guests_file = raw_file.parent / _GUESTS_FILENAME
        for pdf_path in (raw_file, guests_file):
            results.extend(self._parse_one(pdf_path))

        # Do NOT call self.compute_ranks(results): the source-provided
        # ranks are meaningful, and we have no totals to compute from.
        return results

    @staticmethod
    def _parse_one(pdf_path: Path) -> list[ContestantResult]:
        rows: list[ContestantResult] = []
        for row in iter_pdf_rows(pdf_path):
            if len(row) < 5:
                continue
            # Skip the header row.
            if row[0].strip().upper() == "RANK":
                continue
            rank = parse_int(row[0])
            if rank is None:
                continue

            code = row[1].strip()
            raw_name = row[3].strip()
            if not code or not raw_name:
                continue

            canonical = canonical_team_code(code)
            name, given_name, family_name = split_name(
                raw_name,
                surname_first=country_base(canonical) in _SURNAME_FIRST_COUNTRIES,
            )

            rows.append(
                ContestantResult(
                    name=name,
                    country=canonical,
                    problem_scores=[None, None, None, None],
                    total=0,  # placeholder: source has no totals/scores
                    rank=rank,
                    award=normalize_award(row[4]),
                    given_name=given_name,
                    family_name=family_name,
                )
            )
        return rows
