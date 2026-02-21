"""BMO raw data downloader.

Downloads raw HTML and PDF files from various Balkan Mathematical Olympiad sources.
"""

from pathlib import Path

import requests

# Available years with their parser types
# Note: 2015 is excluded because the source only has contestant codes, not names
AVAILABLE_YEARS = [2018, 2020, 2021, 2022, 2023, 2024, 2025]

# Years that use PDF sources
PDF_YEARS = {2020, 2021, 2022, 2025}

# Source URLs by year
YEAR_SOURCES: dict[int, str] = {
    # HTML sources
    2018: "https://bmo2018.dms.rs/results/",
    2023: "https://bmo2023.tubitak.gov.tr/results",
    2024: "https://bmo2024.org/results/",
    # PDF sources
    2025: "https://bmo2025.pmf.unsa.ba/wp-content/uploads/2025/04/BMO2025-Official-Results.pdf",
    2022: "https://cdn.b3web.xyz/web/cms/optimizedBMO2022results_Medals.pdf1652185269.pdf",
    2021: "https://cdn.b3web.xyz/web/cms/optimizedBMO2021-Medalsforwebsite.pdf1631272290.pdf",
    2020: "https://bmo2020.ssmr.ro/sites/bmo2020.ssmr.ro/files/results_bmov.pdf",
}


class DownloadError(Exception):
    """Raised when downloading fails unexpectedly."""

    pass


def get_source_url(year: int) -> str:
    """Get the source URL for a given year."""
    if year not in YEAR_SOURCES:
        raise ValueError(
            f"No source URL available for year {year}. Available years: {AVAILABLE_YEARS}"
        )
    return YEAR_SOURCES[year]


def get_source_type(year: int) -> str:
    """Get the source type ('html' or 'pdf') for a given year."""
    return "pdf" if year in PDF_YEARS else "html"


def get_raw_filename(year: int) -> str:
    """Get the filename for storing raw data."""
    ext = "pdf" if year in PDF_YEARS else "html"
    return f"bmo_{year}_raw.{ext}"


def download_raw(year: int, raw_data_dir: Path, force: bool = False) -> Path:
    """Download raw data for a given year.

    Args:
        year: The competition year
        raw_data_dir: Directory to store raw data files
        force: If True, re-download even if file exists

    Returns:
        Path to the downloaded file

    Raises:
        DownloadError: If download fails
    """
    url = get_source_url(year)
    output_file = raw_data_dir / get_raw_filename(year)

    if output_file.exists() and not force:
        return output_file

    raw_data_dir.mkdir(parents=True, exist_ok=True)

    try:
        if year in PDF_YEARS:
            # Use browser-like headers to avoid 403 errors on some servers
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = requests.get(url, timeout=60, headers=headers)
            response.raise_for_status()
            output_file.write_bytes(response.content)
        else:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            output_file.write_text(response.text, encoding="utf-8")
    except Exception as e:
        raise DownloadError(f"Failed to download data for year {year}: {e}") from e

    return output_file
