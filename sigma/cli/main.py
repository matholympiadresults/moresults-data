"""Sigma CLI - Main entry point."""

import click

from .commands.download import download
from .commands.info import info
from .commands.ingest import ingest, ingest_all
from .commands.parse import parse
from .commands.summary import summary


@click.group()
@click.version_option(package_name="sigma")
def cli():
    """Sigma - Math Olympiad Data Processing CLI.

    Download and process data from mathematical olympiads.

    \b
    Data pipeline:
      1. download - Fetch raw data (HTML, PDF, CSV) to <data-dir>/<source>/raw/<year>/
      2. parse    - Parse raw data to <data-dir>/<source>/parsed/<year>/
      3. ingest   - Ingest parsed data into the database

    \b
    Examples:
      sigma download egmo -d data/ --year 2024
      sigma parse egmo -d data/ --year 2024
      sigma ingest egmo -d data/ -o data/olympiad_data.json --year 2024
      sigma info egmo 2024 -d data/
      sigma ingest-all -d data/ -o data/olympiad_data.json
    """
    pass


cli.add_command(download)
cli.add_command(parse)
cli.add_command(ingest)
cli.add_command(ingest_all)
cli.add_command(info)
cli.add_command(summary)


if __name__ == "__main__":
    cli()
