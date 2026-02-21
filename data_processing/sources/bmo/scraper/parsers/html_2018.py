"""Parser for BMO 2018 results from bmo2018.dms.rs."""

from pathlib import Path

import requests
from bs4 import BeautifulSoup

from ..models import ContestantResult
from .base import BaseParser


class Parser2018(BaseParser):
    """Parser for BMO 2018 results.

    Source: https://bmo2018.dms.rs/results/
    Table columns: Rank, Name and Surname, Country, P1, P2, P3, P4, Total, Medal
    """

    @property
    def source_url(self) -> str:
        return "https://bmo2018.dms.rs/results/"

    @property
    def source_type(self) -> str:
        return "html"

    def download_raw(self, force: bool = False) -> Path:
        """Download HTML page and save to raw_data_dir."""
        output_file = self.raw_data_dir / self.get_raw_filename()

        if output_file.exists() and not force:
            return output_file

        response = requests.get(self.source_url, timeout=30)
        response.raise_for_status()

        self.raw_data_dir.mkdir(parents=True, exist_ok=True)
        output_file.write_text(response.text, encoding="utf-8")
        return output_file

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

            # Expected: Rank, Name and Surname, Country, P1, P2, P3, P4, Total, Medal
            if len(cells) < 9:
                continue

            # Name (skip rank column - we compute ranks ourselves)
            name = cells[1].get_text(strip=True)
            if not name:
                continue

            # Country
            country = cells[2].get_text(strip=True)

            # Problem scores (cells 3-6)
            problem_scores = []
            for i in range(4):
                score_text = cells[3 + i].get_text(strip=True)
                try:
                    score = int(score_text) if score_text else None
                except ValueError:
                    score = None
                problem_scores.append(score)

            # Total (cell 7)
            total_text = cells[7].get_text(strip=True)
            try:
                total = int(total_text)
            except ValueError:
                continue

            # Award (cell 8)
            award_text = cells[8].get_text(strip=True) if len(cells) > 8 else ""
            award = self._normalize_award(award_text) if award_text else None

            results.append(
                ContestantResult(
                    name=name,
                    country=country,
                    problem_scores=problem_scores,
                    total=total,
                    rank=None,  # Computed below
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
