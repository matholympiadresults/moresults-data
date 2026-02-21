"""EGMO source adapter."""

import time
from pathlib import Path

import click

from data_processing.sources.egmo.ingester import ingest_egmo_data
from data_processing.sources.egmo.scraper import (
    FIRST_EGMO_YEAR,
    EGMOYearResults,
    ScraperError,
    download_raw,
    get_available_years,
    parse_raw,
    save_json,
)

from .base import SourceAdapter


class EGMOAdapter(SourceAdapter):
    """Adapter for EGMO (European Girls' Mathematical Olympiad) data."""

    name = "egmo"
    display_name = "EGMO"
    first_year = FIRST_EGMO_YEAR
    last_year = None  # Uses current year

    def download_raw(
        self,
        source_dir: Path,
        years: list[int] | None,
        force: bool,
    ) -> None:
        """Download raw EGMO data."""
        raw_base = self.get_raw_base_dir(source_dir)
        raw_base.mkdir(parents=True, exist_ok=True)

        available = get_available_years()
        target_years = years if years else available

        # Filter to available years
        target_years = [y for y in target_years if y in available]

        click.echo(f"Downloading {len(target_years)} years to {raw_base}")

        for year in target_years:
            try:
                download_raw(year, raw_base, force=force)
                click.echo(f"  {year}: Downloaded")
                time.sleep(0.5)  # Be nice to the server
            except ScraperError as e:
                click.echo(f"  {year}: {e}", err=True)

    def parse_raw(
        self,
        source_dir: Path,
        years: list[int] | None,
        force: bool,
    ) -> None:
        """Parse raw EGMO data."""
        raw_base = self.get_raw_base_dir(source_dir)

        # Find available raw years
        available_years = self.find_available_raw_years(source_dir)

        # Filter to years that have required files
        available_years = [
            y
            for y in available_years
            if (raw_base / str(y) / f"egmo_{y}_scoreboard.html").exists()
            and (raw_base / str(y) / f"egmo_{y}_scores.csv").exists()
        ]

        target_years = years if years else available_years
        target_years = [y for y in target_years if y in available_years]

        click.echo(f"Parsing {len(target_years)} years")

        for year in target_years:
            parsed_dir = self.get_parsed_dir(source_dir, year)
            output_file = parsed_dir / f"egmo_{year}.json"

            if output_file.exists() and not force:
                click.echo(f"  {year}: Already exists, skipping")
                continue

            try:
                parsed_dir.mkdir(parents=True, exist_ok=True)
                html_file = raw_base / str(year) / f"egmo_{year}_scoreboard.html"
                csv_file = raw_base / str(year) / f"egmo_{year}_scores.csv"
                data = parse_raw(year, html_file, csv_file)
                save_json(data, output_file)
                click.echo(f"  {year}: Parsed {data.total_contestants} contestants")
            except Exception as e:
                click.echo(f"  {year}: Failed - {e}", err=True)

    def ingest(
        self,
        source_dir: Path,
        output_path: Path,
        years: list[int] | None,
    ) -> None:
        """Ingest parsed EGMO data into the database."""
        parsed_base = self.get_parsed_base_dir(source_dir)

        if not parsed_base.exists():
            raise click.ClickException(f"Parsed data directory not found: {parsed_base}")

        ingest_egmo_data(parsed_base, output_path, years)

    def info(self, year: int, source_dir: Path) -> None:
        """Show summary info for a specific EGMO year."""
        parsed_dir = self.get_parsed_dir(source_dir, year)
        json_file = parsed_dir / f"egmo_{year}.json"

        if not json_file.exists():
            raise click.ClickException(f"Data file not found: {json_file}")

        data = EGMOYearResults.model_validate_json(json_file.read_text())

        click.echo(f"EGMO {data.year} (Edition {data.edition})")
        click.echo(f"Contestants: {data.total_contestants}")
        click.echo(f"Countries: {len(data.countries)}")
        click.echo(f"Problems: {data.num_problems}")
        click.echo()

        # Count awards
        award_counts: dict[str, int] = {}
        for r in data.results:
            if r.award:
                award_counts[r.award] = award_counts.get(r.award, 0) + 1

        for award in ["Gold Medal", "Silver Medal", "Bronze Medal", "Honourable Mention"]:
            if award in award_counts:
                click.echo(f"{award}: {award_counts[award]}")
