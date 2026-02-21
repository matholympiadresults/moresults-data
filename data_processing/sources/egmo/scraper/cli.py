#!/usr/bin/env python3
"""
EGMO Data CLI

Download, parse, and ingest EGMO (European Girls' Mathematical Olympiad) results data.

Three modes:
- download: Downloads raw HTML/CSV files from egmo.org to raw/{year}/
- parse: Parses raw files into structured JSON in parsed/{year}/
- ingest: Ingests parsed JSON into the normalized database
"""

import sys
import time
from pathlib import Path

import click

from .egmo_scraper import (
    FIRST_EGMO_YEAR,
    ScraperError,
    download_raw,
    get_available_years,
    parse_raw,
    save_json,
)


@click.group()
def cli():
    """EGMO results data tools."""
    pass


@cli.command()
@click.option(
    "--raw-data",
    "-r",
    required=True,
    type=click.Path(path_type=Path),
    help="Directory to store raw HTML/CSV files (files go in {raw-data}/{year}/)",
)
@click.option(
    "--year",
    "-y",
    type=int,
    help="Download a single specific year",
)
@click.option(
    "--from",
    "-f",
    "from_year",
    type=int,
    default=FIRST_EGMO_YEAR,
    show_default=True,
    help="Start year",
)
@click.option(
    "--to",
    "-t",
    "to_year",
    type=int,
    default=None,
    help="End year (default: current year)",
)
@click.option(
    "--delay",
    "-d",
    type=float,
    default=1.0,
    show_default=True,
    help="Delay between requests in seconds",
)
@click.option(
    "--force",
    is_flag=True,
    help="Re-download even if files already exist",
)
def download(
    raw_data: Path,
    year: int | None,
    from_year: int,
    to_year: int | None,
    delay: float,
    force: bool,
):
    """Download raw EGMO data (HTML and CSV files) from egmo.org."""
    raw_data.mkdir(parents=True, exist_ok=True)

    # Determine years to download
    available_years = get_available_years()

    if year:
        if year not in available_years:
            click.echo(
                f"Year {year} not available. Available: {available_years[0]}-{available_years[-1]}"
            )
            sys.exit(1)
        years = [year]
    else:
        end_year = to_year if to_year else available_years[-1]
        years = [y for y in range(from_year, end_year + 1) if y in available_years]

    if not years:
        click.echo(f"No available years in range {from_year}-{to_year}")
        sys.exit(1)

    click.echo("EGMO Data Download")
    click.echo(f"Raw data directory: {raw_data.absolute()}")
    click.echo(f"Years to download: {years[0]} - {years[-1]} ({len(years)} years)")
    click.echo()

    success_count = 0
    fail_count = 0

    for y in years:
        try:
            html_file, csv_file = download_raw(y, raw_data, force=force)
            if html_file.exists() and csv_file.exists():
                click.echo(f"  {y}: Downloaded -> {html_file.parent}")
                success_count += 1
            time.sleep(delay)
        except ScraperError as e:
            click.echo(f"  {y}: {e}", err=True)
            fail_count += 1
        except Exception as e:
            click.echo(f"  {y}: Unexpected error - {e}", err=True)
            fail_count += 1

    click.echo()
    click.echo(f"Done: {success_count} successful, {fail_count} failed")

    if fail_count > 0:
        sys.exit(1)


@cli.command()
@click.option(
    "--raw-data",
    "-r",
    required=True,
    type=click.Path(path_type=Path, exists=True),
    help="Directory containing raw HTML/CSV files in {raw-data}/{year}/ subdirs",
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(path_type=Path),
    help="Directory to store parsed JSON files (files go in {output}/{year}/)",
)
@click.option(
    "--year",
    "-y",
    type=int,
    help="Parse a single specific year",
)
@click.option(
    "--from",
    "-f",
    "from_year",
    type=int,
    default=FIRST_EGMO_YEAR,
    show_default=True,
    help="Start year",
)
@click.option(
    "--to",
    "-t",
    "to_year",
    type=int,
    default=None,
    help="End year (default: current year)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Re-parse even if output file already exists",
)
def parse(
    raw_data: Path,
    output: Path,
    year: int | None,
    from_year: int,
    to_year: int | None,
    force: bool,
):
    """Parse raw EGMO data into structured JSON files (one per year subdirectory)."""
    # Find available raw data
    available_years = []
    for year_dir in raw_data.iterdir():
        if year_dir.is_dir() and year_dir.name.isdigit():
            y = int(year_dir.name)
            html_file = year_dir / f"egmo_{y}_scoreboard.html"
            csv_file = year_dir / f"egmo_{y}_scores.csv"
            if html_file.exists() and csv_file.exists():
                available_years.append(y)

    available_years.sort()

    if not available_years:
        click.echo(f"No raw data found in {raw_data}")
        sys.exit(1)

    # Filter years
    if year:
        if year not in available_years:
            click.echo(f"No raw data for year {year}. Available: {available_years}")
            sys.exit(1)
        years = [year]
    else:
        end_year = to_year if to_year else max(available_years)
        years = [y for y in available_years if from_year <= y <= end_year]

    if not years:
        click.echo(f"No years in range {from_year}-{to_year}")
        sys.exit(1)

    click.echo("EGMO Data Parse")
    click.echo(f"Raw data directory: {raw_data.absolute()}")
    click.echo(f"Output directory: {output.absolute()}")
    click.echo(f"Years to parse: {years[0]} - {years[-1]} ({len(years)} years)")
    click.echo()

    success_count = 0
    fail_count = 0

    for y in years:
        # Output goes to {output}/{year}/egmo_{year}.json
        year_output_dir = output / str(y)
        output_file = year_output_dir / f"egmo_{y}.json"

        if output_file.exists() and not force:
            click.echo(f"  {y}: Already exists, skipping")
            success_count += 1
            continue

        try:
            year_output_dir.mkdir(parents=True, exist_ok=True)
            html_file = raw_data / str(y) / f"egmo_{y}_scoreboard.html"
            csv_file = raw_data / str(y) / f"egmo_{y}_scores.csv"

            data = parse_raw(y, html_file, csv_file)
            save_json(data, output_file)
            click.echo(
                f"  {y}: Parsed {data.total_contestants} contestants -> {y}/{output_file.name}"
            )
            success_count += 1
        except Exception as e:
            click.echo(f"  {y}: Failed - {e}", err=True)
            fail_count += 1

    click.echo()
    click.echo(f"Done: {success_count} successful, {fail_count} failed")

    if fail_count > 0:
        sys.exit(1)


@cli.command()
@click.option(
    "-d",
    "--data-dir",
    type=click.Path(path_type=Path, exists=True),
    required=True,
    help="Directory containing parsed EGMO JSON files in {data-dir}/{year}/ subdirs",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    required=True,
    help="Path to output database file",
)
@click.option(
    "--year",
    type=int,
    multiple=True,
    help="Specific year(s) to ingest (can be used multiple times)",
)
def ingest(data_dir: Path, output: Path, year: tuple[int, ...]):
    """Ingest parsed EGMO data into the normalized database."""
    from data_processing.sources.egmo.ingester import ingest_egmo_data

    years = list(year) if year else None

    click.echo(f"Ingesting EGMO data from {data_dir}")
    click.echo(f"Database: {output}")
    click.echo()

    ingest_egmo_data(data_dir, output, years)

    click.echo()
    click.echo(f"Database saved to {output}")


@cli.command()
@click.argument("year", type=int)
@click.option(
    "-d",
    "--data-dir",
    type=click.Path(path_type=Path, exists=True),
    required=True,
    help="Directory containing parsed EGMO JSON files in {data-dir}/{year}/ subdirs",
)
def info(year: int, data_dir: Path):
    """Show summary info for a specific EGMO year."""
    from .models import EGMOYearResults

    # Look in {data_dir}/{year}/egmo_{year}.json
    json_file = data_dir / str(year) / f"egmo_{year}.json"

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


@cli.command()
def list_years():
    """List all available EGMO years."""
    years = get_available_years()
    click.echo(f"Available EGMO years: {years[0]} - {years[-1]}")
    click.echo(f"Total: {len(years)} editions")


if __name__ == "__main__":
    cli()
