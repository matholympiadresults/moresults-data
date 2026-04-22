"""JBMO 2023 downloader.

Downloads from jbmo2023.al:
- Overall results PDF (all contestants, scores, no names)
- Medals PDF (medalists with names and awards)
- Per-country team pages (contestant names for all teams)
"""

from pathlib import Path

import requests

SOURCE_URL = "https://jbmo2023.al/media/filer_public/68/ae/68ae67f2-eff9-4f7d-a4e7-6cc15f729133/overall-results.pdf"
SOURCE_TYPE = "pdf"
PRIMARY_FILENAME = "jbmo_2023_overall.pdf"

_MEDALS_URL = "https://jbmo2023.al/media/filer_public/13/ec/13ecddbe-98c2-4dce-94e3-16fb7c475556/jbmo_2023_final_results_-_medals.pdf"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Team pages with contestant names (Greece and Montenegro are broken/empty)
_TEAM_BASE_URL = "https://jbmo2023.al/"
_TEAM_PAGES: dict[str, str] = {
    "albania": "albania-results/",
    "albania_b": "albania-b-results/",
    "bosnia": "bosnia-and-herzegovina-results/",
    "bulgaria": "bulgaria-results/",
    "cyprus": "cyprus-results/",
    "north_macedonia": "republic-of-north-macedonia-results/",
    "moldova": "republic-of-moldova-results/",
    "romania": "romania-results/",
    "serbia": "serbia-results/",
    "turkiye": "turkiye-results/",
    "azerbaijan": "azerbaijan-aze-results/",
    "croatia": "croatia-results/",
    "france": "france-results/",
    "kazakhstan": "kazakhstan-results/",
    "kyrgyzstan": "kyrgyzstan-results/",
    "saudi_arabia": "saudi-arabia-results/",
    "tajikistan": "tajikistan-results/",
    "turkmenistan": "turkmenistan-results/",
}


def _download_binary(url: str, output_file: Path) -> Path:
    response = requests.get(url, timeout=60, headers=_HEADERS)
    response.raise_for_status()
    output_file.write_bytes(response.content)
    return output_file


def _download_text(url: str, output_file: Path) -> Path:
    response = requests.get(url, timeout=60, headers=_HEADERS)
    response.raise_for_status()
    output_file.write_text(response.text, encoding="utf-8")
    return output_file


def download(raw_data_dir: Path, force: bool = False) -> Path:
    """Download all 2023 data files."""
    raw_data_dir.mkdir(parents=True, exist_ok=True)

    # Overall results PDF
    overall_file = raw_data_dir / PRIMARY_FILENAME
    if not overall_file.exists() or force:
        _download_binary(SOURCE_URL, overall_file)

    # Medals PDF
    medals_file = raw_data_dir / "jbmo_2023_medals.pdf"
    if not medals_file.exists() or force:
        _download_binary(_MEDALS_URL, medals_file)

    # Team pages for contestant names
    for team_key, page_path in _TEAM_PAGES.items():
        output = raw_data_dir / f"jbmo_2023_team_{team_key}.html"
        if output.exists() and not force:
            continue
        try:
            _download_text(f"{_TEAM_BASE_URL}{page_path}", output)
        except Exception as e:
            print(f"  Warning: could not download {team_key} team page: {e}")

    return overall_file
