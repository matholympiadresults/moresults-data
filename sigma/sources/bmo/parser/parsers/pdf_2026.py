"""Parser for BMO 2026 results.

Source publishes scores only as a code-keyed PDF
(``BMO2026_all_countries_contestant.pdf``) with columns:

    Rank | Code | P1 | P2 | P3 | P4 | Sum | Award

The PDF never names the contestants — each row identifies them by a code
like ``LTU1`` / ``HELB3``. We recover names by scraping each delegation's
team-page HTML (``team<Country>.html``), reading the ``<li>`` items in the
*Contestant* row only, and assuming the i-th contestant in that list
corresponds to ``<COUNTRY><i>`` in the scores PDF.
"""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

from ..models import ContestantResult
from .base import BaseParser
from .code_utils import canonical_team_code, split_name
from .pdf_common import (
    iter_pdf_rows,
    normalize_award,
    parse_int,
    parse_score,
)

# Country prefix in the scores PDF -> team-roster filename in the raw dir.
# HELB (Greece B / "Hellas Guest") has its own page; other delegations are
# either Member countries or a single Guest team.
_TEAM_FILES: dict[str, str] = {
    "ALB": "teamAlbania.html",
    "BIH": "teamBosnia.html",
    "BUL": "teamBulgaria.html",
    "CYP": "teamCyprus.html",
    "HEL": "teamHellas.html",
    "MDA": "teamMoldova.html",
    "MNE": "teamMontenegro.html",
    "MKD": "teamNorth_Macedonia.html",
    "ROU": "teamRomania.html",
    "SRB": "teamserbia.html",
    "TUR": "teamTurkey.html",
    "ALG": "teamalgeria.html",
    "AZE": "teamazerbaijan.html",
    "GEO": "teamGeorgia.html",
    "FRA": "teamfrance.html",
    "HELB": "teamHellasGest.html",
    "ITA": "teamitalia.html",
    "KAZ": "teamkazakstan.html",
    "KGZ": "teamKyrgyzstan.html",
    "LTU": "teamLithuania.html",
    "MAS": "teamMalaysia.html",
    "SAU": "teamSaudi_Arabia.html",
    "TKM": "teamTurkmenistan.html",
    "GBR": "teamUnited_Kingdom.html",
    "UZB": "teamUzbekistan.html",
}

# Every 2026 delegation prints contestants in Given-Surname order.
_SURNAME_FIRST_COUNTRIES: set[str] = set()


def _parse_team_roster(path: Path) -> list[str]:
    """Return the contestants listed under the *Contestant* row of a team page.

    The roster table on each ``team<Country>.html`` page has rows for
    Leader, Deputy Leader, optional Observer(s), and Contestant. We want
    only the Contestant row's ``<li>`` items, so we walk the table rows
    and take the ``<td>`` next to the first row whose label is
    ``Contestant``.
    """
    if not path.exists():
        return []
    html = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("table", attrs={"border": "1"})
    if table is None:
        return []

    # The 2026 pages aren't always well-formed: at least one
    # (``teamKyrgyzstan.html``) puts the *Contestant* ``<td>`` outside
    # any ``<tr>``, so iterating ``<tr>`` rows misses it. Walking every
    # ``<td>`` directly avoids that and still works for the regular pages.
    cells = table.find_all(["td", "th"])
    contestant_cell = None
    for idx, cell in enumerate(cells):
        label = cell.get_text(" ", strip=True).lower()
        if label == "contestant" and idx + 1 < len(cells):
            contestant_cell = cells[idx + 1]
            break

    if contestant_cell is None:
        return []

    names: list[str] = []
    for li in contestant_cell.find_all("li"):
        text = re.sub(r"\s+", " ", li.get_text(" ", strip=False)).strip()
        if text:
            names.append(text)
    return names


# Strip a trailing contestant number from a canonical code (e.g. ``ALB5``
# → ``ALB``, ``HELB3`` → ``HELB``). We can't reuse ``country_base`` from
# code_utils because it also strips a B-team marker, which clobbers
# legitimate ISO codes ending in B (``ALB``, ``SRB``).
_PREFIX_RE = re.compile(r"^([A-Z]+?)(\d+)?$")


def _team_prefix(canonical: str) -> str:
    m = _PREFIX_RE.match(canonical)
    return m.group(1) if m else canonical


def _parse_score_rows(raw_file: Path) -> list[tuple[str, list[int | None], int, str | None]]:
    """Pull the (code, problem_scores, total, award) tuples from the scores PDF."""
    rows: list[tuple[str, list[int | None], int, str | None]] = []
    for row in iter_pdf_rows(raw_file):
        if len(row) < 7:
            continue
        rank_cell, code_cell = row[0].strip(), row[1].strip()
        if not rank_cell.isdigit() or not code_cell:
            continue
        # The PDF also contains a country-summary table whose code cells
        # have no contestant number (e.g. ``TUR``, ``UZB``); skip those.
        if not re.search(r"\d$", code_cell):
            continue
        problem_scores = [parse_score(row[2 + i]) for i in range(4)]
        total = parse_int(row[6])
        if total is None:
            total = sum(s for s in problem_scores if s is not None)
        award_cell = row[7].strip() if len(row) > 7 else ""
        award = normalize_award(award_cell) if award_cell else None
        rows.append((code_cell, problem_scores, total, award))
    return rows


class Parser2026(BaseParser):
    """Parser for BMO 2026 (PDF scores + per-country team-page rosters)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        dir_path = raw_file.parent

        rosters: dict[str, list[str]] = {
            prefix: _parse_team_roster(dir_path / fname) for prefix, fname in _TEAM_FILES.items()
        }

        results: list[ContestantResult] = []
        seen: set[tuple[str, str]] = set()

        for raw_code, problem_scores, total, award in _parse_score_rows(raw_file):
            canonical = canonical_team_code(raw_code)
            prefix = _team_prefix(canonical)

            idx_match = re.search(r"(\d+)$", canonical)
            idx = int(idx_match.group(1)) - 1 if idx_match else None

            roster = rosters.get(prefix, [])
            if idx is not None and 0 <= idx < len(roster):
                raw_name = roster[idx]
            else:
                raw_name = canonical

            name, given_name, family_name = split_name(
                raw_name,
                surname_first=prefix in _SURNAME_FIRST_COUNTRIES,
            )

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
