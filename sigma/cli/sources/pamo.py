"""PAMO source adapter with 3-stage pipeline (download/parse/ingest)."""

import time
from pathlib import Path

import click

from sigma.sources.pamo.downloader import (
    AVAILABLE_YEARS,
    DownloadError,
    download_year,
    get_raw_filename,
)
from sigma.sources.pamo.ingester.pamo_ingester import ingest_pamo_data
from sigma.sources.pamo.parser import ParserError, parse_year

from .base import SourceAdapter

# PAMO available years
FIRST_PAMO_YEAR = min(AVAILABLE_YEARS)
LAST_PAMO_YEAR = max(AVAILABLE_YEARS)


class PAMOAdapter(SourceAdapter):
    """Adapter for PAMO (Pan African Mathematics Olympiad) data.

    Implements the 3-stage pipeline:
    - download_raw: Downloads raw results data from pamoofficial.org
    - parse_raw: Parses HTML into structured JSON
    - ingest: Loads JSON into the database
    """

    name = "pamo"
    display_name = "PAMO"
    first_year = FIRST_PAMO_YEAR
    last_year = LAST_PAMO_YEAR

    def get_available_years(self) -> range:
        """Get range of years with available data."""
        return range(self.first_year, self.last_year + 1)

    def download_raw(
        self,
        source_dir: Path,
        years: list[int] | None,
        force: bool,
    ) -> None:
        """Download raw results data from pamoofficial.org."""
        if years is None:
            target_years = AVAILABLE_YEARS
        else:
            target_years = [y for y in years if y in AVAILABLE_YEARS]

        if not target_years:
            click.echo("No valid years specified for PAMO")
            click.echo(f"Available years: {AVAILABLE_YEARS}")
            return

        success_count = 0
        skip_count = 0
        fail_count = 0

        for year in target_years:
            raw_dir = self.get_raw_dir(source_dir, year)
            raw_file = raw_dir / get_raw_filename(year)

            if raw_file.exists() and not force:
                click.echo(f"  {year}: Skipped (already exists)")
                skip_count += 1
                continue

            try:
                download_year(year, raw_dir, force=force)
                click.echo(f"  {year}: Downloaded")
                success_count += 1

                # Be polite to the server
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
        """Parse raw results data into structured JSON."""
        if years is None:
            target_years = AVAILABLE_YEARS
        else:
            target_years = [y for y in years if y in AVAILABLE_YEARS]

        if not target_years:
            click.echo("No valid years specified for PAMO")
            click.echo(f"Available years: {AVAILABLE_YEARS}")
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
        """Ingest parsed PAMO data into the database."""
        ingest_pamo_data(source_dir, output_path, years)
