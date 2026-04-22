"""JBMO 2014 downloader.

Downloads the results HTML page from the Wayback Machine archive of
jbmo2014.smm.com.mk. The original site is suspended.
HTML table with all 104 contestants, names, scores, and medals.
"""

from pathlib import Path

import requests

SOURCE_URL = "http://www.jbmo2014.smm.com.mk/results/total"
SOURCE_TYPE = "html"
PRIMARY_FILENAME = "jbmo_2014_raw.html"

_WAYBACK_URL = (
    "https://web.archive.org/web/20141015141454/http://www.jbmo2014.smm.com.mk:80/results/total"
)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def download(raw_data_dir: Path, force: bool = False) -> Path:
    """Download the 2014 results HTML page from the Wayback Machine."""
    raw_data_dir.mkdir(parents=True, exist_ok=True)
    output_file = raw_data_dir / PRIMARY_FILENAME

    if output_file.exists() and not force:
        return output_file

    response = requests.get(_WAYBACK_URL, timeout=30, headers=_HEADERS)
    response.raise_for_status()
    output_file.write_text(response.text, encoding="utf-8")
    return output_file
