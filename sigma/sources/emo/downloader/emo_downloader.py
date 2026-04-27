"""EMO raw data downloader.

The European Mathematical Olympiad (EMO) launched in 2026 in Lithuania
(emo2026.lt). Results are not yet published programmatically; raw CSV
files must currently be placed manually under ``data/emo/raw/<year>/``.
"""

from pathlib import Path

AVAILABLE_YEARS = [2026]

_SOURCE_URLS: dict[int, str] = {
    2026: "https://emo2026.lt",
}

_RAW_FILENAMES: dict[int, str] = {
    2026: "emo_2026_raw.csv",
}


class DownloadError(Exception):
    """Raised when downloading fails unexpectedly."""

    pass


def get_source_url(year: int) -> str:
    """Get the source URL for a given year."""
    if year not in _SOURCE_URLS:
        raise ValueError(
            f"No source URL available for year {year}. Available years: {AVAILABLE_YEARS}"
        )
    return _SOURCE_URLS[year]


def get_source_type(year: int) -> str:
    """Get the source type for a given year."""
    if year not in AVAILABLE_YEARS:
        raise ValueError(f"No source type available for year {year}.")
    return "csv"


def get_raw_filename(year: int) -> str:
    """Get the primary filename for storing raw data."""
    if year not in _RAW_FILENAMES:
        raise ValueError(
            f"No raw filename available for year {year}. Available years: {AVAILABLE_YEARS}"
        )
    return _RAW_FILENAMES[year]


def download_raw(year: int, raw_data_dir: Path, force: bool = False) -> Path:
    """Download raw data for a given year.

    EMO results are not currently available via a stable URL — raw CSV
    files must be placed under ``data/emo/raw/<year>/`` by hand. This
    function checks for the expected file and returns its path.
    """
    if year not in AVAILABLE_YEARS:
        raise DownloadError(
            f"No downloader available for year {year}. Available years: {AVAILABLE_YEARS}"
        )

    raw_file = raw_data_dir / get_raw_filename(year)
    if not raw_file.exists():
        raise DownloadError(
            f"EMO {year} raw file not found at {raw_file}. "
            f"Place the official results CSV at this path before parsing."
        )
    return raw_file
