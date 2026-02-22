"""IMO source adapter."""

from pathlib import Path

import click

from sigma.sources.imo.downloader import download_years
from sigma.sources.imo.ingester import ingest_years, print_database_stats
from sigma.sources.imo.parser import parse_years

from .base import SourceAdapter

# IMO started in 1959
FIRST_IMO_YEAR = 1959


class IMOAdapter(SourceAdapter):
    """Adapter for IMO (International Mathematical Olympiad) data.

    Pipeline:
    1. download_raw - Downloads raw HTML pages from imo-official.org
    2. parse_raw - Parses HTML into structured JSON
    3. ingest - Loads JSON into the normalized database
    """

    name = "imo"
    display_name = "IMO"
    first_year = FIRST_IMO_YEAR
    last_year = None  # Uses current year

    def download_raw(
        self,
        source_dir: Path,
        years: list[int] | None,
        force: bool,
    ) -> None:
        """Download raw HTML pages from imo-official.org."""
        available = list(self.get_available_years())

        if years is None:
            target_years = available
        else:
            target_years = [y for y in years if y in available]

        if not target_years:
            click.echo("No valid years specified for IMO")
            return

        raw_base = self.get_raw_base_dir(source_dir)
        stats = download_years(raw_base, target_years, force=force)

        click.echo()
        click.echo(
            f"Done: {stats['success']} downloaded, "
            f"{stats['skipped']} skipped, {stats['failed']} failed"
        )

    def parse_raw(
        self,
        source_dir: Path,
        years: list[int] | None,
        force: bool,
    ) -> None:
        """Parse raw HTML files into structured JSON."""
        raw_base = self.get_raw_base_dir(source_dir)
        parsed_base = self.get_parsed_base_dir(source_dir)

        stats = parse_years(raw_base, parsed_base, years=years, force=force)

        click.echo()
        click.echo(
            f"Done: {stats['success']} parsed, {stats['skipped']} skipped, {stats['failed']} failed"
        )

    def ingest(
        self,
        source_dir: Path,
        output_path: Path,
        years: list[int] | None,
    ) -> None:
        """Ingest parsed JSON data into the database."""
        parsed_base = self.get_parsed_base_dir(source_dir)
        db = ingest_years(parsed_base, output_path, years)
        print_database_stats(db)
