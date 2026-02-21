#!/usr/bin/env python3
"""
IMO Data CLI

Unified CLI for downloading, parsing, and ingesting IMO data.
Pipeline: download -> parse -> ingest
"""

import sys
from datetime import datetime
from pathlib import Path

import click

from data_processing.sources.imo.download import FIRST_IMO_YEAR, download_years
from data_processing.sources.imo.ingest import ingest_years, print_database_stats
from data_processing.sources.imo.parse import parse_years

CURRENT_YEAR = datetime.now().year


def parse_year_range(
    year: int | None,
    from_year: int,
    to_year: int,
) -> list[int]:
    """Parse year arguments into a list of years."""
    if year:
        return [year]
    return list(range(from_year, to_year + 1))


@click.group()
def cli():
    """IMO data pipeline: download, parse, and ingest results data."""
    pass


@cli.command()
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(),
    help="Base directory for raw data (creates yearly subdirs: output/2024/results.html)",
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
    default=FIRST_IMO_YEAR,
    show_default=True,
    help="Start year",
)
@click.option(
    "--to",
    "-t",
    "to_year",
    type=int,
    default=CURRENT_YEAR,
    show_default=True,
    help="End year",
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
    help="Re-download even if file already exists",
)
def download(
    output: str,
    year: int | None,
    from_year: int,
    to_year: int,
    delay: float,
    force: bool,
):
    """Download raw HTML pages from imo-official.org."""
    output_dir = Path(output).expanduser()
    years = parse_year_range(year, from_year, to_year)

    click.echo("IMO Download")
    click.echo(f"Output directory: {output_dir.absolute()}")
    click.echo(f"Years: {years[0]} - {years[-1]} ({len(years)} years)")
    click.echo()

    stats = download_years(output_dir, years, delay=delay, force=force)

    click.echo()
    click.echo(
        f"Done: {stats['success']} downloaded, {stats['skipped']} skipped, {stats['failed']} failed"
    )

    if stats["failed"] > 0:
        sys.exit(1)


@cli.command()
@click.option(
    "--input",
    "-i",
    required=True,
    type=click.Path(exists=True),
    help="Base directory with raw data (expects input/2024/results.html)",
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(),
    help="Base directory for parsed data (creates output/2024/results.json)",
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
    default=FIRST_IMO_YEAR,
    show_default=True,
    help="Start year",
)
@click.option(
    "--to",
    "-t",
    "to_year",
    type=int,
    default=CURRENT_YEAR,
    show_default=True,
    help="End year",
)
@click.option(
    "--force",
    is_flag=True,
    help="Re-parse even if output file already exists",
)
def parse(
    input: str,
    output: str,
    year: int | None,
    from_year: int,
    to_year: int,
    force: bool,
):
    """Parse raw HTML files into structured JSON."""
    input_dir = Path(input).expanduser()
    output_dir = Path(output).expanduser()
    years = parse_year_range(year, from_year, to_year) if year else None

    click.echo("IMO Parse")
    click.echo(f"Input directory: {input_dir.absolute()}")
    click.echo(f"Output directory: {output_dir.absolute()}")
    if years:
        click.echo(f"Years: {years[0]} - {years[-1]} ({len(years)} years)")
    else:
        click.echo("Years: all available")
    click.echo()

    stats = parse_years(input_dir, output_dir, years=years, force=force)

    click.echo()
    click.echo(
        f"Done: {stats['success']} parsed, {stats['skipped']} skipped, {stats['failed']} failed"
    )

    if stats["failed"] > 0:
        sys.exit(1)


@cli.command()
@click.option(
    "--input",
    "-i",
    required=True,
    type=click.Path(exists=True),
    help="Base directory with parsed data (expects input/2024/results.json)",
)
@click.option(
    "--database",
    "-d",
    required=True,
    type=click.Path(),
    help="Path to database file (will be created if doesn't exist)",
)
@click.option(
    "--year",
    "-y",
    type=int,
    help="Ingest a single specific year",
)
@click.option(
    "--from",
    "-f",
    "from_year",
    type=int,
    default=FIRST_IMO_YEAR,
    show_default=True,
    help="Start year",
)
@click.option(
    "--to",
    "-t",
    "to_year",
    type=int,
    default=CURRENT_YEAR,
    show_default=True,
    help="End year",
)
def ingest(
    input: str,
    database: str,
    year: int | None,
    from_year: int,
    to_year: int,
):
    """Ingest parsed JSON data into the database."""
    input_dir = Path(input).expanduser()
    db_path = Path(database).expanduser()
    years = parse_year_range(year, from_year, to_year) if year else None

    click.echo("IMO Ingest")
    click.echo(f"Input directory: {input_dir.absolute()}")
    click.echo(f"Database: {db_path.absolute()}")
    if years:
        click.echo(f"Years: {years[0]} - {years[-1]} ({len(years)} years)")
    else:
        click.echo("Years: all available")
    click.echo()

    try:
        db = ingest_years(input_dir, db_path, years=years)
        print_database_stats(db)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
