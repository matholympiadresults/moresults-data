"""Shared helpers for BMO PDF parsers."""

import re
from collections.abc import Iterator
from pathlib import Path


def iter_pdf_rows(raw_file: Path) -> Iterator[list[str]]:
    """Yield all table rows from a PDF as lists of stripped strings.

    Header rows and empty rows are yielded as-is; callers decide what to skip.
    """
    try:
        import pdfplumber
    except ImportError as e:
        raise ImportError(
            "pdfplumber is required for PDF parsing. Install it with: pip install pdfplumber"
        ) from e

    with pdfplumber.open(raw_file) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table:
                    continue
                for row in table:
                    if row is None:
                        continue
                    yield [str(cell).strip() if cell else "" for cell in row]


def parse_int(value: str) -> int | None:
    """Parse an integer, returning None on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def parse_score(value: str) -> int | None:
    """Parse a problem score in [0, 10], returning None if out of range or invalid."""
    score = parse_int(value)
    if score is None or score < 0 or score > 10:
        return None
    return score


def extract_country_from_code(code: str) -> str | None:
    """Extract a country code from patterns like 'ALB1', 'ROU 1', 'BGR2', 'BIH-B1'."""
    match = re.match(r"^([A-Za-z]+)(?:-[A-Za-z]*)?\s*\d*$", code)
    return match.group(1).upper() if match else None


def normalize_award(award: str | None) -> str | None:
    """Normalize award text to standard format (Gold/Silver/Bronze/Honourable Mention)."""
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
    return award or None
