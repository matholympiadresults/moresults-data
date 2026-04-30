"""JBMO 2025 downloader.

Downloads the participants page from web.archive.org. The participants
page provides the country-code + team-number to contestant-name mapping
(e.g. "ALB 1" -> "Eol Myshketa") that pairs with the per-problem score
sheet stored in jbmo_2025_scores.xlsx.

The XLSX file (with per-problem scores) is supplied manually and is not
downloadable; only the participants page is fetched here.
"""

from pathlib import Path

import requests

SOURCE_URL = "https://web.archive.org/web/20260210185927/https://jbmo2025.mk/participants"
SOURCE_TYPE = "html"
PRIMARY_FILENAME = "jbmo_2025_participants.html"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def download(raw_data_dir: Path, force: bool = False) -> Path:
    """Download the 2025 participants page (web.archive.org snapshot)."""
    raw_data_dir.mkdir(parents=True, exist_ok=True)
    output_file = raw_data_dir / PRIMARY_FILENAME

    if output_file.exists() and not force:
        return output_file

    response = requests.get(SOURCE_URL, timeout=60, headers=_HEADERS)
    response.raise_for_status()
    output_file.write_text(response.text, encoding="utf-8")
    return output_file
