"""Parser for BMO 2011 results from bmo-2011.info (Iași, Romania).

The single ``results.html`` holds one table row per entry in this order:

  Name | Country-Code | Role | P1 | P2 | P3 | P4 | Total | Medal

The "Role" column tells "Contestant" vs. other (we only keep contestants).
Romania hosts two official squads: "ROM A1..A6" is the main team and
"ROM B1..B6" is the invited/secondary team. Codes are normalised via
`canonical_team_code` so that ``ROM A1`` → ``ROM1`` (main) and ``ROM B1`` →
``ROMB1`` (B-team, flagged by the ingester).

Names are mostly Given-Surname but CYP (in ALL CAPS surname-first), HEL,
KAZ, MDA, and ROM (both squads) are printed Surname-Given. We flip those
so IMO cross-edition matching works. Cyprus entries also have the
surname word uppercased; we title-case it before splitting.
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup

from ..models import ContestantResult
from .base import BaseParser
from .code_utils import canonical_team_code, country_base, split_name
from .pdf_common import normalize_award, parse_int, parse_score

_SURNAME_FIRST_COUNTRIES = {"CYP", "HEL", "KAZ", "MDA", "ROM"}

# Words written in ALL-CAPS that capitalize_name() preserves because the full
# string is mixed-case. Title-case them explicitly before splitting.
_ALLCAPS_WORD_RE = re.compile(r"\b[A-ZÄÖÜÇĞİŞÆØÅÁÉÍÓÚÑŞŚŞŻÖÜÇĞ]{3,}\b")


class Parser2011(BaseParser):
    """Parser for BMO 2011 (HTML snapshot from bmo-2011.info)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        html = raw_file.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        results: list[ContestantResult] = []
        seen: set[tuple[str, str]] = set()

        for row in soup.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
            if len(cells) < 9:
                continue

            raw_name = cells[0].strip()
            code = cells[1].strip()
            role = cells[2].strip().lower()
            if role and role != "contestant":
                # Skip leaders / deputies / observers (a couple appear in the table).
                continue
            if not raw_name or not code:
                continue
            # Rows like "Name" / "Country" are the header repeated; skip them.
            if raw_name.lower() == "name" and code.lower() == "country":
                continue

            canonical = canonical_team_code(code)
            normalised_name = _ALLCAPS_WORD_RE.sub(lambda m: m.group(0).capitalize(), raw_name)
            name, given_name, family_name = split_name(
                normalised_name,
                surname_first=country_base(canonical) in _SURNAME_FIRST_COUNTRIES,
            )

            problem_scores = [parse_score(cells[3 + i]) for i in range(4)]

            total = parse_int(cells[7])
            if total is None:
                total = sum(s for s in problem_scores if s is not None)

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
