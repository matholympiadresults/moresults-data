"""RMM download module - downloads raw HTML from rmms.lbi.ro."""

from .downloader import AVAILABLE_YEARS, download_year, fetch_page

__all__ = ["download_year", "fetch_page", "AVAILABLE_YEARS"]
