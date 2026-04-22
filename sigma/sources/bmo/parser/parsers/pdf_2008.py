"""Parser for BMO 2008 results (PDF bulletin from matematickitalent.mk).

The 45-page bulletin ends with a "Complete results of BMO 2008" ranking table
on pages 42–44 with columns:

  Rank | Code | Contestant | P1 | P2 | P3 | P4 | Total | Medal

Medals are printed lowercase (``gold`` / ``silver`` / ``bronze`` / blank).

Names are mostly Given-Surname but CYP, MDA (and the occasional Kazakh
entry) are printed Surname-Given. We flip those so IMO-era records match.

Macedonia hosted and fielded two squads, spelled ``MKDnA`` (main) and
``MKDnB`` (secondary). The trailing ``A`` is dropped for the main squad;
``MKDnB`` becomes ``MKDBn`` so the ingester flags it as a B-team. ``UNK&IRL``
(the 2008 UK+Ireland combined squad) is normalised to ``UNKIRL`` by
`canonical_team_code`.
"""

import re
from pathlib import Path

from ..models import ContestantResult
from .base import BaseParser
from .code_utils import canonical_team_code, country_base, split_name
from .pdf_common import iter_pdf_rows, normalize_award, parse_int, parse_score

_SURNAME_FIRST_COUNTRIES = {"CYP", "MDA"}

_TRAIL_AB_RE = re.compile(r"^([A-Za-z&]+)(\d+)([AB])$")


class Parser2008(BaseParser):
    """Parser for BMO 2008 (PDF scorecard at the end of the bulletin)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        results: list[ContestantResult] = []
        seen: set[tuple[str, str]] = set()

        for row in iter_pdf_rows(raw_file):
            # The bulletin has per-country roster tables (3 cols) earlier; the
            # complete ranking rows are 9-column with a numeric rank first.
            if len(row) < 9 or not row[0].strip().isdigit():
                continue

            code = row[1].strip()
            raw_name = row[2].strip()
            if not code or not raw_name:
                continue

            canonical = canonical_team_code(_apply_ab_marker(code))
            name, given_name, family_name = split_name(
                raw_name,
                surname_first=country_base(canonical) in _SURNAME_FIRST_COUNTRIES,
            )

            problem_scores = [parse_score(row[3 + i]) for i in range(4)]

            total = parse_int(row[7])
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
                    rank=parse_int(row[0]),
                    award=normalize_award(row[8]) if len(row) > 8 else None,
                    given_name=given_name,
                    family_name=family_name,
                )
            )

        self.compute_ranks(results)
        return results


def _apply_ab_marker(code: str) -> str:
    """Normalise trailing ``A``/``B`` host-team markers.

    ``MKD1A..MKD6A`` → ``MKD1..MKD6`` (main squad: A dropped).
    ``MKD1B..MKD6B`` → ``MKDB1..MKDB6`` (B-team marker flipped ahead of the
    contestant number so the ingester recognises it as a secondary team).
    """
    m = _TRAIL_AB_RE.match(code.strip())
    if not m:
        return code
    base, num, letter = m.group(1), m.group(2), m.group(3)
    if letter.upper() == "A":
        return f"{base}{num}"
    return f"{base}B{num}"
