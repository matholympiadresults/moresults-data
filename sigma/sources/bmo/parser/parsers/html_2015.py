"""Parser for BMO 2015 results (HTML snapshot from the Athens organiser).

The 2015 bulletin is a multi-file HTML dump. Per-country score tables live
in ``sg<country>.htm`` files with columns:

  ID | Student | Prob.1 | Prob.2 | Prob.3 | Prob.4 | Total

The ``Student`` column is a bare team code like ``ALB1``..``ALB6`` -- there
are **no contestant names** in the score tables. The companion
``team<country>.htm`` files list the delegation with Leader / Deputy Leader
/ Contestants as a ``<ul><li>`` of names. We merge the two by country,
assuming the i-th ``<li>`` contestant corresponds to the i-th score row
(both are printed in ID order).

Medals are not shown per contestant. We recover them from the four tier
aggregate files (``gold.htm`` / ``silver.htm`` / ``bronze.htm`` /
``mentions.htm``) which list the codes in each tier. A handful of
contestants are missing from every tier despite having a medal-worthy
score (e.g. TKM6 Ruslan Myratgeldiyev scored 33 but isn't listed
anywhere) — for those we fall back to threshold-based assignment using
the cutoffs derived from the lowest score in each tier.

Code quirks handled:

  - ``HEL(b)`` (Greece's second guest team) becomes ``HELB`` so the
    ingester treats it as a B-team. The caller adds ``helb -> grc`` to
    ``BMO_CODE_MAPPING`` and ``helb`` to ``B_TEAM_CODES``.
  - ``UK-IRE`` (the combined UK+Ireland guest squad) becomes ``UNKIRL``,
    which the ingester already maps to ``gbr`` (see the 2008 squad).

sg -> team filename mapping (the prefixes don't always line up):

  sgalb -> teamalb         sgbih -> teamboz
  sgbul -> teambul         sgazb -> teamazer
  sgcyp -> teamcyp         sgirn -> teamiran
  sgfrm -> teamfyr         sgita -> teamita
  sghel -> teamhel         sgkaz -> teamkaz
  sghelb -> teamhelb       sgkgz -> teamkyrg
  sgmld -> teammld         sgsau -> teamsaudi
  sgmng -> teammont        sgtaz -> teamtaji
  sgrom -> teamrom         sgtrm -> teamtrm
  sgscg -> teamscg         sgunk -> teamuk
  sgtur -> teamtur

Per-country name order inferred from the data evidence (contestant list in
each team file):

  - Surname-Given (flipped): CYP, HEL, HELB, ITA, ROU
  - Given-Surname: every other delegation

(``country_base`` returns the raw letter prefix -- ``ROU`` here, not
``ROM``, because canonical_team_code turns ``ROMn`` into ``ROMn`` and
country_base strips the digit to ``ROM``. In 2015 the raw prefix is
``ROM`` (via ``sgrom.htm`` -> ``ROUn`` actually -- inspect: rows use
``ROU1``, so the prefix is ROU). So the key is ``ROU``.)
"""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

from ..models import ContestantResult
from .base import BaseParser
from .code_utils import canonical_team_code, country_base, split_name
from .pdf_common import normalize_award, parse_int, parse_score

_SURNAME_FIRST_COUNTRIES = {"CYP", "HEL", "HELB", "ITA", "ROU"}

# sg<key> -> team<other> where the team filename stem differs.
_SG_TO_TEAM_STEM: dict[str, str] = {
    "alb": "alb",
    "bih": "boz",
    "bul": "bul",
    "cyp": "cyp",
    "frm": "fyr",
    "hel": "hel",
    "helb": "helb",
    "mld": "mld",
    "mng": "mont",
    "rom": "rom",
    "scg": "scg",
    "tur": "tur",
    "azb": "azer",
    "irn": "iran",
    "ita": "ita",
    "kaz": "kaz",
    "kgz": "kyrg",
    "sau": "saudi",
    "taz": "taji",
    "trm": "trm",
    "unk": "uk",
}

# "HEL(b)5" -> "HELB5"; strip parens around a single B / A marker.
_PAREN_B_RE = re.compile(r"\(\s*([AaBb])\s*\)")

_AWARD_FILES = {
    "Gold": "gold.htm",
    "Silver": "silver.htm",
    "Bronze": "bronze.htm",
    "Honourable Mention": "mentions.htm",
}


def _preclean_code(raw: str) -> str:
    """Normalise code quirks before canonical_team_code.

    - ``HEL(b)1`` -> ``HELB1`` (strip parens around the B marker).
    - ``UK-IRE3`` / ``UNK-IRE3`` -> ``UNKIRL3`` (rename the combined UK+
      Ireland squad to the 2008-era form the ingester already knows).
    """
    s = raw.strip()
    s = _PAREN_B_RE.sub(lambda m: m.group(1).upper(), s)
    s = re.sub(r"^UNK-IRE", "UNKIRL", s, flags=re.IGNORECASE)
    s = re.sub(r"^UK-IRE", "UNKIRL", s, flags=re.IGNORECASE)
    return s


def _parse_score_table(path: Path) -> list[tuple[str, list[int | None], int]]:
    """Read an ``sg<country>.htm`` scores table.

    Returns a list of ``(canonical_code, [P1..P4], total)`` tuples, one per
    contestant row, in the order they appear in the HTML.
    """
    html = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")

    out: list[tuple[str, list[int | None], int]] = []
    for row in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
        # Expect 7 cells: ID, Student, P1..P4, Total
        if len(cells) < 7:
            continue
        id_cell = cells[0].strip()
        code_cell = cells[1].strip()
        # Skip header and non-data rows.
        if not id_cell.isdigit():
            continue
        if not code_cell:
            continue
        # Skip rows with all-dash scores (e.g. SAU2 marked "-").
        problem_scores = [parse_score(cells[2 + i]) for i in range(4)]
        total = parse_int(cells[6])
        if total is None and all(s is None for s in problem_scores):
            # Absentee -- no data to record.
            continue
        if total is None:
            total = sum(s for s in problem_scores if s is not None)
        canonical = canonical_team_code(_preclean_code(code_cell))
        out.append((canonical, problem_scores, total))
    return out


def _parse_team_roster(path: Path) -> list[str]:
    """Extract the contestants listed under Leader / Deputy Leader / Contestant.

    Returns a list of raw names in document order. The team files use
    unclosed ``<li>`` tags which the stdlib ``html.parser`` nests
    recursively, so we pull each ``<li>``'s *direct* text only (stopping
    at the next nested ``<li>``) rather than calling ``get_text`` on the
    whole subtree.
    """
    html = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")

    names: list[str] = []
    list_tag = soup.find(["ul", "ol"])
    if list_tag is None:
        return names
    for li in list_tag.find_all("li"):
        parts: list[str] = []
        for child in li.children:
            if isinstance(child, NavigableString):
                parts.append(str(child))
            elif getattr(child, "name", None) == "li":
                break
            else:
                parts.append(child.get_text(" ", strip=False))
        text = " ".join(parts)
        # Collapse runs of whitespace (some entries use tabs between given/family).
        text = re.sub(r"\s+", " ", text).strip()
        # Trim trailing separators like ';' that sneak in (e.g. BGR roster).
        text = text.rstrip(";,").strip()
        if text:
            names.append(text)
    return names


def _iter_award_rows(
    dir_path: Path,
) -> list[tuple[str, str, int | None]]:
    """Yield ``(award, raw_code, total)`` tuples from the four tier tables.

    Iteration order is gold -> silver -> bronze -> mentions so the highest
    tier wins if a code somehow appears twice.
    """
    out: list[tuple[str, str, int | None]] = []
    for award, fname in _AWARD_FILES.items():
        path = dir_path / fname
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        for row in soup.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
            if len(cells) < 6:
                continue
            # The Student cell is at index 1 when there's a rank, else 0.
            if len(cells) == 6:
                code_cell = cells[0]
                total_cell = cells[5] if len(cells) > 5 else ""
            else:
                code_cell = cells[1]
                total_cell = cells[6] if len(cells) > 6 else ""
            code = code_cell.strip()
            if not code or code.lower() in {"student", "grading of students"}:
                continue
            out.append((award, code, parse_int(total_cell.strip())))
    return out


def _load_award_lookup(
    dir_path: Path,
    code_totals: dict[str, int],
) -> tuple[dict[str, str], dict[str, int]]:
    """Map each contestant code to its award, and derive per-tier cutoffs.

    Some tier tables contain a stray row where the organiser forgot the
    contestant number (e.g. ``MDA`` instead of ``MDA4`` in ``gold.htm``).
    For those we fall back to matching the aggregate-row total against
    ``code_totals`` (the per-code totals from the score tables) within the
    same country prefix.

    Returns ``(code -> award, award -> min_total_in_tier)``. The cutoff
    dict is used by the caller to backfill awards for contestants the
    source forgot to list in any tier.
    """
    lookup: dict[str, str] = {}
    tier_min: dict[str, int] = {}
    for award, code, total in _iter_award_rows(dir_path):
        normalised = normalize_award(award) or award
        if total is not None:
            prev = tier_min.get(normalised)
            if prev is None or total < prev:
                tier_min[normalised] = total
        canonical = canonical_team_code(_preclean_code(code))
        if re.match(r"^[A-Z]+\d+$", canonical):
            lookup.setdefault(canonical, normalised)
            continue
        # Unnumbered code -- e.g. bare "MDA". Resolve by country + total.
        prefix = re.match(r"^[A-Z]+$", canonical)
        if prefix and total is not None:
            # Match to any <prefix>N whose total equals this row's total and
            # that isn't already awarded a higher tier.
            for c_code, c_total in code_totals.items():
                if c_code.startswith(canonical) and c_total == total and c_code not in lookup:
                    lookup[c_code] = normalised
                    break
    return lookup, tier_min


def _threshold_award(total: int, tier_min: dict[str, int]) -> str | None:
    """Assign an award from the score thresholds derived from the tier files.

    Used only as a fallback when the per-code lookup doesn't resolve a
    medal — i.e. the source dropped the contestant from every tier page
    despite a medal-worthy score.
    """
    for award in ("Gold", "Silver", "Bronze", "Honourable Mention"):
        cutoff = tier_min.get(award)
        if cutoff is not None and total >= cutoff:
            return award
    return None


class Parser2015(BaseParser):
    """Parser for BMO 2015 (HTML multi-file dump from the Athens organiser)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        dir_path = raw_file.parent

        # Pre-read every score table so we know each code's total. The
        # aggregate medal tables have a stray unnumbered code
        # (``gold.htm`` lists ``MDA`` rather than ``MDA4``) that we need
        # to resolve by matching totals.
        score_tables: dict[Path, list[tuple[str, list[int | None], int]]] = {}
        code_totals: dict[str, int] = {}
        for sg_path in sorted(dir_path.glob("sg*.htm")):
            rows = _parse_score_table(sg_path)
            if rows:
                score_tables[sg_path] = rows
                for canonical, _problem_scores, total in rows:
                    code_totals[canonical] = total

        award_lookup, tier_min = _load_award_lookup(dir_path, code_totals)

        results: list[ContestantResult] = []
        seen: set[tuple[str, str]] = set()

        # Iterate every per-country score file in the directory so the
        # caller's primary-file choice doesn't matter.
        for sg_path, rows in sorted(score_tables.items()):
            stem = sg_path.stem  # e.g. "sgalb"
            country_key = stem[2:]  # strip "sg"
            team_stem = _SG_TO_TEAM_STEM.get(country_key, country_key)
            team_path = dir_path / f"team{team_stem}.htm"

            names = _parse_team_roster(team_path) if team_path.exists() else []

            for canonical, problem_scores, total in rows:
                # Align the team roster by the trailing digit in the code:
                # absentees (all-dash rows) are skipped above, which shifts
                # plain enumerate indices when a country has one. Using the
                # ``<prefix>N`` index keeps everyone paired with the right
                # ``<li>`` in the team file. Fall back to the score-row
                # position when the code has no digit (shouldn't happen).
                idx_match = re.search(r"(\d+)$", canonical)
                idx = int(idx_match.group(1)) - 1 if idx_match else None
                if idx is not None and 0 <= idx < len(names):
                    raw_name = names[idx]
                else:
                    # Fall back to the code when the roster is missing or
                    # shorter than the score table.
                    raw_name = canonical

                name, given_name, family_name = split_name(
                    raw_name,
                    surname_first=country_base(canonical) in _SURNAME_FIRST_COUNTRIES,
                )

                key = (name, canonical)
                if key in seen:
                    continue
                seen.add(key)

                award = award_lookup.get(canonical) or _threshold_award(total, tier_min)

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
