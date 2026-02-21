#!/usr/bin/env python3
"""
BalcanMO Data CLI

Download BalcanMO (Balkan Mathematical Olympiad) results data from various sources.
"""

import sys
import time
from pathlib import Path

import click

from .bmo_scraper import AVAILABLE_YEARS, ScraperError, save_json, scrape_year


def download_year(
    year: int,
    output_dir: Path,
    raw_data_dir: Path,
    delay: float,
    force: bool,
) -> bool:
    """Download results for a single year.

    Returns True if successful, False otherwise.
    """
    output_file = output_dir / f"bmo_{year}.json"

    # Skip if already exists and not forcing
    if output_file.exists() and not force:
        click.echo(f"  {year}: Already exists, skipping")
        return True

    try:
        data = scrape_year(year, raw_data_dir, force=force)
        save_json(data, str(output_file))
        click.echo(
            f"  {year}: Downloaded {data.total_contestants} contestants ({data.source_type})"
        )

        # Be nice to the server
        time.sleep(delay)
        return True

    except ScraperError as e:
        click.echo(f"  {year}: {e}", err=True)
        return False
    except Exception as e:
        click.echo(f"  {year}: Unexpected error - {e}", err=True)
        return False


@click.group()
def cli():
    """BalcanMO results data tools."""
    pass


@cli.command()
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(),
    help="Output directory for parsed JSON files",
)
@click.option(
    "--raw-data",
    "-r",
    required=True,
    type=click.Path(),
    help="Directory to store raw data files (HTML/PDF)",
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
    default=min(AVAILABLE_YEARS),
    show_default=True,
    help="Start year",
)
@click.option(
    "--to",
    "-t",
    "to_year",
    type=int,
    default=max(AVAILABLE_YEARS),
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
    raw_data: str,
    year: int | None,
    from_year: int,
    to_year: int,
    delay: float,
    force: bool,
):
    """Download BalcanMO results data from various sources.

    Raw HTML/PDF files are saved to --raw-data directory.
    Parsed JSON files are saved to --output directory.
    """
    # Create output directories (expand ~ to home directory)
    output_dir = Path(output).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_data_dir = Path(raw_data).expanduser()
    raw_data_dir.mkdir(parents=True, exist_ok=True)

    # Determine years to download
    if year:
        if year not in AVAILABLE_YEARS:
            click.echo(f"Year {year} not available. Available years: {AVAILABLE_YEARS}")
            sys.exit(1)
        years = [year]
    else:
        # Filter to only available years in range
        years = [y for y in range(from_year, to_year + 1) if y in AVAILABLE_YEARS]

    if not years:
        click.echo(f"No available years in range {from_year}-{to_year}")
        click.echo(f"Available years: {AVAILABLE_YEARS}")
        sys.exit(1)

    click.echo("BalcanMO Data Download")
    click.echo(f"Output directory: {output_dir.absolute()}")
    click.echo(f"Raw data directory: {raw_data_dir.absolute()}")
    click.echo(f"Years to download: {years[0]} - {years[-1]} ({len(years)} years)")
    click.echo()

    # Download
    success_count = 0
    fail_count = 0

    for y in years:
        if download_year(y, output_dir, raw_data_dir, delay, force):
            success_count += 1
        else:
            fail_count += 1

    click.echo()
    click.echo(f"Done: {success_count} successful, {fail_count} failed")

    if fail_count > 0:
        sys.exit(1)


@cli.command()
def list_years():
    """List all available years and their data sources."""
    from .parsers.pdf_parser import PDF_SOURCES

    click.echo("Available BMO years and sources:")
    click.echo()

    for year in AVAILABLE_YEARS:
        if year in PDF_SOURCES:
            click.echo(f"  {year}: PDF - {PDF_SOURCES[year]}")
        else:
            # Get source URL from parser
            from pathlib import Path

            from .bmo_scraper import get_parser

            parser = get_parser(year, Path("."))
            click.echo(f"  {year}: HTML - {parser.source_url}")


@cli.command()
@click.option(
    "-d",
    "--data-dir",
    type=click.Path(path_type=Path, exists=True),
    required=True,
    help="Directory containing downloaded BMO JSON files.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    required=True,
    help="Path to output database file.",
)
@click.option(
    "--year",
    type=int,
    multiple=True,
    help="Specific year(s) to ingest (can be used multiple times).",
)
def ingest(data_dir: Path, output: Path, year: tuple[int, ...]):
    """Ingest downloaded BMO data into the normalized database."""
    from data_processing.sources.bmo.ingester import ingest_bmo_data

    years = list(year) if year else None

    click.echo(f"Ingesting BMO data from {data_dir}")
    click.echo(f"Database: {output}")
    click.echo()

    ingest_bmo_data(data_dir, output, years)

    click.echo()
    click.echo(f"Database saved to {output}")


if __name__ == "__main__":
    cli()
