"""Parser for BMO 2024 results from bmo2024.org."""

from pathlib import Path

from bs4 import BeautifulSoup

from ..models import ContestantResult
from .base import BaseParser


class Parser2024(BaseParser):
    """Parser for BMO 2024 results.

    Source: https://bmo2024.org/results/
    Table columns: Code, Name, P1, P2, P3, P4, Total, Medal
    """

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        """Parse the HTML table and extract contestant results."""
        html = raw_file.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Find the results table
        table = soup.find("table")
        if not table:
            raise ValueError(f"Could not find results table for BMO {self.year}")

        rows = table.find_all("tr")

        for row in rows:
            cells = row.find_all("td")
            if len(cells) == 0:
                continue

            # Expected columns: Code, Name, P1, P2, P3, P4, Total, Medal
            if len(cells) < 8:
                continue

            # Extract data
            # Code is in cells[0], but we don't need it for the model
            name = cells[1].get_text(strip=True)
            if not name:
                continue

            # Problem scores (cells 2-5)
            problem_scores = []
            for i in range(4):
                score_text = cells[2 + i].get_text(strip=True)
                try:
                    score = int(score_text) if score_text else None
                except ValueError:
                    score = None
                problem_scores.append(score)

            # Total (cell 6)
            total_text = cells[6].get_text(strip=True)
            try:
                total = int(total_text)
            except ValueError:
                continue

            # Medal (cell 7)
            award_text = cells[7].get_text(strip=True)
            award = self._normalize_award(award_text) if award_text else None

            # Extract country from code (first 3 letters typically)
            code = cells[0].get_text(strip=True)
            country = code[:3] if code else "UNK"

            # Rank will be computed after all results are collected
            results.append(
                ContestantResult(
                    name=name,
                    country=country,
                    problem_scores=problem_scores,
                    total=total,
                    rank=None,  # Placeholder, computed below
                    award=award,
                )
            )

        # Compute proper competition-style ranks
        self.compute_ranks(results)

        return results

    def _normalize_award(self, award: str) -> str | None:
        """Normalize award text to standard format."""
        award_lower = award.lower().strip()
        if "gold" in award_lower:
            return "Gold"
        elif "silver" in award_lower:
            return "Silver"
        elif "bronze" in award_lower:
            return "Bronze"
        elif "honourable" in award_lower or "honorable" in award_lower or "hm" in award_lower:
            return "Honourable Mention"
        return award if award else None
