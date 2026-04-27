"""Info command for the Sigma CLI."""

from pathlib import Path

import click

from ..sources import get_source


@click.command()
@click.argument(
    "source",
    type=click.Choice(
        ["apmo", "balticway", "bmo", "egmo", "emo", "imo", "jbmo", "memo", "pamo", "rmm"]
    ),
)
@click.argument("year", type=int)
@click.option(
    "-d",
    "--data-dir",
    type=click.Path(path_type=Path),
    required=True,
    help="Base data directory (reads from <data-dir>/<source>/parsed/<year>/).",
)
def info(source: str, year: int, data_dir: Path):
    """Show summary info for a specific year.

    Reads parsed data from <data-dir>/<source>/parsed/<year>/.

    SOURCE is one of: apmo, bmo, egmo, imo, memo, pamo, rmm

    YEAR is the calendar year (e.g., 2024)
    """
    adapter = get_source(source)

    try:
        adapter.info(year, data_dir)
    except NotImplementedError as e:
        raise click.ClickException(str(e)) from None
