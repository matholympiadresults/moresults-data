"""RMM 2008 HTML parser.

The 2008 edition used a different HTML format:
- Header text is "Results" (not "Individual Results")
- 10 columns: Nr, Last name, First name, Country, P1-P4, Total, Medal
- Only 4 problems instead of 6
- Country is a full name (e.g., "Poland", "United Kingdom") rather than an ISO code
- Yakutsk appears as a standalone "country" (regional Russian delegation)
"""

from bs4 import BeautifulSoup

from .models import ContestantResult, RMMYearResults, ValidationResult
from .rmm_parser import ParseError

# Map full country name from 2008 HTML to a 3-letter code normalized by the ingester.
COUNTRY_NAME_TO_CODE: dict[str, str] = {
    "Poland": "POL",
    "Serbia": "SRB",
    "United Kingdom": "GBR",
    "Russia": "RUS",
    "Romania": "ROU",
    "Bulgaria": "BGR",
    "Moldova": "MDA",
    "Yakutsk": "YAKUTSK",
}

# Medal text -> canonical award string used by the ingester.
MEDAL_MAP: dict[str, str] = {
    "GOLD": "GOLD",
    "SILVER": "SILVER",
    "BRONZE": "BRONZE",
}


def parse_2008_html(html: str) -> RMMYearResults:
    """Parse the RMM 2008 results HTML file."""
    soup = BeautifulSoup(html, "html.parser")

    header = next(
        (
            h
            for h in soup.find_all("h2", class_="title_content")
            if h.get_text(strip=True) == "Results"
        ),
        None,
    )
    if header is None:
        raise ParseError("2008: could not find 'Results' header")

    # The table is inside the next <td id="inside_content"> sibling row.
    parent = header.find_parent("tr")
    table = None
    for sibling in parent.find_next_siblings("tr"):
        td = sibling.find("td", id="inside_content")
        if td:
            table = td.find("table")
            break
    if table is None:
        raise ParseError("2008: could not find results table")

    results: list[ContestantResult] = []
    current_rank: int | None = None

    for row_idx, row in enumerate(table.find_all("tr")):
        cells = row.find_all("td")
        if len(cells) != 10:
            continue

        first_cell = cells[0].get_text(strip=True)
        # Header row
        if cells[0].find("b") or first_cell in ("Nr.", ""):
            continue

        try:
            current_rank = int(first_cell)
        except ValueError:
            continue

        last_name = cells[1].get_text(strip=True)
        first_name = cells[2].get_text(strip=True)
        if not last_name or not first_name:
            raise ParseError(f"2008 row {row_idx}: missing name")
        name = f"{first_name} {last_name}"

        country_name = cells[3].get_text(strip=True)
        country_code = COUNTRY_NAME_TO_CODE.get(country_name)
        if country_code is None:
            raise ParseError(f"2008 row {row_idx}: unknown country {country_name!r}")

        scores: list[int] = []
        for i in range(4):
            raw = cells[4 + i].get_text(strip=True)
            try:
                score = int(raw)
            except ValueError as e:
                raise ParseError(
                    f"2008 row {row_idx}: invalid score {raw!r} for P{i + 1} ({name})"
                ) from e
            if score < 0 or score > 7:
                raise ParseError(
                    f"2008 row {row_idx}: score {score} out of range for P{i + 1} ({name})"
                )
            scores.append(score)

        total_text = cells[8].get_text(strip=True)
        try:
            total = int(total_text)
        except ValueError as e:
            raise ParseError(f"2008 row {row_idx}: invalid total {total_text!r} ({name})") from e

        medal_text = cells[9].get_text(strip=True).upper()
        award = MEDAL_MAP.get(medal_text) if medal_text else None
        if medal_text and award is None:
            raise ParseError(f"2008 row {row_idx}: unknown medal {medal_text!r} ({name})")

        results.append(
            ContestantResult(
                name=name,
                country=country_code,
                problem_scores=scores,
                total=total,
                rank=current_rank,
                award=award,
                is_official_team=False,
                is_online=False,
            )
        )

    if not results:
        raise ParseError("2008: no results parsed")

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
        year=2008,
        total_contestants=len(results),
        results=results,
        validation=ValidationResult(all_totals_match=not mismatches, mismatches=mismatches),
    )
