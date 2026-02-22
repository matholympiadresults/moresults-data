"""APMO source adapter."""

from pathlib import Path

import click

from sigma.sources.apmo.downloader import download_raw_year
from sigma.sources.apmo.ingester import ingest_apmo_data
from sigma.sources.apmo.parser import APMOScoreboard, Award, parse_raw_year, save_json

from .base import SourceAdapter

# APMO started in 1989, but full online results from 2016
FIRST_APMO_YEAR = 1989
FIRST_ONLINE_YEAR = 2016


class APMOAdapter(SourceAdapter):
    """Adapter for APMO (Asian Pacific Mathematical Olympiad) data."""

    name = "apmo"
    display_name = "APMO"
    first_year = FIRST_ONLINE_YEAR  # Use first year with online data as default
    last_year = None  # Uses current year

    def download_raw(
        self,
        source_dir: Path,
        years: list[int] | None,
        force: bool,
    ) -> None:
        """Download raw APMO HTML files."""
        target_years = years if years else list(self.get_available_years())

        for year in target_years:
            raw_dir = self.get_raw_dir(source_dir, year)
            click.echo(f"Downloading APMO {year}...")

            try:
                downloaded = download_raw_year(year, raw_dir, force=force)
                if downloaded:
                    click.echo(f"  Downloaded {len(downloaded)} files to {raw_dir}")
                else:
                    click.echo("  Already exists (use --force to re-download)")
            except Exception as e:
                click.echo(f"  Error: {e}", err=True)

    def parse_raw(
        self,
        source_dir: Path,
        years: list[int] | None,
        force: bool,
    ) -> None:
        """Parse raw APMO HTML files to JSON."""
        target_years = years if years else list(self.get_available_years())

        for year in target_years:
            raw_dir = self.get_raw_dir(source_dir, year)
            parsed_dir = self.get_parsed_dir(source_dir, year)

            if not raw_dir.exists():
                click.echo(f"Skipping APMO {year}: raw data not found at {raw_dir}")
                continue

            output_path = parsed_dir / f"apmo_{year}.json"
            if not force and output_path.exists():
                click.echo(f"Parsing APMO {year}...")
                click.echo("  Already exists (use --force to re-parse)")
                continue

            click.echo(f"Parsing APMO {year}...")
            parsed_dir.mkdir(parents=True, exist_ok=True)

            try:
                scoreboard = parse_raw_year(year, raw_dir)
                save_json(scoreboard, output_path)
                click.echo(f"  Parsed to {output_path}")
            except Exception as e:
                click.echo(f"  Error: {e}", err=True)

    def ingest(
        self,
        source_dir: Path,
        output_path: Path,
        years: list[int] | None,
    ) -> None:
        """Ingest parsed APMO JSON data into the database."""
        # Find all parsed directories with data
        parsed_base = source_dir / self.name / "parsed"

        if not parsed_base.exists():
            raise click.ClickException(f"No parsed data found at {parsed_base}")

        # Collect all parsed JSON files
        all_json_files = sorted(parsed_base.glob("*/apmo_*.json"))

        if not all_json_files:
            raise click.ClickException(f"No parsed APMO JSON files found in {parsed_base}")

        # Filter by years if specified
        if years:
            year_set = set(years)
            all_json_files = [
                f for f in all_json_files if int(f.stem.replace("apmo_", "")) in year_set
            ]

        if not all_json_files:
            raise click.ClickException("No APMO files match the specified years")

        # Create a temporary directory structure for ingester
        # The ingester expects files in a flat directory
        click.echo(f"Ingesting {len(all_json_files)} APMO years...")

        # Use the parent parsed directory for ingestion
        ingest_apmo_data(
            data_dir=parsed_base,
            db_path=output_path,
            years=years,
        )

    def info(self, year: int, source_dir: Path) -> None:
        """Show summary info for a specific APMO year."""
        parsed_dir = self.get_parsed_dir(source_dir, year)
        json_file = parsed_dir / f"apmo_{year}.json"

        if not json_file.exists():
            raise click.ClickException(f"Data file not found: {json_file}")

        scoreboard = APMOScoreboard.model_validate_json(json_file.read_text())

        click.echo(f"APMO {scoreboard.year}")
        click.echo(f"Contestants: {len(scoreboard.contestants)}")
        click.echo(f"Countries: {len(scoreboard.countries)}")
        click.echo(f"Problems: {scoreboard.num_problems}")
        click.echo()

        for award in Award:
            count = len(scoreboard.get_by_award(award))
            if count:
                click.echo(f"{award.value}: {count}")
