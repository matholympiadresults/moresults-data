"""Parse commands for the Sigma CLI."""

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
@click.option(
    "-d",
    "--data-dir",
    type=click.Path(path_type=Path),
    required=True,
    help="Base data directory (reads from raw/<year>/, writes to parsed/<year>/).",
)
@click.option(
    "--year",
    type=int,
    multiple=True,
    help="Specific year(s) to parse (can be used multiple times).",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Force re-parse existing files.",
)
def parse(source: str, data_dir: Path, year: tuple[int, ...], force: bool):
    """Parse raw data into intermediate format.

    Reads raw data from <data-dir>/<source>/raw/<year>/ and writes parsed data
    to <data-dir>/<source>/parsed/<year>/.

    SOURCE is one of: apmo, bmo, egmo, imo, memo, pamo, rmm
    """
    adapter = get_source(source)
    years = list(year) if year else None

    raw_base = adapter.get_raw_base_dir(data_dir)
    parsed_base = adapter.get_parsed_base_dir(data_dir)

    click.echo(f"Parsing {adapter.display_name} data")
    click.echo(f"Raw directory: {raw_base}/<year>/")
    click.echo(f"Parsed directory: {parsed_base}/<year>/")
    if years:
        click.echo(f"Years: {', '.join(map(str, years))}")
    else:
        click.echo("Years: all available")
    click.echo()

    try:
        adapter.parse_raw(data_dir, years, force)
    except NotImplementedError as e:
        raise click.ClickException(str(e)) from None
