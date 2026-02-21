"""Download commands for the Sigma CLI."""

from pathlib import Path

import click

from ..sources import get_source


def build_year_list(
    adapter, year: int | None, from_year: int | None, to_year: int | None
) -> list[int]:
    """Build a list of years based on options."""
    if year is not None:
        return [year]

    available = adapter.get_available_years()
    start = from_year if from_year is not None else available.start
    end = to_year if to_year is not None else available.stop - 1

    return [y for y in range(start, end + 1) if y in available]


@click.command()
@click.argument("source", type=click.Choice(["apmo", "bmo", "egmo", "imo", "memo", "pamo", "rmm"]))
@click.option(
    "-d",
    "--data-dir",
    type=click.Path(path_type=Path),
    required=True,
    help="Base data directory (raw files go to <data-dir>/<source>/raw/<year>/).",
)
@click.option(
    "--year",
    type=int,
    default=None,
    help="Download a single year.",
)
@click.option(
    "--from",
    "from_year",
    type=int,
    default=None,
    help="Start year (inclusive).",
)
@click.option(
    "--to",
    "to_year",
    type=int,
    default=None,
    help="End year (inclusive).",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Force re-download existing files.",
)
def download(
    source: str,
    data_dir: Path,
    year: int | None,
    from_year: int | None,
    to_year: int | None,
    force: bool,
):
    """Download raw data from a source.

    Downloads raw data files (HTML, PDF, CSV, etc.) to <data-dir>/<source>/raw/<year>/.

    SOURCE is one of: apmo, bmo, egmo, imo, memo, pamo, rmm
    """
    adapter = get_source(source)
    years = build_year_list(adapter, year, from_year, to_year)

    raw_base = adapter.get_raw_base_dir(data_dir)
    click.echo(f"{adapter.display_name} Data Download")
    click.echo(f"Output directory: {raw_base.absolute()}/<year>/")
    if len(years) == 1:
        click.echo(f"Year: {years[0]}")
    else:
        click.echo(f"Years: {years[0]} - {years[-1]} ({len(years)} years)")
    click.echo()

    try:
        adapter.download_raw(data_dir, years, force)
    except NotImplementedError as e:
        raise click.ClickException(str(e)) from None
