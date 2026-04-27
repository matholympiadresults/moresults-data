"""Parser for EMO 2026 results from the official CSV.

Source: emo2026.lt (CSV provided by organisers).

CSV layout (with a leading empty column):
    ,Rank,First name,Last Name,Code,#,P1,P2,P3,P4,P5,P6,P7,P8,Sum,Prize

Country codes appear as either bare 3-letter codes (e.g. "KAZ") or with an
"A"/"B" team suffix (e.g. "UKR A", "LTU B").
"""

import csv
from pathlib import Path

from ..models import ContestantResult
from .base import BaseParser


def _parse_int(text: str) -> int | None:
    text = text.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


class Parser2026(BaseParser):
    """Parser for EMO 2026 (CSV from emo2026.lt)."""

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        results: list[ContestantResult] = []

        with open(raw_file, encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Find the header row (contains "Rank" and "First name").
        header_idx = None
        for i, row in enumerate(rows):
            if any(cell.strip() == "Rank" for cell in row) and any(
                cell.strip() == "First name" for cell in row
            ):
                header_idx = i
                break
        if header_idx is None:
            raise ValueError("Could not locate header row in EMO 2026 CSV")

        header = [c.strip() for c in rows[header_idx]]
        col = {name: idx for idx, name in enumerate(header) if name}

        required = ["Rank", "First name", "Last Name", "Code", "Sum", "Prize"]
        for name in required:
            if name not in col:
                raise ValueError(f"Missing required column {name!r} in EMO 2026 CSV")

        problem_columns = [f"P{i}" for i in range(1, 9)]
        for name in problem_columns:
            if name not in col:
                raise ValueError(f"Missing problem column {name!r} in EMO 2026 CSV")

        for row in rows[header_idx + 1 :]:
            if not any(cell.strip() for cell in row):
                continue

            first_name = row[col["First name"]].strip()
            last_name = row[col["Last Name"]].strip()
            if not first_name and not last_name:
                continue

            full_name = f"{first_name} {last_name}".strip()
            country = row[col["Code"]].strip()

            problem_scores = [_parse_int(row[col[p]]) for p in problem_columns]
            total = _parse_int(row[col["Sum"]])
            if total is None:
                total = sum(s for s in problem_scores if s is not None)

            rank = _parse_int(row[col["Rank"]])

            contestant_number = None
            if "#" in col:
                contestant_number = _parse_int(row[col["#"]])

            award = self.normalize_award(row[col["Prize"]].strip()) or None

            results.append(
                ContestantResult(
                    name=full_name,
                    country=country,
                    contestant_number=contestant_number,
                    problem_scores=problem_scores,
                    total=total,
                    rank=rank,
                    award=award,
                    given_name=first_name or None,
                    family_name=last_name or None,
                )
            )

        return results
