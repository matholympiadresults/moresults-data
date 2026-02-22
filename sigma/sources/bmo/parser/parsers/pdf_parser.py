"""PDF parser for BMO results (2025, 2022, 2021, 2020)."""

from pathlib import Path

from ..models import ContestantResult
from .base import BaseParser


class PDFParser(BaseParser):
    """Parser for BMO results from PDF files.

    Uses pdfplumber to extract tables from PDF documents.

    Expected table structure:
    A/A (rank), CODE, NAME, COUNTRY, PR1, PR2, PR3, PR4, TOTAL, MEDAL
    """

    def parse(self, raw_file: Path) -> list[ContestantResult]:
        """Parse the PDF and extract contestant results using pdfplumber."""
        try:
            import pdfplumber
        except ImportError as e:
            raise ImportError(
                "pdfplumber is required for PDF parsing. Install it with: pip install pdfplumber"
            ) from e

        results = []
        seen_contestants = set()

        with pdfplumber.open(raw_file) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()

                for table in tables:
                    if not table:
                        continue

                    # Detect column structure from header row
                    header_indices = self._detect_columns(table)

                    # Process each row in the table
                    for row in table:
                        if not row or len(row) < 7:
                            continue

                        # Skip header rows
                        if self._is_header_row(row):
                            continue

                        result = self._parse_row(row, header_indices)
                        if result:
                            # Deduplicate by name
                            key = (result.name, result.country)
                            if key not in seen_contestants:
                                seen_contestants.add(key)
                                results.append(result)

        # Compute proper competition-style ranks (overrides any source ranks)
        self.compute_ranks(results)

        return results

    def _detect_columns(self, table: list) -> dict:
        """Detect column indices from the header row."""
        # Default indices for expected structure:
        # A/A, CODE, NAME, COUNTRY, PR1, PR2, PR3, PR4, TOTAL, MEDAL
        default_indices = {
            "rank": 0,
            "code": 1,
            "name": 2,
            "country": 3,
            "p1": 4,
            "p2": 5,
            "p3": 6,
            "p4": 7,
            "total": 8,
            "medal": 9,
        }

        # Try to find header row and detect actual indices
        for row in table:
            if not row:
                continue
            row_lower = [str(cell).lower().strip() if cell else "" for cell in row]

            # Check if this looks like a header row
            row_text = " ".join(row_lower)
            if "name" in row_text or "country" in row_text or "total" in row_text:
                indices = {}
                for i, cell in enumerate(row_lower):
                    if "a/a" in cell or cell == "rank" or cell == "#":
                        indices["rank"] = i
                    elif cell == "code":
                        indices["code"] = i
                    elif "given name" in cell:
                        # 2025 format: separate given name column
                        indices["given_name"] = i
                    elif cell == "surname":
                        # 2025 format: separate surname column
                        indices["surname"] = i
                    elif "name" in cell and "name" not in indices and "given_name" not in indices:
                        # Matches "name", "student name&surname", etc.
                        indices["name"] = i
                    elif cell == "country":
                        indices["country"] = i
                    elif "problem 1" in cell or cell in ["pr1", "p1", "problem1"]:
                        indices["p1"] = i
                    elif "problem 2" in cell or cell in ["pr2", "p2", "problem2"]:
                        indices["p2"] = i
                    elif "problem 3" in cell or cell in ["pr3", "p3", "problem3"]:
                        indices["p3"] = i
                    elif "problem 4" in cell or cell in ["pr4", "p4", "problem4"]:
                        indices["p4"] = i
                    elif cell == "total":
                        indices["total"] = i
                    elif cell in ["medal", "award", "prize"]:
                        indices["medal"] = i

                # Fill in missing with defaults if we found some
                if indices:
                    for key, val in default_indices.items():
                        if key not in indices:
                            indices[key] = val
                    return indices

        return default_indices

    def _is_header_row(self, row: list) -> bool:
        """Check if this is a header row."""
        row_text = " ".join(str(cell).lower() for cell in row if cell)
        header_keywords = [
            "a/a",
            "rank",
            "name",
            "country",
            "problem",
            "total",
            "medal",
            "award",
            "pr1",
            "pr2",
            "code",
        ]
        return any(kw in row_text for kw in header_keywords)

    def _parse_row(self, row: list, indices: dict) -> ContestantResult | None:
        """Parse a single row from the table."""
        import re

        # Clean the row
        clean_row = [str(cell).strip() if cell else "" for cell in row]

        if len(clean_row) < max(indices.values()) + 1:
            return None

        # Extract rank
        rank: int | None = None
        try:
            rank = int(clean_row[indices["rank"]])
        except (ValueError, IndexError, KeyError):
            pass

        # Extract name - handle 2025 format with separate given_name and surname
        if "given_name" in indices and "surname" in indices:
            given_name = clean_row[indices.get("given_name", 0)]
            surname = clean_row[indices.get("surname", 1)]
            name = f"{given_name} {surname}".strip()
        else:
            name = clean_row[indices.get("name", 2)]
        if not name:
            return None

        # Extract country
        # First check for dedicated country column
        country = clean_row[indices.get("country", 3)] if "country" in indices else ""

        # If no country, try to extract from code (e.g., "ALB1" -> "ALB")
        if not country or country.isdigit():
            code_idx = indices.get("code")
            if code_idx is not None and code_idx < len(clean_row):
                code = clean_row[code_idx]
                # Extract country code from patterns like "ALB1", "ROU 1", "BGR2", "BIH-B1"
                match = re.match(r"^([A-Za-z]+)(?:-[A-Za-z]*)?\s*\d*$", code)
                if match:
                    country = match.group(1).upper()

        if not country:
            country = "UNK"

        # Extract problem scores
        problem_scores = []
        for p in ["p1", "p2", "p3", "p4"]:
            idx = indices.get(p)
            if idx is not None and idx < len(clean_row):
                try:
                    score = int(clean_row[idx])
                    if 0 <= score <= 10:
                        problem_scores.append(score)
                    else:
                        problem_scores.append(None)
                except (ValueError, IndexError):
                    problem_scores.append(None)
            else:
                problem_scores.append(None)

        if len(problem_scores) != 4:
            return None

        # Extract total
        total = 0
        total_idx = indices.get("total")
        if total_idx is not None and total_idx < len(clean_row):
            try:
                total = int(clean_row[total_idx])
            except (ValueError, IndexError):
                # Calculate from scores
                valid_scores = [s for s in problem_scores if s is not None]
                total = sum(valid_scores)
        else:
            valid_scores = [s for s in problem_scores if s is not None]
            total = sum(valid_scores)

        # Extract award
        award = None
        medal_idx = indices.get("medal")
        if medal_idx is not None and medal_idx < len(clean_row):
            award = self._normalize_award(clean_row[medal_idx])

        return ContestantResult(
            name=name,
            country=country,
            problem_scores=problem_scores,
            total=total,
            rank=rank,
            award=award,
        )

    def _normalize_award(self, award: str) -> str | None:
        """Normalize award text to standard format."""
        if not award:
            return None
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
