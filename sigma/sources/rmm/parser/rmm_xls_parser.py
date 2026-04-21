"""RMM 2009 and 2010 XLS parsers.

These editions were distributed as Excel files. The 2009 file has 4 problems
and includes individual and team sheets. The 2010 file has 6 problems across
separate "Individual" and "Teams" sheets. Names are stored as "Last First"
(with a few particle-prefixed variants); we swap them into natural "First Last"
order so person matching joins them to later years.
"""

from pathlib import Path

import xlrd

from .models import ContestantResult, RMMYearResults, ValidationResult
from .rmm_parser import ParseError

# Lowercase particles that belong with the surname when found at the start
# of an inverted name (e.g. "von Burg Teodor" -> "Teodor von Burg").
_NAME_PARTICLES: frozenset[str] = frozenset({"von", "van", "de", "da", "del", "le", "la"})


def _normalize_name(raw: str) -> str:
    """Convert "Last First [Middle]" style names into "First [Middle] Last".

    Handles a leading lowercase particle ("von Burg Teodor" -> "Teodor von Burg")
    and strips trailing ♀ markers / extra whitespace.
    """
    name = raw.replace("♀", "").strip()
    # Collapse internal runs of whitespace.
    name = " ".join(name.split())
    if not name:
        return name

    parts = name.split(" ")
    if len(parts) == 1:
        return name

    # "von Burg Teodor" -> treat "von Burg" as the two-word surname.
    if parts[0].lower() in _NAME_PARTICLES and len(parts) >= 3:
        surname = f"{parts[0]} {parts[1]}"
        given = " ".join(parts[2:])
        return f"{given} {surname}"

    surname = parts[0]
    given = " ".join(parts[1:])
    return f"{given} {surname}"


def _parse_score(cell_value) -> int:
    """Coerce an xls score cell (possibly empty) to an int in [0, 7]."""
    if cell_value == "" or cell_value is None:
        return 0
    try:
        score = int(cell_value)
    except (TypeError, ValueError) as e:
        raise ParseError(f"invalid score cell: {cell_value!r}") from e
    if score < 0 or score > 7:
        raise ParseError(f"score {score} out of range [0, 7]")
    return score


def _parse_prize(raw: str) -> tuple[str | None, str | None]:
    """Split a prize column into (award, extra_award).

    Accepts inputs like "Gold", "Silver Medal", "Hon. Mention",
    "Special + Gold", or empty.
    Returns canonical award string ("GOLD"/"SILVER"/"BRONZE"/"HON. MEN.") or None,
    plus an optional extra_award string for special prizes.
    """
    text = raw.strip()
    if not text:
        return None, None

    extra: str | None = None
    if "+" in text:
        left, right = (part.strip() for part in text.split("+", 1))
        extra = left
        text = right

    canonical = {
        "gold": "GOLD",
        "gold medal": "GOLD",
        "silver": "SILVER",
        "silver medal": "SILVER",
        "bronze": "BRONZE",
        "bronze medal": "BRONZE",
        "hon. mention": "HON. MEN.",
        "honourable mention": "HON. MEN.",
    }
    key = text.lower()
    if key not in canonical:
        raise ParseError(f"unknown prize value: {raw!r}")
    return canonical[key], extra


def _iter_contestant_rows(sheet, num_problems: int, header_row: int):
    """Yield (row_idx, cells) tuples for data rows, stopping at totals/blanks."""
    expected_cols = 3 + num_problems + 2  # Name, Country, Code + Ps + Total + Prize
    for row_idx in range(header_row + 1, sheet.nrows):
        cells = [sheet.cell_value(row_idx, c) for c in range(min(sheet.ncols, expected_cols))]
        # Stop at "Grand Total" / "Average" footer rows — they begin with a
        # non-contestant label in col 0 or 1.
        joined = " ".join(str(c) for c in cells).lower()
        if "grand total" in joined or "average" in joined:
            break
        yield row_idx, cells


def _parse_xls_sheet(sheet, num_problems: int, year: int) -> list[ContestantResult]:
    results: list[ContestantResult] = []

    # Locate header row: the row whose first cell contains "Contestant".
    header_row = None
    for r in range(min(sheet.nrows, 10)):
        first = str(sheet.cell_value(r, 0)).strip().lower()
        if "contestant" in first:
            header_row = r
            break
    if header_row is None:
        raise ParseError(f"{year}: could not find header row in sheet {sheet.name!r}")

    for row_idx, cells in _iter_contestant_rows(sheet, num_problems, header_row):
        raw_name = str(cells[0]).strip()
        raw_country = str(cells[1]).strip()

        # Blank rows and DNS rows (empty name or no scores) are skipped.
        if not raw_name or "(contestant)" in raw_name.lower():
            continue
        if not raw_country:
            continue

        name = _normalize_name(raw_name)

        # Country codes sometimes have trailing spaces in the xls.
        country = raw_country.strip().upper()

        score_start = 3
        try:
            scores = [_parse_score(cells[score_start + i]) for i in range(num_problems)]
        except ParseError as e:
            raise ParseError(f"{year} row {row_idx} ({name}): {e}") from e

        total_raw = cells[score_start + num_problems]
        try:
            total = int(total_raw) if total_raw != "" else 0
        except (TypeError, ValueError) as e:
            raise ParseError(f"{year} row {row_idx}: invalid total {total_raw!r} ({name})") from e

        prize_raw = str(cells[score_start + num_problems + 1]).strip()
        if prize_raw.upper() == "DNS":
            # Did-not-start rows: skip entirely.
            continue

        try:
            award, extra = _parse_prize(prize_raw)
        except ParseError as e:
            raise ParseError(f"{year} row {row_idx} ({name}): {e}") from e

        # Stash "Special" extra awards onto the contestant name for the ingester
        # to pull off — ContestantResult has no extra_award field, so we piggy-
        # back via a parallel dict. Here we just drop the extra; the existing
        # RMM ingester does not record extra awards, matching pre-2008 policy.
        del extra  # Acknowledge parsed but unused.

        results.append(
            ContestantResult(
                name=name,
                country=country,
                problem_scores=scores,
                total=total,
                rank=None,
                award=award,
                is_official_team=False,
                is_online=False,
            )
        )

    return results


def _assign_ranks(results: list[ContestantResult]) -> None:
    """Assign ranks in descending-total order; ties share a rank number."""
    ordered = sorted(enumerate(results), key=lambda ir: (-ir[1].total, ir[0]))
    prev_total: int | None = None
    rank = 0
    for position, (_, r) in enumerate(ordered, start=1):
        if r.total != prev_total:
            rank = position
            prev_total = r.total
        r.rank = rank


def parse_2009_xls(xls_path: Path) -> RMMYearResults:
    """Parse the RMM 2009 XLS (4 problems, individual sheet only)."""
    workbook = xlrd.open_workbook(str(xls_path))
    sheet = workbook.sheet_by_index(0)
    results = _parse_xls_sheet(sheet, num_problems=4, year=2009)
    if not results:
        raise ParseError("2009: no results parsed")
    _assign_ranks(results)
    mismatches = [
        {
            "name": r.name,
            "country": r.country,
            "calculated": sum(r.problem_scores),
            "reported": r.total,
        }
        for r in results
        if sum(r.problem_scores) != r.total
    ]
    return RMMYearResults(
        year=2009,
        total_contestants=len(results),
        results=results,
        validation=ValidationResult(all_totals_match=not mismatches, mismatches=mismatches),
    )


def parse_2010_xls(xls_path: Path) -> RMMYearResults:
    """Parse the RMM 2010 XLS (6 problems, 'Individual' sheet)."""
    workbook = xlrd.open_workbook(str(xls_path))
    try:
        sheet = workbook.sheet_by_name("Individual")
    except xlrd.XLRDError as e:
        raise ParseError("2010: no 'Individual' sheet in xls") from e
    results = _parse_xls_sheet(sheet, num_problems=6, year=2010)
    if not results:
        raise ParseError("2010: no results parsed")
    _assign_ranks(results)
    mismatches = [
        {
            "name": r.name,
            "country": r.country,
            "calculated": sum(r.problem_scores),
            "reported": r.total,
        }
        for r in results
        if sum(r.problem_scores) != r.total
    ]
    return RMMYearResults(
        year=2010,
        total_contestants=len(results),
        results=results,
        validation=ValidationResult(all_totals_match=not mismatches, mismatches=mismatches),
    )
