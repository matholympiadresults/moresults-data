"""Parser for JBMO 2026 results from HTML.

Source: https://jbmo2026.ssmr.ro/results-individual/
Ninja Tables embed with columns:
    id, Name, Country, Code, P1, P2, P3, P4, official_team, Total, Medal.

The ``Total`` column (Ninja Tables internal name ``display``) does not
hold the score sum on this page — it carries an unrelated 1-4 value —
so the total is recomputed from the four problem scores. The hidden
``official_team`` column is also ignored: it is 1 for Balkan member
teams and 0 for guest delegations (including Romania B as ``ROUB``),
which is not information we preserve at the contestant level.

Names are uppercased in the source (``BALTOV STOYAN``) in family-first
order. They are title-cased and reordered to Western form
(``Stoyan Baltov``) for storage.
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup

from ..models import ContestantResult
from .base import BaseParser


def _title_case(token: str) -> str:
    """Title-case a single word while keeping interior hyphens/apostrophes proper.

    "BALTOV"           -> "Baltov"
    "ETILE-ZEPHORIS"   -> "Etile-Zephoris"
    "O'CONNOR"         -> "O'Connor"
    """
    parts = re.split(r"([-'])", token)
    return "".join(p.capitalize() if i % 2 == 0 else p for i, p in enumerate(parts))


# A handful of source rows the page lists in non-standard order. Maps the
# raw upper-case label to (full_name, given_name, family_name) in Western
# order, title-cased.
#
# The Romanian/Bulgarian/etc. delegations submit ``FAMILY GIVEN`` so the
# default reorder rule is correct for them. Malaysia's roster is the
# exception: the team submits names with a two-word family-equivalent
# (``MOHD <FATHER>``) FIRST and the personal name(s) after, and the
# Chinese-Malaysian rows are likewise listed family-first with the family
# name at the END. Each MAS row is overridden explicitly to land on the
# same canonical form used in JBMO 2025.
_NAME_ORDER_OVERRIDES: dict[str, tuple[str, str, str]] = {
    "TIAN YOU ALEXANDER CHEW": ("Tian You Alexander Chew", "Tian You Alexander", "Chew"),
    "TIAN HONG BENJAMIN CHEW": ("Tian Hong Benjamin Chew", "Tian Hong Benjamin", "Chew"),
    "LAI JOE HERN": ("Joe Hern Lai", "Joe Hern", "Lai"),
    "MOHD AFIZ MUHAMMAD ARIF HAIKAL": (
        "Muhammad Arif Haikal Mohd Afiz",
        "Muhammad Arif Haikal",
        "Mohd Afiz",
    ),
    "MOHD REDZUAN AISH FAHEEMY": (
        "Aish Faheemy Mohd Redzuan",
        "Aish Faheemy",
        "Mohd Redzuan",
    ),
    "MOHD IRWAN IZZ ZULQARNAIN": (
        "Irwan Izz Zulqarnain Mohd",
        "Irwan Izz Zulqarnain",
        "Mohd",
    ),
}


def _split_name(raw_name: str) -> tuple[str, str, str]:
    """Convert a source label like 'BALTOV STOYAN' to Western order.

    The source lists names family-first in upper case. The first token is
    treated as the family name and the remainder as the given name(s),
    matching the layout used by the other Romanian-hosted JBMO pages.
    """
    if raw_name in _NAME_ORDER_OVERRIDES:
        return _NAME_ORDER_OVERRIDES[raw_name]

    tokens = raw_name.split()
    if len(tokens) < 2:
        full = _title_case(raw_name)
        return full, "", full

    family = _title_case(tokens[0])
    given = " ".join(_title_case(t) for t in tokens[1:])
    full = f"{given} {family}"
    return full, given, family


def _parse_score(text: str) -> int | None:
    try:
        return int(text.strip())
    except (ValueError, TypeError):
        return None


class Parser2026(BaseParser):
    """Parser for JBMO 2026 (HTML Ninja Tables embed from jbmo2026.ssmr.ro)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        html = raw_file.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        # The page contains a single Ninja Tables results table.
        table = soup.find("table", attrs={"data-ninja_table_instance": True})
        if not table:
            raise ValueError(f"Could not find Ninja Tables results table for JBMO {self.year}")

        results: list[ContestantResult] = []

        body = table.find("tbody") or table
        for row in body.find_all("tr"):
            cells = row.find_all("td")
            # Expected columns: id, name, country, code, p1, p2, p3, p4,
            # official_team, display, medal
            if len(cells) != 11:
                continue

            raw_name = cells[1].get_text(strip=True)
            country = cells[2].get_text(strip=True)
            if not raw_name or not country:
                continue

            problem_scores = [_parse_score(cells[4 + i].get_text(strip=True)) for i in range(4)]
            total = sum(s for s in problem_scores if s is not None)

            award_text = cells[10].get_text(strip=True)
            # The source uses "-" for no medal.
            award = self.normalize_award(award_text) if award_text and award_text != "-" else None

            full_name, given_name, family_name = _split_name(raw_name)

            results.append(
                ContestantResult(
                    name=full_name,
                    country=country,
                    problem_scores=problem_scores,
                    total=total,
                    rank=None,
                    award=award,
                    given_name=given_name or None,
                    family_name=family_name or None,
                )
            )

        self.compute_ranks(results)
        return results
