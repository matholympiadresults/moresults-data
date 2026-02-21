"""APMO Data CLI - Download and Ingest APMO data."""

from pathlib import Path

import click

from data_processing.sources.apmo.apmo_downloader import (
    APMOScoreboard,
    Award,
    download_apmo_year,
    save_to_json,
)
from data_processing.sources.apmo.ingester import ingest_apmo_data

# APMO started in 1989 (edition 1)
# Full online results available from 2016
FIRST_APMO_YEAR = 1989
FIRST_ONLINE_YEAR = 2016


@click.group()
def cli():
    """APMO scoreboard data tools."""
    pass


@cli.command()
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    required=True,
    help="Directory to store downloaded data.",
)
@click.option(
    "--from",
    "start_year",
    type=int,
    default=FIRST_ONLINE_YEAR,
    help=f"First year to download (default: {FIRST_ONLINE_YEAR}, first year with online data).",
)
@click.option(
    "--to",
    "end_year",
    type=int,
    default=None,
    help="Last year to download (default: current year).",
)
@click.option(
    "--year",
    type=int,
    default=None,
    help="Download a single year (e.g., 2024).",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Force re-download existing files.",
)
def download(output: Path, start_year: int, end_year: int | None, year: int | None, force: bool):
    """Download APMO scoreboard data from apmo-official.org."""
    from datetime import datetime

    if year is not None:
        years = [year]
    else:
        end = end_year or datetime.now().year
        years = list(range(start_year, end + 1))

    output.mkdir(parents=True, exist_ok=True)

    click.echo(f"Downloading APMO data for {len(years)} year(s)...")
    click.echo()

    for y in years:
        output_file = output / f"apmo_{y}.json"

        if output_file.exists() and not force:
            click.echo(f"  APMO {y}: Skipped (already exists, use --force to re-download)")
            continue

        try:
            scoreboard = download_apmo_year(y)
            path = save_to_json(scoreboard, output)
            click.echo(
                f"  APMO {y}: {len(scoreboard.contestants)} contestants "
                f"from {len(scoreboard.countries)} countries -> {path}"
            )
        except Exception as e:
            click.echo(f"  APMO {y}: Failed - {e}", err=True)


@cli.command()
@click.argument("year", type=int)
@click.option(
    "-d",
    "--data-dir",
    type=click.Path(path_type=Path, exists=True),
    required=True,
    help="Directory containing downloaded JSON files.",
)
def info(year: int, data_dir: Path):
    """Show summary info for a specific APMO year (e.g., 2024)."""
    json_file = data_dir / f"apmo_{year}.json"

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


@cli.command()
@click.option(
    "-d",
    "--data-dir",
    type=click.Path(path_type=Path, exists=True),
    required=True,
    help="Directory containing downloaded APMO JSON files.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=Path("data/olympiad_data.json"),
    help="Path to output database file.",
)
@click.option(
    "--year",
    type=int,
    multiple=True,
    help="Specific year(s) to ingest (can be used multiple times).",
)
def ingest(data_dir: Path, output: Path, year: tuple[int, ...]):
    """Ingest downloaded APMO data into the normalized database."""
    years = list(year) if year else None

    click.echo(f"Ingesting APMO data from {data_dir}")
    click.echo(f"Database: {output}")
    click.echo()

    ingest_apmo_data(data_dir, output, years)

    click.echo()
    click.echo(f"Database saved to {output}")


if __name__ == "__main__":
    cli()
