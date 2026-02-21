"""BMO (Balkan Mathematical Olympiad) source adapter."""

from pathlib import Path

import click

from data_processing.sources.bmo.downloader import (
    AVAILABLE_YEARS,
    download_raw,
    get_raw_filename,
)
from data_processing.sources.bmo.ingester.bmo_ingester import ingest_bmo_data
from data_processing.sources.bmo.parser import (
    BMOYearResults,
    parse_raw,
    save_json,
)

from .base import SourceAdapter

# BMO available years (not contiguous)
FIRST_BMO_YEAR = min(AVAILABLE_YEARS)
LAST_BMO_YEAR = max(AVAILABLE_YEARS)


class BMOAdapter(SourceAdapter):
    """Adapter for BMO (Balkan Mathematical Olympiad) data."""

    name = "bmo"
    display_name = "BMO"
    first_year = FIRST_BMO_YEAR
    last_year = LAST_BMO_YEAR

    def get_available_years(self) -> range:
        """Get range of years with available data."""
        return range(self.first_year, self.last_year + 1)

    def _get_valid_years(self, years: list[int] | None) -> list[int]:
        """Filter years to only those that have parsers available."""
        if years:
            valid = [y for y in years if y in AVAILABLE_YEARS]
            invalid = [y for y in years if y not in AVAILABLE_YEARS]
            if invalid:
                click.echo(f"Warning: No data available for years: {invalid}")
            return valid
        return AVAILABLE_YEARS

    def download_raw(
        self,
        source_dir: Path,
        years: list[int] | None,
        force: bool,
    ) -> None:
        """Download raw BMO data (HTML or PDF files)."""
        target_years = self._get_valid_years(years)

        for year in target_years:
            raw_dir = self.get_raw_dir(source_dir, year)
            raw_dir.mkdir(parents=True, exist_ok=True)
            click.echo(f"Downloading BMO {year}...")

            try:
                raw_file = download_raw(year, raw_dir, force=force)
                click.echo(f"  Downloaded to {raw_file}")
            except Exception as e:
                click.echo(f"  Error: {e}", err=True)

    def parse_raw(
        self,
        source_dir: Path,
        years: list[int] | None,
        force: bool,
    ) -> None:
        """Parse raw BMO data to JSON."""
        target_years = self._get_valid_years(years)

        for year in target_years:
            raw_dir = self.get_raw_dir(source_dir, year)
            parsed_dir = self.get_parsed_dir(source_dir, year)

            if not raw_dir.exists():
                click.echo(f"Skipping BMO {year}: raw data not found at {raw_dir}")
                continue

            parsed_dir.mkdir(parents=True, exist_ok=True)
            output_file = parsed_dir / f"bmo_{year}.json"

            if output_file.exists() and not force:
                click.echo(f"Skipping BMO {year}: already parsed (use --force to re-parse)")
                continue

            click.echo(f"Parsing BMO {year}...")

            try:
                raw_file = raw_dir / get_raw_filename(year)
                if not raw_file.exists():
                    click.echo(f"  Skipping: raw file not found at {raw_file}", err=True)
                    continue

                result = parse_raw(year, raw_file)
                save_json(result, str(output_file))
                click.echo(f"  Parsed {result.total_contestants} contestants to {output_file}")
            except Exception as e:
                click.echo(f"  Error: {e}", err=True)

    def ingest(
        self,
        source_dir: Path,
        output_path: Path,
        years: list[int] | None,
    ) -> None:
        """Ingest parsed BMO JSON data into the database."""
        parsed_base = source_dir / self.name / "parsed"

        if not parsed_base.exists():
            raise click.ClickException(f"No parsed data found at {parsed_base}")

        # Collect all parsed JSON files
        all_json_files = sorted(parsed_base.glob("*/bmo_*.json"))

        if not all_json_files:
            raise click.ClickException(f"No parsed BMO JSON files found in {parsed_base}")

        # Filter by years if specified
        if years:
            year_set = set(years)
            all_json_files = [
                f for f in all_json_files if int(f.stem.replace("bmo_", "")) in year_set
            ]

        if not all_json_files:
            raise click.ClickException("No BMO files match the specified years")

        click.echo(f"Ingesting {len(all_json_files)} BMO years...")

        ingest_bmo_data(
            data_dir=parsed_base,
            db_path=output_path,
            years=years,
        )

    def info(self, year: int, source_dir: Path) -> None:
        """Show summary info for a specific BMO year."""
        parsed_dir = self.get_parsed_dir(source_dir, year)
        json_file = parsed_dir / f"bmo_{year}.json"

        if not json_file.exists():
            raise click.ClickException(f"Data file not found: {json_file}")

        result = BMOYearResults.model_validate_json(json_file.read_text())

        click.echo(f"BMO {result.year}")
        click.echo(f"Contestants: {result.total_contestants}")
        click.echo(f"Source: {result.source_type} ({result.source_url})")
        click.echo()

        # Count awards
        awards = {}
        for contestant in result.results:
            if contestant.award:
                awards[contestant.award] = awards.get(contestant.award, 0) + 1

        for award, count in sorted(awards.items()):
            click.echo(f"{award}: {count}")
