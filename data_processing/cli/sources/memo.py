"""MEMO source adapter with 3-stage pipeline (download/parse/ingest)."""

import time
from pathlib import Path

import click

from data_processing.sources.memo.downloader import (
    AVAILABLE_YEARS,
    TEAM_AVAILABLE_YEARS,
    DownloadError,
    download_team_year,
    download_year,
)
from data_processing.sources.memo.ingester.memo_ingester import (
    ingest_memo_data,
    ingest_memo_team_data,
)
from data_processing.sources.memo.parser import (
    ParserError,
    TeamParserError,
    parse_team_year,
    parse_year,
)

from .base import SourceAdapter

# MEMO editions 1 (2007) and 9-19 (2015-2025) have online results
FIRST_MEMO_YEAR = 2007
LAST_MEMO_YEAR = 2025


class MEMOAdapter(SourceAdapter):
    """Adapter for MEMO (Middle European Mathematical Olympiad) data.

    Implements the 3-stage pipeline:
    - download_raw: Downloads raw HTML from memo-official.org
    - parse_raw: Parses HTML into structured JSON
    - ingest: Loads JSON into the database
    """

    name = "memo"
    display_name = "MEMO"
    first_year = FIRST_MEMO_YEAR
    last_year = LAST_MEMO_YEAR

    def get_available_years(self) -> range:
        """Get range of years with available data (limited for MEMO)."""
        return range(self.first_year, self.last_year + 1)

    def download_raw(
        self,
        source_dir: Path,
        years: list[int] | None,
        force: bool,
    ) -> None:
        """Download raw HTML from memo-official.org (individual and team)."""
        if years is None:
            target_years = AVAILABLE_YEARS
        else:
            target_years = [y for y in years if y in AVAILABLE_YEARS]

        if not target_years:
            click.echo("No valid years specified for MEMO")
            click.echo(f"Available years: {AVAILABLE_YEARS[0]}-{AVAILABLE_YEARS[-1]}")
            return

        # Download individual results
        click.echo("Downloading individual results:")
        ind_success = 0
        ind_skip = 0
        ind_fail = 0

        for year in target_years:
            raw_dir = self.get_raw_dir(source_dir, year)
            raw_file = raw_dir / "individual.html"

            if raw_file.exists() and not force:
                click.echo(f"  {year}: Skipped (already exists)")
                ind_skip += 1
                continue

            try:
                download_year(year, raw_dir, force=force)
                click.echo(f"  {year}: Downloaded")
                ind_success += 1
                time.sleep(1.0)
            except DownloadError as e:
                click.echo(f"  {year}: {e}", err=True)
                ind_fail += 1

        click.echo(f"Individual: {ind_success} downloaded, {ind_skip} skipped, {ind_fail} failed")

        # Download team results (only for years with team data)
        team_years = [y for y in target_years if y in TEAM_AVAILABLE_YEARS]
        if team_years:
            click.echo("\nDownloading team results:")
            team_success = 0
            team_skip = 0
            team_fail = 0

            for year in team_years:
                raw_dir = self.get_raw_dir(source_dir, year)
                raw_file = raw_dir / "team.html"

                if raw_file.exists() and not force:
                    click.echo(f"  {year}: Skipped (already exists)")
                    team_skip += 1
                    continue

                try:
                    download_team_year(year, raw_dir, force=force)
                    click.echo(f"  {year}: Downloaded")
                    team_success += 1
                    time.sleep(1.0)
                except DownloadError as e:
                    click.echo(f"  {year}: {e}", err=True)
                    team_fail += 1

            click.echo(f"Team: {team_success} downloaded, {team_skip} skipped, {team_fail} failed")

    def parse_raw(
        self,
        source_dir: Path,
        years: list[int] | None,
        force: bool,
    ) -> None:
        """Parse raw HTML into structured JSON (individual and team)."""
        if years is None:
            target_years = AVAILABLE_YEARS
        else:
            target_years = [y for y in years if y in AVAILABLE_YEARS]

        if not target_years:
            click.echo("No valid years specified for MEMO")
            click.echo(f"Available years: {AVAILABLE_YEARS[0]}-{AVAILABLE_YEARS[-1]}")
            return

        # Parse individual results
        click.echo("Parsing individual results:")
        ind_success = 0
        ind_skip = 0
        ind_fail = 0

        for year in target_years:
            raw_dir = self.get_raw_dir(source_dir, year)
            parsed_dir = self.get_parsed_dir(source_dir, year)
            output_file = parsed_dir / "scoreboard.json"

            if output_file.exists() and not force:
                click.echo(f"  {year}: Skipped (already exists)")
                ind_skip += 1
                continue

            try:
                parse_year(year, raw_dir, parsed_dir, force=force)
                click.echo(f"  {year}: Parsed")
                ind_success += 1
            except FileNotFoundError:
                click.echo(f"  {year}: Raw HTML not found (run download first)", err=True)
                ind_fail += 1
            except ParserError as e:
                click.echo(f"  {year}: {e}", err=True)
                ind_fail += 1

        click.echo(f"Individual: {ind_success} parsed, {ind_skip} skipped, {ind_fail} failed")

        # Parse team results (only for years with team data)
        team_years = [y for y in target_years if y in TEAM_AVAILABLE_YEARS]
        if team_years:
            click.echo("\nParsing team results:")
            team_success = 0
            team_skip = 0
            team_fail = 0

            for year in team_years:
                raw_dir = self.get_raw_dir(source_dir, year)
                parsed_dir = self.get_parsed_dir(source_dir, year)
                output_file = parsed_dir / "team_scoreboard.json"

                if output_file.exists() and not force:
                    click.echo(f"  {year}: Skipped (already exists)")
                    team_skip += 1
                    continue

                try:
                    parse_team_year(year, raw_dir, parsed_dir, force=force)
                    click.echo(f"  {year}: Parsed")
                    team_success += 1
                except FileNotFoundError:
                    click.echo(f"  {year}: Team raw HTML not found (run download first)", err=True)
                    team_fail += 1
                except TeamParserError as e:
                    click.echo(f"  {year}: {e}", err=True)
                    team_fail += 1

            click.echo(f"Team: {team_success} parsed, {team_skip} skipped, {team_fail} failed")

    def ingest(
        self,
        source_dir: Path,
        output_path: Path,
        years: list[int] | None,
    ) -> None:
        """Ingest parsed MEMO data (individual and team) into the database."""
        # Ingest individual data
        click.echo("Ingesting individual results:")
        ingest_memo_data(source_dir, output_path, years)

        # Ingest team data
        click.echo("\nIngesting team results:")
        ingest_memo_team_data(source_dir, output_path, years)
