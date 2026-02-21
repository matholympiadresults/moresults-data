#!/usr/bin/env python3
"""
MEMO 2013 Parser

Parses the MEMO 2013 individual results PDF into structured data.
Uses text-based parsing since table extraction can miss rows at page boundaries.
"""

import re
from pathlib import Path

import pdfplumber

from .models import ContestantResult, MEMOYearResults, ValidationResult

# Country code mapping from PDF codes to standard country names
COUNTRY_CODE_MAP = {
    "AUT": "Austria",
    "CRO": "Croatia",
    "CZR": "Czech Republic",
    "GER": "Germany",
    "HUN": "Hungary",
    "LTU": "Lithuania",
    "POL": "Poland",
    "SLN": "Slovenia",
    "SUI": "Switzerland",
    "SVK": "Slovakia",
}

# Award mapping
AWARD_MAP = {
    "Gold": "Gold",
    "Silver": "Silver",
    "Bronze": "Bronze",
    "Hon. Men.": "Honourable Mention",
}

# Regex pattern to match result rows
# Format: Rank Name Code I-1 I-2 I-3 I-4 Total [Medal]
# Example: 25-35 Marko Puza SVK 4 0 1 8 1 10 Bronze
ROW_PATTERN = re.compile(
    r"^(\d+(?:-\d+)?)\s+"  # Rank (e.g., "1-3" or "25")
    r"(.+?)\s+"  # Name (non-greedy)
    r"(AUT|CRO|CZR|GER|HUN|LTU|POL|SLN|SUI|SVK)\s+"  # Country code
    r"(\d+)\s+"  # Contestant number within country
    r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+"  # I-1, I-2, I-3, I-4 scores
    r"(\d+)"  # Total
    r"(?:\s+(Gold|Silver|Bronze|Hon\. Men\.))?$"  # Optional medal
)


class ParserError(Exception):
    """Raised when parsing fails unexpectedly."""

    pass


def get_parsed_filename() -> str:
    """Get the filename for a parsed JSON file."""
    return "scoreboard.json"


def parse_rank(rank_str: str) -> int:
    """Parse rank string, handling tied ranks like '1-3' -> 1."""
    rank_str = rank_str.strip()
    if "-" in rank_str:
        return int(rank_str.split("-")[0])
    return int(rank_str)


def parse_pdf(pdf_path: Path) -> list[ContestantResult]:
    """Parse the PDF and extract contestant results using text extraction."""
    results = []
    seen_names = set()

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue

            for line_num, line in enumerate(text.split("\n")):
                line = line.strip()

                # Skip header and title lines
                if not line or line.startswith("MEMO2013") or line.startswith("Rank"):
                    continue

                match = ROW_PATTERN.match(line)
                if not match:
                    continue

                try:
                    rank = parse_rank(match.group(1))
                    name = match.group(2).strip()
                    country_code = match.group(3)
                    country = COUNTRY_CODE_MAP.get(country_code, country_code)

                    # Parse problem scores
                    problem_scores = [
                        int(match.group(5)),
                        int(match.group(6)),
                        int(match.group(7)),
                        int(match.group(8)),
                    ]

                    # Validate scores are in range
                    for i, score in enumerate(problem_scores):
                        if score < 0 or score > 8:
                            raise ParserError(
                                f"Page {page_num + 1}, line {line_num}: "
                                f"Score {score} out of range [0-8] for I-{i + 1}, contestant {name}"
                            )

                    total = int(match.group(9))

                    # Parse award (can be None)
                    award_str = match.group(10)
                    award = AWARD_MAP.get(award_str) if award_str else None

                    # Skip duplicates (in case of any page overlap)
                    name_key = (name, country)
                    if name_key in seen_names:
                        continue
                    seen_names.add(name_key)

                    results.append(
                        ContestantResult(
                            name=name,
                            country=country,
                            problem_scores=problem_scores,
                            total=total,
                            rank=rank,
                            award=award,
                        )
                    )
                except (ValueError, IndexError) as e:
                    raise ParserError(
                        f"Page {page_num + 1}, line {line_num}: Failed to parse line '{line}': {e}"
                    ) from e

    # Sort results by rank for consistent output
    results.sort(key=lambda r: (r.rank or 0, r.name))

    return results


def validate_totals(results: list[ContestantResult]) -> list[dict]:
    """Validate that totals match sum of individual scores. Returns mismatches."""
    mismatches = []
    for r in results:
        calculated = sum(r.problem_scores)
        if calculated != r.total:
            mismatches.append(
                {
                    "name": r.name,
                    "country": r.country,
                    "calculated": calculated,
                    "reported": r.total,
                }
            )
    return mismatches


def save_json(data: MEMOYearResults, filepath: Path) -> None:
    """Save results to JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(data.model_dump_json(indent=2))


def parse_2013(raw_dir: Path, output_dir: Path, force: bool = False) -> Path:
    """
    Parse the MEMO 2013 PDF and save as structured JSON.

    Args:
        raw_dir: Directory containing raw PDF file (2013 year subdirectory)
        output_dir: Directory to save parsed JSON (2013 year subdirectory)
        force: If True, re-parse even if output file exists

    Returns:
        Path to the parsed JSON file

    Raises:
        ParserError: If parsing fails
        FileNotFoundError: If raw PDF file doesn't exist
    """
    from data_processing.sources.memo.downloader.memo_2013_downloader import (
        get_raw_filename,
    )

    raw_file = raw_dir / get_raw_filename()
    output_file = output_dir / get_parsed_filename()

    if output_file.exists() and not force:
        return output_file

    if not raw_file.exists():
        raise FileNotFoundError(f"Raw PDF file not found: {raw_file}")

    results = parse_pdf(raw_file)

    if not results:
        raise ParserError("No results found in MEMO 2013 PDF.")

    mismatches = validate_totals(results)

    year_results = MEMOYearResults(
        year=2013,
        total_contestants=len(results),
        results=results,
        validation=ValidationResult(
            all_totals_match=len(mismatches) == 0,
            mismatches=mismatches,
        ),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    save_json(year_results, output_file)

    return output_file
