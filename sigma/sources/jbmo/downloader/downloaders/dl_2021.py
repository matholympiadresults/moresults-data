"""JBMO 2021 downloader.

Downloads per-country HTML pages from jbmo2021.ance.gov.md.
Each country page has a table with contestant codes, names, scores, and awards.
"""

from pathlib import Path

import requests

SOURCE_URL = "http://jbmo2021.ance.gov.md/participants.html"
SOURCE_TYPE = "html"
PRIMARY_FILENAME = "jbmo_2021_participants.html"

_BASE_URL = "http://jbmo2021.ance.gov.md/"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# All country pages to download
COUNTRY_PAGES = [
    "albania.html",
    "azerbajan.html",
    "bosnia.html",
    "bulgaria.html",
    "croatia.html",
    "cyprus.html",
    "france.html",
    "greece.html",
    "indonesia.html",
    "kazakhstan.html",
    "kyrgyzstan.html",
    "macedonia.html",
    "moldova.html",
    "moldovab.html",
    "montenegro.html",
    "philipines.html",
    "romania.html",
    "saudiarabia.html",
    "serbia.html",
    "tajikistan.html",
    "turkey.html",
    "turkmenistan.html",
]


def _download_file(url: str, output_file: Path) -> Path:
    response = requests.get(url, timeout=60, headers=_HEADERS)
    response.raise_for_status()
    output_file.write_text(response.text, encoding="utf-8")
    return output_file


def download(raw_data_dir: Path, force: bool = False) -> Path:
    """Download all 2021 country pages into raw directory."""
    raw_data_dir.mkdir(parents=True, exist_ok=True)

    # Download participants index
    index_file = raw_data_dir / PRIMARY_FILENAME
    if not index_file.exists() or force:
        _download_file(f"{_BASE_URL}participants.html", index_file)

    # Download each country page
    for page in COUNTRY_PAGES:
        output = raw_data_dir / f"jbmo_2021_{page}"
        if output.exists() and not force:
            continue
        try:
            _download_file(f"{_BASE_URL}{page}", output)
        except Exception as e:
            print(f"  Warning: could not download {page}: {e}")

    return index_file
