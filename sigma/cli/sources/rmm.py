"""RMM source adapter."""

import time
from pathlib import Path

import click

from sigma.sources.rmm.downloader import AVAILABLE_YEARS, download_participants, download_year
from sigma.sources.rmm.downloader.rmm_downloader import DownloadError
from sigma.sources.rmm.parser import ParseError, parse_participants_html, parse_year
from sigma.sources.rmm.parser.rmm_parser import load_html, save_json

from .base import SourceAdapter

# RMM started in 2008
FIRST_RMM_YEAR = 2008
LAST_RMM_YEAR = 2025


class RMMAdapter(SourceAdapter):
    """Adapter for RMM (Romanian Masters of Mathematics) data."""

    name = "rmm"
    display_name = "RMM"
    first_year = FIRST_RMM_YEAR
    last_year = LAST_RMM_YEAR

    def get_available_years(self) -> range:
        """Get range of years with available data."""
        return range(self.first_year, self.last_year + 1)

    def download_raw(
        self,
        source_dir: Path,
        years: list[int] | None,
        force: bool,
    ) -> None:
        """Download raw RMM data (HTML files) to rmm/raw/{year}/."""
        # Determine years to download
        if years is None:
            years = [y for y in self.get_available_years() if y in AVAILABLE_YEARS]
        else:
            years = [y for y in years if y in AVAILABLE_YEARS]

        click.echo(f"Downloading {len(years)} years")

        success = 0
        failed = 0
        for year in years:
            year_dir = self.get_raw_dir(source_dir, year)
            year_dir.mkdir(parents=True, exist_ok=True)
            output_file = year_dir / f"rmm_{year}.html"

            if output_file.exists() and not force:
                click.echo(f"  {year}: Already exists, skipping")
                success += 1
                continue

            try:
                download_year(year, year_dir, force)
                click.echo(f"  {year}: Downloaded results")
                time.sleep(1)  # Be nice to the server
                # Also download participants page
                participants_file = year_dir / f"rmm_{year}_participants.html"
                if not participants_file.exists() or force:
                    try:
                        download_participants(year, year_dir, force)
                        click.echo(f"  {year}: Downloaded participants")
                        time.sleep(1)
                    except DownloadError:
                        click.echo(f"  {year}: No participants page available")
                success += 1
            except DownloadError as e:
                click.echo(f"  {year}: {e}", err=True)
                failed += 1

        click.echo(f"Done: {success} successful, {failed} failed")

    def parse_raw(
        self,
        source_dir: Path,
        years: list[int] | None,
        force: bool,
    ) -> None:
        """Parse raw RMM HTML files from rmm/raw/{year}/ to rmm/parsed/{year}/."""
        raw_base = self.get_raw_base_dir(source_dir)

        # Find years to parse
        if years:
            years_to_parse = years
        else:
            # Find all year directories
            years_to_parse = sorted(
                int(d.name) for d in raw_base.iterdir() if d.is_dir() and d.name.isdigit()
            )

        if not years_to_parse:
            raise click.ClickException(f"No year directories found in {raw_base}")

        click.echo(f"Parsing {len(years_to_parse)} years")

        success = 0
        failed = 0
        for year in years_to_parse:
            raw_year_dir = self.get_raw_dir(source_dir, year)
            parsed_year_dir = self.get_parsed_dir(source_dir, year)
            html_file = raw_year_dir / f"rmm_{year}.html"
            output_file = parsed_year_dir / f"rmm_{year}.json"

            if not html_file.exists():
                click.echo(f"  {year}: No HTML file found, skipping")
                continue

            if output_file.exists() and not force:
                click.echo(f"  {year}: Already parsed, skipping")
                success += 1
                continue

            try:
                parsed_year_dir.mkdir(parents=True, exist_ok=True)
                html = load_html(html_file)
                # Load participants page if available (for multi-word name resolution)
                participants = None
                participants_file = raw_year_dir / f"rmm_{year}_participants.html"
                if participants_file.exists():
                    participants_html = load_html(participants_file)
                    participants = parse_participants_html(participants_html)
                data = parse_year(html, year, participants)
                save_json(data, output_file)
                click.echo(f"  {year}: Parsed {data.total_contestants} contestants")
                success += 1
            except ParseError as e:
                click.echo(f"  {year}: {e}", err=True)
                failed += 1

        click.echo(f"Done: {success} successful, {failed} failed")

    def ingest(
        self,
        source_dir: Path,
        output_path: Path,
        years: list[int] | None,
    ) -> None:
        """Ingest parsed RMM JSON data from rmm/parsed/{year}/ into the database."""
        parsed_base = self.get_parsed_base_dir(source_dir)

        if not parsed_base.exists():
            raise click.ClickException(f"Parsed directory not found: {parsed_base}")

        # Find years to ingest
        if years:
            years_to_ingest = years
        else:
            years_to_ingest = sorted(
                int(d.name) for d in parsed_base.iterdir() if d.is_dir() and d.name.isdigit()
            )

        if not years_to_ingest:
            raise click.ClickException(f"No year directories found in {parsed_base}")

        click.echo(f"Ingesting {len(years_to_ingest)} years")

        # Collect all JSON files for ingestion
        from sigma.database import create_empty_database, load_database, save_database
        from sigma.sources.rmm.ingester.rmm_ingester import (
            ingest_year_results,
            load_year_results_from_file,
        )

        # Load or create database
        if output_path.exists():
            db = load_database(output_path)
        else:
            db = create_empty_database()

        for year in years_to_ingest:
            json_file = self.get_parsed_dir(source_dir, year) / f"rmm_{year}.json"
            if not json_file.exists():
                click.echo(f"  {year}: No parsed file found, skipping")
                continue

            year_results = load_year_results_from_file(json_file)
            stats = ingest_year_results(db, year_results)

            skipped_parts = []
            if stats["skipped_online"]:
                skipped_parts.append(f"{stats['skipped_online']} online")
            if stats["skipped_secondary_teams"]:
                skipped_parts.append(f"{stats['skipped_secondary_teams']} secondary ROU teams")
            skipped_str = f", skipped: {', '.join(skipped_parts)}" if skipped_parts else ""

            click.echo(
                f"  {year}: {stats['contestants']} contestants "
                f"({stats['new_people']} new, {stats['matched_people']} matched{skipped_str})"
            )

        save_database(db, output_path)
        click.echo(f"\nDatabase saved to {output_path}")
        click.echo(
            f"  {len(db.competitions)} competitions, {len(db.people)} people, {len(db.participations)} participations"
        )

    def info(self, year: int, source_dir: Path) -> None:
        """Show summary info for a specific RMM year."""
        from sigma.sources.rmm.parser.models import RMMYearResults

        json_file = self.get_parsed_dir(source_dir, year) / f"rmm_{year}.json"

        if not json_file.exists():
            raise click.ClickException(f"Data file not found: {json_file}")

        data = RMMYearResults.model_validate_json(json_file.read_text())

        click.echo(f"RMM {year}")
        click.echo(f"Contestants: {data.total_contestants}")

        # Count by award
        awards: dict[str, int] = {}
        for r in data.results:
            if r.award:
                awards[r.award] = awards.get(r.award, 0) + 1

        click.echo()
        for award, count in sorted(awards.items()):
            click.echo(f"{award}: {count}")
