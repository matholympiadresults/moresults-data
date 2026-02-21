"""Summary command for the Sigma CLI."""

import json
from collections import Counter
from pathlib import Path

import click


def format_year_range(years: set[int]) -> str:
    """Format a set of years into ranges with gaps shown.

    Example: {2012, 2013, 2014, 2016, 2017, 2020} -> "2012-2014, 2016-2017, 2020"
    """
    if not years:
        return "none"

    sorted_years = sorted(years)
    ranges: list[str] = []
    start = sorted_years[0]
    end = start

    for year in sorted_years[1:]:
        if year == end + 1:
            end = year
        else:
            ranges.append(f"{start}-{end}" if start != end else str(start))
            start = end = year

    ranges.append(f"{start}-{end}" if start != end else str(start))
    return ", ".join(ranges)


@click.command()
@click.argument("database", type=click.Path(exists=True, path_type=Path))
def summary(database: Path):
    """Show summary statistics for a database file.

    DATABASE is the path to an olympiad_data.json file.

    \b
    Examples:
      sigma summary data/olympiad_data.json
      sigma summary ~/Data/Olympiads/v2/olympiad_data.json
    """
    with open(database, encoding="utf-8") as f:
        db = json.load(f)

    countries = db.get("countries", {})
    competitions = db.get("competitions", {})
    people = db.get("people", {})
    participations = db.get("participations", {})

    # Basic counts
    click.echo(f"Database: {database}")
    click.echo(f"Last updated: {db.get('last_updated', 'unknown')}")
    click.echo()
    click.echo("=== Entity Counts ===")
    click.echo(f"Countries:      {len(countries):,}")
    click.echo(f"Competitions:   {len(competitions):,}")
    click.echo(f"People:         {len(people):,}")
    click.echo(f"Participations: {len(participations):,}")

    if not participations:
        return

    # Participations by olympiad and years per olympiad
    olympiad_counts: Counter[str] = Counter()
    olympiad_years: dict[str, set[int]] = {}

    for p in participations.values():
        comp_id = p.get("competition_id", "")
        parts = comp_id.split("-")
        if len(parts) >= 2:
            olympiad = parts[0].upper()
            olympiad_counts[olympiad] += 1
            if parts[-1].isdigit():
                year = int(parts[-1])
                if olympiad not in olympiad_years:
                    olympiad_years[olympiad] = set()
                olympiad_years[olympiad].add(year)

    click.echo()
    click.echo("=== Participations by Olympiad ===")
    for olympiad in sorted(olympiad_counts.keys()):
        click.echo(f"{olympiad:8} {olympiad_counts[olympiad]:,}")

    # Year coverage per olympiad
    click.echo()
    click.echo("=== Year Coverage by Olympiad ===")
    for olympiad in sorted(olympiad_years.keys()):
        years = olympiad_years[olympiad]
        year_range = format_year_range(years)
        click.echo(f"{olympiad:8} {year_range}")

    # Awards breakdown
    award_counts: Counter[str] = Counter()
    no_award_count = 0
    for p in participations.values():
        award = p.get("award")
        if award:
            award_counts[award] += 1
        else:
            no_award_count += 1

    click.echo()
    click.echo("=== Awards ===")
    for award in ["gold", "silver", "bronze", "honourable_mention"]:
        if award in award_counts:
            click.echo(f"{award:20} {award_counts[award]:,}")
    click.echo(f"{'no_award':20} {no_award_count:,}")
