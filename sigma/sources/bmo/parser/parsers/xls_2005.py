"""Parser for BMO 2005 results from a bundled Excel spreadsheet.

The workbook's 'general results' sheet lists every contestant in a single
flat table with columns: TIP | COD | NAME | P1 | P2 | P3 | P4 | TOTAL | Medal.
TIP is 'P' for Participating (official) or 'I' for Invited guest teams.

Names are printed in ALL CAPS with per-country ordering:
  - Surname-Given: CYP, MDA, ROM (both squads), SCG
  - Given-Surname: everyone else

For the surname-first set we flip tokens into "Given Surname" so contestants
match their IMO records in the same year. Particles like "von" / "al" are
absorbed into the family name (no such cases in 2005, but the shared helper
handles them).

Romania fielded two squads that year: ``ROM1..ROM6`` (participating / main)
and ``ROM1A..ROM6A`` (invited / secondary). The trailing 'A' marker is
normalised here — ``ROMnA`` becomes ``ROMBn`` so the ingester recognises
them as the B-team.
"""

import re
from pathlib import Path

from ..models import ContestantResult
from .base import BaseParser
from .code_utils import canonical_team_code, country_base, split_name
from .pdf_common import normalize_award, parse_int, parse_score

_SURNAME_FIRST_COUNTRIES = {"CYP", "MDA", "ROM", "SCG"}


class Parser2005(BaseParser):
    """Parser for BMO 2005 (.xls, single sheet with all contestants)."""

    SHEET_NAME = "general results"

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        import xlrd

        book = xlrd.open_workbook(str(raw_file))
        sheet = book.sheet_by_name(self.SHEET_NAME)

        results: list[ContestantResult] = []
        for row_idx in range(1, sheet.nrows):  # skip header
            row = [sheet.cell_value(row_idx, col) for col in range(sheet.ncols)]
            if len(row) < 9:
                continue

            code = str(row[1]).strip()
            raw_name = str(row[2]).strip()
            if not code or not raw_name:
                continue

            canonical = canonical_team_code(_apply_2005_quirks(code))
            name, given_name, family_name = split_name(
                raw_name,
                surname_first=country_base(canonical) in _SURNAME_FIRST_COUNTRIES,
            )

            problem_scores = [parse_score(_fmt(row[3 + i])) for i in range(4)]

            total = parse_int(_fmt(row[7]))
            if total is None:
                total = sum(s for s in problem_scores if s is not None)

            medal_text = str(row[8]) if len(row) > 8 else ""

            results.append(
                ContestantResult(
                    name=name,
                    country=canonical,
                    problem_scores=problem_scores,
                    total=total,
                    rank=None,
                    award=normalize_award(medal_text),
                    given_name=given_name,
                    family_name=family_name,
                )
            )

        self.compute_ranks(results)
        return results


_ROM_INVITED_RE = re.compile(r"^([A-Za-z]+)(\d+)A$")


def _apply_2005_quirks(code: str) -> str:
    """Flip 2005-specific trailing-'A' invited-team codes to B-team form."""
    m = _ROM_INVITED_RE.match(code.strip())
    if m:
        return f"{m.group(1)}B{m.group(2)}"
    return code


def _fmt(value) -> str:
    """Format an xlrd cell value for the int/score helpers."""
    if value == "" or value is None:
        return ""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)
    return str(value).strip()
