"""BMO raw data downloader.

Downloads raw HTML and PDF files from various Balkan Mathematical Olympiad sources.
Some older years are bundled locally (pass-through) because the originals have
vanished from the web or were only ever shared as spreadsheets/multi-file HTML
site dumps.
"""

from pathlib import Path

import requests

# Available years with their parser types.
# Excluded years are documented in sigma/sources/bmo/README.md (missing
# contestant names, missing per-problem scores, etc.).
AVAILABLE_YEARS = [
    2005,
    2008,
    2009,
    2010,
    2011,
    2014,
    2015,
    2016,
    2017,
    2018,
    2019,
    2020,
    2021,
    2022,
    2023,
    2024,
    2025,
    2026,
]

# Years that use PDF sources
PDF_YEARS = {2008, 2009, 2010, 2014, 2016, 2020, 2021, 2022, 2025, 2026}

# Years with pass-through downloaders. Raw files are bundled in the repo under
# data/bmo/raw/<year>/ and are NOT fetched over the network.
LOCAL_YEARS: dict[int, str] = {
    2005: "BalkanResults.xls",
    2009: "RESULTS_BMO_2009.pdf",
    2010: "Official_Results_BMO_2010.pdf",
    2011: "results.html",
    2014: "individual-results.pdf",
    2015: "sgalb.htm",
    2016: "bmo2016_results.pdf",
    2017: "results-total.html",
    2019: "results.html",
}

# Source URLs by year (informational, stored alongside parsed results).
YEAR_SOURCES: dict[int, str] = {
    # Bundled / pass-through
    2005: "local:balkan-mo-2005",
    2009: "local:balkan-mo-2009",
    2010: "local:balkan-mo-2010-official-pdf",
    2011: "local:balkan-mo-2011",
    2014: "local:balkan-mo-2014",
    2015: "local:balkan-mo-2015",
    2016: "local:balkan-mo-2016",
    2017: "local:balkan-mo-2017",
    2019: "local:balkan-mo-2019",
    # HTML sources
    2018: "https://bmo2018.dms.rs/results/",
    2023: "https://bmo2023.tubitak.gov.tr/results",
    2024: "https://bmo2024.org/results/",
    # PDF sources
    2008: "https://matematickitalent.mk/uploads/books/i77ZsGyCqEeVJ_JkreZPuw.pdf",
    2025: "https://bmo2025.pmf.unsa.ba/wp-content/uploads/2025/04/BMO2025-Official-Results.pdf",
    2022: "https://cdn.b3web.xyz/web/cms/optimizedBMO2022results_Medals.pdf1652185269.pdf",
    2021: "https://cdn.b3web.xyz/web/cms/optimizedBMO2021-Medalsforwebsite.pdf1631272290.pdf",
    2020: "https://bmo2020.ssmr.ro/sites/bmo2020.ssmr.ro/files/results_bmov.pdf",
    2026: "https://hms.gr/43bmo2026/pdf/BMO2026_all_countries_contestant.pdf",
}

# Auxiliary team-roster pages for 2026. The official site publishes scores
# only as a code-keyed PDF (BMO2026_all_countries_contestant.pdf), so we
# fetch each delegation's team-page HTML and pair the i-th contestant in
# the page with code <COUNTRY><i>. Filename in the raw dir → URL path
# under https://hms.gr/43bmo2026/.
BMO_2026_TEAM_FILES: dict[str, str] = {
    "teamAlbania.html": "team/teamAlbania.html",
    "teamBosnia.html": "team/teamBosnia.html",
    "teamBulgaria.html": "team/teamBulgaria.html",
    "teamCyprus.html": "team/teamCyprus.html",
    "teamHellas.html": "team/teamHellas.html",
    "teamMoldova.html": "team/teamMoldova.html",
    "teamMontenegro.html": "team/teamMontenegro.html",
    "teamNorth_Macedonia.html": "team/teamNorth_Macedonia.html",
    "teamRomania.html": "team/teamRomania.html",
    "teamserbia.html": "team/teamserbia.html",
    "teamTurkey.html": "team/teamTurkey.html",
    "teamalgeria.html": "team/teamalgeria.html",
    "teamazerbaijan.html": "team/teamazerbaijan.html",
    "teamGeorgia.html": "team/teamGeorgia.html",
    "teamfrance.html": "team/teamfrance.html",
    "teamHellasGest.html": "team/teamHellasGest.html",
    "teamitalia.html": "team/teamitalia.html",
    "teamkazakstan.html": "team/teamkazakstan.html",
    "teamKyrgyzstan.html": "team/teamKyrgyzstan.html",
    "teamLithuania.html": "team/teamLithuania.html",
    "teamMalaysia.html": "team/teamMalaysia.html",
    "teamSaudi_Arabia.html": "team/teamSaudi_Arabia.html",
    "teamTurkmenistan.html": "team/teamTurkmenistan.html",
    "teamUnited_Kingdom.html": "team/teamUnited Kingdom.html",
    "teamUzbekistan.html": "team/teamUzbekistan.html",
}
BMO_2026_BASE_URL = "https://hms.gr/43bmo2026/"


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
    """Get the source type ('html', 'pdf', or 'xls') for a given year."""
    if year == 2005:
        return "xls"
    if year in PDF_YEARS:
        return "pdf"
    return "html"


def get_raw_filename(year: int) -> str:
    """Get the primary filename for the year's raw data.

    For multi-file years (e.g. 2008's per-country HTML dump), this returns the
    canonical "index" file; parsers use `raw_file.parent` to locate siblings.
    """
    if year in LOCAL_YEARS:
        return LOCAL_YEARS[year]
    ext = "pdf" if year in PDF_YEARS else "html"
    return f"bmo_{year}_raw.{ext}"


def download_raw(year: int, raw_data_dir: Path, force: bool = False) -> Path:
    """Download raw data for a given year.

    For LOCAL_YEARS this is a pass-through — the caller is expected to have the
    raw files already present in `raw_data_dir` (shipped inside the repo).

    Args:
        year: The competition year
        raw_data_dir: Directory to store raw data files
        force: If True, re-download even if file exists

    Returns:
        Path to the primary raw file for the year

    Raises:
        DownloadError: If download fails or a bundled file is missing
    """
    output_file = raw_data_dir / get_raw_filename(year)

    if year in LOCAL_YEARS:
        if not output_file.exists():
            raise DownloadError(
                f"Bundled raw data for BMO {year} not found at {output_file}. "
                f"These files are shipped with the repo; check your checkout."
            )
        return output_file

    url = get_source_url(year)

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

    if year == 2026:
        _download_2026_team_pages(raw_data_dir, force=force)

    return output_file


def _download_2026_team_pages(raw_data_dir: Path, *, force: bool) -> None:
    """Fetch the per-country team rosters that pair with the 2026 scores PDF."""
    for filename, path in BMO_2026_TEAM_FILES.items():
        target = raw_data_dir / filename
        if target.exists() and not force:
            continue
        url = BMO_2026_BASE_URL + path
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            target.write_text(response.text, encoding="utf-8")
        except Exception as e:
            raise DownloadError(f"Failed to download {url}: {e}") from e
