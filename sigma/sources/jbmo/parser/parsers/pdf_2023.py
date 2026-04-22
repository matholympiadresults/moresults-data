"""Parser for JBMO 2023 results (two PDFs + team HTML pages).

JBMO 2023 was held in Tirana, Albania. The results are split across:

1. ``jbmo_2023_overall.pdf`` -- all 114 contestants with scores but NO names.
   Header: ID | Country | Code | Official | P1 | P2 | P3 | P4 | Total

2. ``jbmo_2023_medals.pdf`` -- 80 medalists WITH names and medal info.
   Header: ID | Country | Name | Code | Official | P1 | P2 | P3 | P4 | Total | Medal

3. ``jbmo_2023_team_*.html`` -- per-country team pages with contestant names
   for non-medalists too.

Names come from team pages first, then medals PDF, then fall back to codes.
Scores and awards come from the overall PDF and medals PDF respectively.
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup

from ..models import ContestantResult
from .base import BaseParser


def _iter_pdf_rows(raw_file: Path):
    """Yield all table rows from the PDF as lists of stripped strings."""
    import pdfplumber

    with pdfplumber.open(raw_file) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table:
                    continue
                for row in table:
                    if row is None:
                        continue
                    yield [str(cell).strip() if cell else "" for cell in row]


def _is_header_row(row: list[str]) -> bool:
    """Return True for header rows that should be skipped."""
    text = " ".join(row).lower()
    return "country" in text and ("code" in text or "id" in text)


def _parse_int(value: str) -> int | None:
    """Parse an integer, returning None on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _parse_score(value: str) -> int | None:
    """Parse a problem score in [0, 10], returning None if out of range or invalid."""
    score = _parse_int(value)
    if score is None or score < 0 or score > 10:
        return None
    return score


def _normalize_award(award: str | None) -> str | None:
    """Normalize award text to standard format."""
    if not award:
        return None
    award_lower = award.lower().strip()
    if "gold" in award_lower:
        return "Gold"
    if "silver" in award_lower:
        return "Silver"
    if "bronze" in award_lower:
        return "Bronze"
    if "honourable" in award_lower or "honorable" in award_lower or "hm" in award_lower:
        return "Honourable Mention"
    return award if award else None


def _normalize_country(raw: str) -> str:
    """Normalize a country name by collapsing newlines and extra whitespace."""
    return re.sub(r"\s+", " ", raw.replace("\n", " ")).strip()


def _split_name(full_name: str) -> tuple[str | None, str | None]:
    """Split a 'Given Surname' name into (given_name, family_name).

    Names in the medals PDF are already in Given Surname order.
    The last token is treated as the family name.
    """
    tokens = full_name.strip().split()
    if len(tokens) < 2:
        return None, None
    return " ".join(tokens[:-1]), tokens[-1]


# ------------------------------------------------------------------
# Medals PDF column indices
# ID | Country | Name | Code | Official | P1 | P2 | P3 | P4 | Total | Medal
# ------------------------------------------------------------------
MED_IDX_CODE = 3
MED_IDX_NAME = 2
MED_IDX_MEDAL = 10
MED_MIN_COLS = 11

# ------------------------------------------------------------------
# Overall PDF column indices
# ID | Country | Code | Official | P1 | P2 | P3 | P4 | Total
# ------------------------------------------------------------------
OVR_IDX_COUNTRY = 1
OVR_IDX_CODE = 2
OVR_IDX_P1 = 4
OVR_IDX_TOTAL = 8
OVR_MIN_COLS = 9


def _parse_team_pages(directory: Path) -> dict[str, str]:
    """Parse team HTML pages and build a mapping of Code -> name.

    The team pages have a column-by-column layout: all codes listed, then all
    names, then P1 values, etc.  We extract Code->Name pairs.

    Returns:
        Dict mapping contestant code (e.g. "ALB 1") to full name.
    """
    code_to_name: dict[str, str] = {}

    for html_file in sorted(directory.glob("jbmo_2023_team_*.html")):
        try:
            html = html_file.read_text(encoding="utf-8")
        except Exception:
            continue

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # Find "Contestants" section, then extract Code and Name columns
        try:
            contestants_idx = lines.index("Contestants")
        except ValueError:
            continue

        # After "Contestants", expect: "Code", 6 codes, "Name", 6 names, ...
        after = lines[contestants_idx + 1 :]

        # Find Code section
        try:
            code_start = after.index("Code") + 1
        except ValueError:
            continue

        # Find Name section
        try:
            name_start = after.index("Name") + 1
        except ValueError:
            continue

        # Codes are between "Code" and "Name"
        codes = after[code_start : name_start - 1]

        # Find P1 to know where names end
        try:
            p1_idx = after.index("P1")
        except ValueError:
            p1_idx = name_start + len(codes)

        names = after[name_start:p1_idx]

        # Pair them up
        for code, name in zip(codes, names, strict=False):
            # Normalize code to match overall PDF format.
            # Team pages: "ALB 1" -> "ALB1", "ALB B 1" -> "ALB-B1"
            parts = code.split()
            if len(parts) == 3 and parts[1] == "B":
                # B-team: "ALB B 1" -> "ALB-B1"
                normalized_code = f"{parts[0]}-{parts[1]}{parts[2]}"
            else:
                # Regular: "ALB 1" -> "ALB1"
                normalized_code = code.replace(" ", "")
            code_to_name[normalized_code] = name

    return code_to_name


def _parse_medals_pdf(medals_file: Path) -> dict[str, tuple[str, str | None]]:
    """Parse the medals PDF and build a mapping of Code -> (name, award).

    Returns:
        Dict mapping contestant code (e.g. "MKD1") to (full_name, normalized_award).
    """
    medal_info: dict[str, tuple[str, str | None]] = {}

    for row in _iter_pdf_rows(medals_file):
        if len(row) < MED_MIN_COLS:
            continue
        if _is_header_row(row):
            continue

        code = row[MED_IDX_CODE].strip()
        name = row[MED_IDX_NAME].strip()
        award = _normalize_award(row[MED_IDX_MEDAL])

        if not code or not name:
            continue

        medal_info[code] = (name, award)

    return medal_info


class Parser2023(BaseParser):
    """Parser for JBMO 2023 (two PDFs: overall scores + medalist names)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        # raw_file is the overall PDF; medals PDF and team pages in same directory
        medals_file = raw_file.parent / "jbmo_2023_medals.pdf"
        if not medals_file.exists():
            raise FileNotFoundError(
                f"Medals PDF not found at {medals_file}. "
                "Download it first with: sigma download jbmo -d data/ --year 2023"
            )

        # Step 1: Parse team HTML pages for code -> name mapping
        team_names = _parse_team_pages(raw_file.parent)

        # Step 2: Parse medals PDF for name + award lookup
        medal_info = _parse_medals_pdf(medals_file)

        # Step 2: Parse overall PDF for all contestants
        results: list[ContestantResult] = []
        seen: set[str] = set()

        for row in _iter_pdf_rows(raw_file):
            if len(row) < OVR_MIN_COLS:
                continue
            if _is_header_row(row):
                continue

            result = self._parse_row(row, medal_info, team_names)
            if result is None:
                continue

            # Deduplicate by code (used as key in name field for non-medalists)
            code = row[OVR_IDX_CODE].strip()
            if code in seen:
                continue
            seen.add(code)
            results.append(result)

        self.compute_ranks(results)
        return results

    def _parse_row(
        self,
        row: list[str],
        medal_info: dict[str, tuple[str, str | None]],
        team_names: dict[str, str],
    ) -> ContestantResult | None:
        code = row[OVR_IDX_CODE].strip()
        if not code:
            return None

        country = _normalize_country(row[OVR_IDX_COUNTRY])
        if not country:
            return None

        # Look up name: try medals PDF first (has award too), then team pages
        if code in medal_info:
            name, award = medal_info[code]
            given_name, family_name = _split_name(name)
        elif code in team_names:
            name = team_names[code]
            award = None
            given_name, family_name = _split_name(name)
        else:
            # No name found anywhere -- use code as placeholder
            name = code
            award = None
            given_name = None
            family_name = None

        problem_scores = [_parse_score(row[OVR_IDX_P1 + i]) for i in range(4)]

        total = _parse_int(row[OVR_IDX_TOTAL])
        if total is None:
            total = sum(s for s in problem_scores if s is not None)

        # Skip non-participants (all scores None = never sat the exam)
        if all(s is None for s in problem_scores):
            return None

        return ContestantResult(
            name=name,
            country=country,
            problem_scores=problem_scores,
            total=total,
            rank=None,  # Will be computed by compute_ranks
            award=award,
            given_name=given_name,
            family_name=family_name,
        )
