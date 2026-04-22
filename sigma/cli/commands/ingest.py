"""Ingest commands for the Sigma CLI."""

from pathlib import Path

import click

from ..sources import get_source, ingest_all_sources


@click.command()
@click.argument(
    "source",
    type=click.Choice(["apmo", "balticway", "bmo", "egmo", "imo", "jbmo", "memo", "pamo", "rmm"]),
)
@click.option(
    "-d",
    "--data-dir",
    type=click.Path(path_type=Path),
    required=True,
    help="Base data directory (reads from <data-dir>/<source>/parsed/<year>/).",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=Path("data/olympiad_data.json"),
    show_default=True,
    help="Path to output database file.",
)
@click.option(
    "--year",
    type=int,
    multiple=True,
    help="Specific year(s) to ingest (can be used multiple times).",
)
def ingest(source: str, data_dir: Path, output: Path, year: tuple[int, ...]):
    """Ingest parsed data into the database.

    Reads parsed data from <data-dir>/<source>/parsed/<year>/ and writes to the database.

    SOURCE is one of: apmo, bmo, egmo, imo, memo, pamo, rmm
    """
    adapter = get_source(source)
    years = list(year) if year else None

    parsed_base = adapter.get_parsed_base_dir(data_dir)

    click.echo(f"Ingesting {adapter.display_name} data")
    click.echo(f"Parsed directory: {parsed_base}/<year>/")
    click.echo(f"Database: {output}")
    if years:
        click.echo(f"Years: {', '.join(map(str, years))}")
    else:
        click.echo("Years: all available")
    click.echo()

    try:
        adapter.ingest(data_dir, output, years)
    except NotImplementedError as e:
        raise click.ClickException(str(e)) from None

    click.echo()
    click.echo(f"Database saved to {output}")


@click.command("ingest-all")
@click.option(
    "-d",
    "--data-dir",
    type=click.Path(path_type=Path),
    required=True,
    help="Base data directory containing source subdirectories.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=Path("data/olympiad_data.json"),
    show_default=True,
    help="Path to output database file.",
)
def ingest_all(data_dir: Path, output: Path):
    """Ingest data from all sources into the database.

    Deletes any existing database and re-ingests all parsed data from scratch.
    Reads parsed data from <data-dir>/<source>/parsed/<year>/ for each source.
    """
    ingest_all_sources(data_dir, output, verbose=True)
