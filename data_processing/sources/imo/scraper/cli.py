#!/usr/bin/env python3
"""
IMO Data Download CLI

Download raw IMO (International Mathematical Olympiad) results data.
"""

import sys
import time
from datetime import datetime
from pathlib import Path

import click

from .imo_scraper import ScraperError, save_json, scrape_year

# IMO has been held since 1959
FIRST_IMO_YEAR = 1959
CURRENT_YEAR = datetime.now().year


def download_year(year: int, output_dir: Path, delay: float, force: bool) -> bool:
    """Download results for a single year.

    Returns True if successful, False otherwise.
    """
    output_file = output_dir / f"imo_{year}.json"

    # Skip if already exists and not forcing
    if output_file.exists() and not force:
        click.echo(f"  {year}: Already exists, skipping")
        return True

    try:
        data = scrape_year(year)
        save_json(data, str(output_file))
        click.echo(f"  {year}: Downloaded {data.total_contestants} contestants")

        # Be nice to the server
        time.sleep(delay)
        return True

    except ScraperError as e:
        click.echo(f"  {year}: {e}", err=True)
        return False
    except Exception as e:
        click.echo(f"  {year}: Unexpected error - {e}", err=True)
        return False


@click.command()
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(),
    help="Output directory for raw data files",
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
def main(output: str, year: int | None, from_year: int, to_year: int, delay: float, force: bool):
    """Download IMO results data from imo-official.org."""
    # Create output directory (expand ~ to home directory)
    output_dir = Path(output).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine years to download
    if year:
        years = [year]
    else:
        years = list(range(from_year, to_year + 1))

    click.echo("IMO Data Download")
    click.echo(f"Output directory: {output_dir.absolute()}")
    click.echo(f"Years to download: {years[0]} - {years[-1]} ({len(years)} years)")
    click.echo()

    # Download
    success_count = 0
    fail_count = 0

    for y in years:
        if download_year(y, output_dir, delay, force):
            success_count += 1
        else:
            fail_count += 1

    click.echo()
    click.echo(f"Done: {success_count} successful, {fail_count} failed")

    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
