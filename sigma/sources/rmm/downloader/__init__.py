"""RMM download module - downloads raw HTML from rmms.lbi.ro."""

from .rmm_downloader import (
    AVAILABLE_YEARS,
    download_participants,
    download_year,
    fetch_page,
    fetch_participants_page,
)

__all__ = [
    "download_year",
    "download_participants",
    "fetch_page",
    "fetch_participants_page",
    "AVAILABLE_YEARS",
]
