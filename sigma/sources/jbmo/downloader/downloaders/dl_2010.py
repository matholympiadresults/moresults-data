"""JBMO 2010 downloader.

Downloads the official results PDF from the Wayback Machine archive
of fmi.unibuc.ro/jbmo2010. The original site is no longer available.
PDF contains 2 pages with 93 contestants (60 official + 31 invited + 2 reserve).
"""

from pathlib import Path

import requests

SOURCE_URL = "http://fmi.unibuc.ro/jbmo2010/14th_JBMO_official_results.pdf"
SOURCE_TYPE = "pdf"
PRIMARY_FILENAME = "jbmo_2010_raw.pdf"

_WAYBACK_URL = "https://web.archive.org/web/20100625/http://fmi.unibuc.ro:80/jbmo2010/14th_JBMO_official_results.pdf"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def download(raw_data_dir: Path, force: bool = False) -> Path:
    """Download the 2010 results PDF from the Wayback Machine."""
    raw_data_dir.mkdir(parents=True, exist_ok=True)
    output_file = raw_data_dir / PRIMARY_FILENAME

    if output_file.exists() and not force:
        return output_file

    response = requests.get(_WAYBACK_URL, timeout=60, headers=_HEADERS)
    response.raise_for_status()
    output_file.write_bytes(response.content)
    return output_file
