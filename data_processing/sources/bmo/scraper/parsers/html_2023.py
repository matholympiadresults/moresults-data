"""Parser for BMO 2023 results from bmo2023.tubitak.gov.tr."""

from pathlib import Path

import requests
from bs4 import BeautifulSoup

from ..models import ContestantResult
from .base import BaseParser


class Parser2023(BaseParser):
    """Parser for BMO 2023 results.

    Source: https://bmo2023.tubitak.gov.tr/results
    Table columns: Rank, Country Code, First Name, Surname, P1, P2, P3, P4, Total, Medal
    """

    @property
    def source_url(self) -> str:
        return "https://bmo2023.tubitak.gov.tr/results"

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

        # Find the contestants table (first table with contestant data)
        tables = soup.find_all("table")
        contestant_table = None
        for table in tables:
            # Look for table with rank column
            headers = table.find_all("th")
            header_texts = [h.get_text(strip=True).lower() for h in headers]
            if "rank" in header_texts or any("name" in h for h in header_texts):
                contestant_table = table
                break

        if not contestant_table:
            raise ValueError(f"Could not find contestants table for BMO {self.year}")

        rows = contestant_table.find_all("tr")

        for row in rows:
            cells = row.find_all("td")
            if len(cells) == 0:
                continue

            # Expected: Rank, Country, First Name, Surname, P1-P4, Total, Medal
            if len(cells) < 10:
                continue

            # Skip rank column - we compute ranks ourselves

            # Country code
            country = cells[1].get_text(strip=True)

            # Name (First + Surname)
            first_name = cells[2].get_text(strip=True)
            surname = cells[3].get_text(strip=True)
            name = f"{first_name} {surname}".strip()

            if not name:
                continue

            # Problem scores (cells 4-7)
            problem_scores = []
            for i in range(4):
                score_text = cells[4 + i].get_text(strip=True)
                try:
                    score = int(score_text) if score_text else None
                except ValueError:
                    score = None
                problem_scores.append(score)

            # Total (cell 8)
            total_text = cells[8].get_text(strip=True)
            try:
                total = int(total_text)
            except ValueError:
                continue

            # Award (cell 9)
            award_text = cells[9].get_text(strip=True) if len(cells) > 9 else ""
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
