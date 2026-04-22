"""JBMO 2012 downloader.

Downloads the results HTML page from the Wayback Machine snapshot of
hms.gr/16jbmo2012/medals.htm.  The original site now returns 301, so
we fetch the Internet Archive's cached copy.

HTML table with all 89 contestants, scores, and medals.
"""

from pathlib import Path

import requests

SOURCE_URL = "https://web.archive.org/web/2025/http://www.hms.gr/16jbmo2012/medals.htm"
SOURCE_TYPE = "html"
PRIMARY_FILENAME = "jbmo_2012_raw.html"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def download(raw_data_dir: Path, force: bool = False) -> Path:
    """Download the 2012 results HTML page."""
    raw_data_dir.mkdir(parents=True, exist_ok=True)
    output_file = raw_data_dir / PRIMARY_FILENAME

    if output_file.exists() and not force:
        return output_file

    response = requests.get(SOURCE_URL, timeout=30, headers=_HEADERS)
    response.raise_for_status()
    output_file.write_text(response.text, encoding="utf-8")
    return output_file
