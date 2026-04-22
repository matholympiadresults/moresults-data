"""Parser for BMO 2017 results (HTML snapshot from bmo2017.smm.com.mk).

The official results page ``results-total.html`` is sorted by total score and
each ``<tr>`` in the ranking table has nine ``<td>`` cells:

  Rank | Name and Surname | Code | P1 | P2 | P3 | P4 | Total | Medal

Medal values appear inline per row as ``GOLD`` / ``SILVER`` / ``BRONZE`` or
empty for unawarded contestants (there were no Honourable Mentions in 2017).

Country codes include North Macedonia's two host squads: ``MKDAn`` for the
main team (mapped to ``MKD`` by `BMO_CODE_MAPPING`) and ``MKDBn`` for the B
team (a recognised B-team code). Other codes (``ROU``, ``ITA``, ``GRE``,
``BUL``, ``MDA``, ``MNE``, ``BIH``, ``TKM``, ``CYP``, ``UNK``, ``SAU``,
``AZE``, ``ALB``, ``TUR``, ``KAZ``, ``KGZ``, ``KTA``) pass straight through
`canonical_team_code`.

Per-country name order inferred from the data evidence:

  - Surname-Given (flipped): GRE, KAZ, KGZ, MDA
  - Given-Surname: every other delegation, including ROU, ITA, BUL, TKM,
    MNE, BIH, CYP, UNK, SAU, AZE, ALB, TUR, KTA

(`country_base` returns the raw letter prefix -- ``GRE`` here, not the
ISO-normalised ``HEL``/``GRC`` -- so the set keys on the code as it
appears in the HTML.)

Rows with an empty Total and empty score cells (listed at the very bottom
for a few absent KGZ contestants) are skipped.
"""

from pathlib import Path

from bs4 import BeautifulSoup

from ..models import ContestantResult
from .base import BaseParser
from .code_utils import canonical_team_code, country_base, split_name
from .pdf_common import normalize_award, parse_int, parse_score

_SURNAME_FIRST_COUNTRIES = {"GRE", "KAZ", "KGZ", "MDA"}


class Parser2017(BaseParser):
    """Parser for BMO 2017 (HTML ranking from the Macedonian organiser)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        # Always read the total-sorted results file from the same directory,
        # in case the caller passed the secondary ``results-code.html`` or the
        # scanned PDF.
        html_path = raw_file
        if html_path.name != "results-total.html":
            candidate = raw_file.parent / "results-total.html"
            if candidate.exists():
                html_path = candidate

        html = html_path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        results: list[ContestantResult] = []
        seen: set[tuple[str, str]] = set()

        for row in soup.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
            if len(cells) < 9:
                continue

            raw_name = cells[1].strip()
            code = cells[2].strip()
            if not raw_name or not code:
                continue

            problem_scores = [parse_score(cells[3 + i]) for i in range(4)]
            total = parse_int(cells[7])
            # Skip contestants listed without any score (empty Total and
            # empty problem cells -- absentees at the bottom of the table).
            if total is None and all(s is None for s in problem_scores):
                continue
            if total is None:
                total = sum(s for s in problem_scores if s is not None)

            canonical = canonical_team_code(code)
            name, given_name, family_name = split_name(
                raw_name,
                surname_first=country_base(canonical) in _SURNAME_FIRST_COUNTRIES,
            )

            award = normalize_award(cells[8]) if len(cells) > 8 else None

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
                    rank=None,
                    award=award,
                    given_name=given_name,
                    family_name=family_name,
                )
            )

        self.compute_ranks(results)
        return results
