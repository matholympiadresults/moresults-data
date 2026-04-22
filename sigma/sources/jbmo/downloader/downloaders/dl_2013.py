"""JBMO 2013 downloader.

Downloads the results HTML page from jbmo2013.tubitak.gov.tr.
HTML table with all contestants, per-problem scores, and medals.
Separate Name and Surname columns; codes like "ROU1", "TURB4".
"""

from pathlib import Path

import requests

SOURCE_URL = "https://jbmo2013.tubitak.gov.tr/Results.html"
SOURCE_TYPE = "html"
PRIMARY_FILENAME = "jbmo_2013_raw.html"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def download(raw_data_dir: Path, force: bool = False) -> Path:
    """Download the 2013 results HTML page."""
    raw_data_dir.mkdir(parents=True, exist_ok=True)
    output_file = raw_data_dir / PRIMARY_FILENAME

    if output_file.exists() and not force:
        return output_file

    response = requests.get(SOURCE_URL, timeout=30, headers=_HEADERS)
    response.raise_for_status()
    output_file.write_text(response.text, encoding="utf-8")
    return output_file
