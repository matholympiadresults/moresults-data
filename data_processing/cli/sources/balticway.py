"""Baltic Way source adapter."""

import time
from pathlib import Path

import click

from data_processing.sources.balticway.downloader import (
    AVAILABLE_YEARS,
    DownloadError,
    download_year,
)

from .base import SourceAdapter

FIRST_BW_YEAR = min(AVAILABLE_YEARS)
LAST_BW_YEAR = max(AVAILABLE_YEARS)


class BalticWayAdapter(SourceAdapter):
    """Adapter for Baltic Way data.

    Implements the 3-stage pipeline:
    - download_raw: Downloads results (HTML/PDF) from math.olympiaadid.ut.ee
    - parse_raw: Not yet implemented
    - ingest: Not yet implemented
    """

    name = "balticway"
    display_name = "Baltic Way"
    first_year = FIRST_BW_YEAR
    last_year = LAST_BW_YEAR

    def get_available_years(self) -> range:
        """Get range of years with available data."""
        return range(self.first_year, self.last_year + 1)

    def download_raw(
        self,
        source_dir: Path,
        years: list[int] | None,
        force: bool,
    ) -> None:
        """Download results from math.olympiaadid.ut.ee."""
        if years is None:
            target_years = AVAILABLE_YEARS
        else:
            target_years = [y for y in years if y in AVAILABLE_YEARS]

        if not target_years:
            click.echo("No valid years specified for Baltic Way")
            click.echo(f"Available years: {AVAILABLE_YEARS[0]}-{AVAILABLE_YEARS[-1]}")
            return

        success_count = 0
        skip_count = 0
        fail_count = 0

        for year in target_years:
            raw_dir = self.get_raw_dir(source_dir, year)
            raw_file = raw_dir / "results.html"
            raw_pdf = raw_dir / "results.pdf"

            if (raw_file.exists() or raw_pdf.exists()) and not force:
                click.echo(f"  {year}: Skipped (already exists)")
                skip_count += 1
                continue

            try:
                download_year(year, raw_dir, force=force)
                click.echo(f"  {year}: Downloaded")
                success_count += 1

                time.sleep(1.0)
            except DownloadError as e:
                click.echo(f"  {year}: {e}", err=True)
                fail_count += 1

        click.echo()
        click.echo(f"Done: {success_count} downloaded, {skip_count} skipped, {fail_count} failed")

    def parse_raw(
        self,
        source_dir: Path,
        years: list[int] | None,
        force: bool,
    ) -> None:
        """Parse raw HTML/PDF results into structured JSON."""
        if years is not None and len(years) == 0:
            return

        from data_processing.sources.balticway.parser import ParserError, parse_year

        if years is None:
            target_years = AVAILABLE_YEARS
        else:
            target_years = [y for y in years if y in AVAILABLE_YEARS]

        if not target_years:
            click.echo("No valid years specified for Baltic Way")
            click.echo(f"Available years: {AVAILABLE_YEARS[0]}-{AVAILABLE_YEARS[-1]}")
            return

        success_count = 0
        skip_count = 0
        fail_count = 0

        for year in target_years:
            raw_dir = self.get_raw_dir(source_dir, year)
            parsed_dir = self.get_parsed_dir(source_dir, year)
            output_file = parsed_dir / "scoreboard.json"

            if output_file.exists() and not force:
                click.echo(f"  {year}: Skipped (already exists)")
                skip_count += 1
                continue

            try:
                parse_year(year, raw_dir, parsed_dir, force=force)
                click.echo(f"  {year}: Parsed")
                success_count += 1
            except FileNotFoundError:
                click.echo(f"  {year}: Raw file not found (run download first)", err=True)
                fail_count += 1
            except ParserError as e:
                click.echo(f"  {year}: {e}", err=True)
                fail_count += 1

        click.echo()
        click.echo(f"Done: {success_count} parsed, {skip_count} skipped, {fail_count} failed")

    def ingest(
        self,
        source_dir: Path,
        output_path: Path,
        years: list[int] | None,
    ) -> None:
        """Ingest parsed Baltic Way data into the database."""
        from data_processing.sources.balticway.ingester import ingest_balticway_data

        ingest_balticway_data(source_dir, output_path, years)
