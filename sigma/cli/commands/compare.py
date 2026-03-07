"""Compare command for the Sigma CLI."""

import json
from collections import Counter
from pathlib import Path

import click

from .summary import format_year_range


def _load_db(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


ENTITY_LABELS = [
    ("countries", "Countries"),
    ("competitions", "Competitions"),
    ("people", "People"),
    ("participations", "Participations"),
    ("team_participations", "Team Participations"),
]

AWARD_ORDER = ["gold", "silver", "bronze", "honourable_mention", "no_award"]


def _collect_sources(db: dict) -> set[str]:
    sources: set[str] = set()
    for p in (
        *db.get("participations", {}).values(),
        *db.get("team_participations", {}).values(),
    ):
        comp_id = p.get("competition_id", "")
        parts = comp_id.split("-")
        if len(parts) >= 2 and parts[-1].isdigit() and len(parts[-1]) == 4:
            sources.add("-".join(parts[:-1]).upper())
    return sources


def _collect_olympiad_stats(db: dict) -> tuple[Counter[str], dict[str, set[int]]]:
    counts: Counter[str] = Counter()
    years: dict[str, set[int]] = {}
    for p in (
        *db.get("participations", {}).values(),
        *db.get("team_participations", {}).values(),
    ):
        comp_id = p.get("competition_id", "")
        parts = comp_id.split("-")
        if len(parts) >= 2 and parts[-1].isdigit() and len(parts[-1]) == 4:
            year = int(parts[-1])
            olympiad = "-".join(parts[:-1]).upper()
            counts[olympiad] += 1
            years.setdefault(olympiad, set()).add(year)
    return counts, years


def _collect_awards(db: dict) -> Counter[str]:
    counts: Counter[str] = Counter()
    for p in db.get("participations", {}).values():
        award = p.get("award")
        counts[award if award else "no_award"] += 1
    return counts


def _diff_str(a: int, b: int) -> str:
    diff = b - a
    if diff == 0:
        return click.style("0", fg="yellow")
    if diff > 0:
        return click.style(f"+{diff}", fg="green")
    return click.style(str(diff), fg="red")


def _section(title: str) -> None:
    click.echo()
    click.echo(click.style(f"=== {title} ===", bold=True))


def _diff_counter_row(label: str, a: int, b: int, width: int = 22) -> None:
    click.echo(f"{label + ':':>{width}} {a:,} vs {b:,} (diff: {_diff_str(a, b)})")


@click.command()
@click.argument("database_a", type=click.Path(path_type=Path))
@click.argument("database_b", type=click.Path(path_type=Path))
@click.option("-v", "--verbose", is_flag=True, help="Show individual differences.")
def compare(database_a: Path, database_b: Path, *, verbose: bool):
    """Compare two database files and show differences.

    DATABASE_A and DATABASE_B are paths to olympiad_data.json files.

    \b
    Examples:
      sigma compare old.json new.json
      sigma compare old.json new.json -v
    """
    db_a = _load_db(database_a)
    db_b = _load_db(database_b)

    click.echo(f"A: {database_a}")
    click.echo(f"B: {database_b}")

    # --- Entity counts ---
    _section("Entity Counts")
    for key, label in ENTITY_LABELS:
        a_dict = db_a.get(key, {})
        b_dict = db_b.get(key, {})
        _diff_counter_row(label, len(a_dict), len(b_dict))
        if verbose:
            keys_a = set(a_dict.keys())
            keys_b = set(b_dict.keys())
            added = sorted(keys_b - keys_a)
            removed = sorted(keys_a - keys_b)
            if added:
                click.echo(click.style(f"  Added:   {', '.join(added)}", fg="green"))
            if removed:
                click.echo(click.style(f"  Removed: {', '.join(removed)}", fg="red"))

    # Unique sources
    sources_a = _collect_sources(db_a)
    sources_b = _collect_sources(db_b)
    _diff_counter_row("Unique Sources", len(sources_a), len(sources_b))
    if verbose:
        added_src = sorted(sources_b - sources_a)
        removed_src = sorted(sources_a - sources_b)
        if added_src:
            click.echo(click.style(f"  Added:   {', '.join(added_src)}", fg="green"))
        if removed_src:
            click.echo(click.style(f"  Removed: {', '.join(removed_src)}", fg="red"))

    # --- Participations by olympiad ---
    counts_a, years_a = _collect_olympiad_stats(db_a)
    counts_b, years_b = _collect_olympiad_stats(db_b)
    all_olympiads = sorted(set(counts_a) | set(counts_b))

    if all_olympiads:
        _section("Participations by Olympiad")
        for olympiad in all_olympiads:
            _diff_counter_row(olympiad, counts_a[olympiad], counts_b[olympiad])

    # --- Year coverage by olympiad ---
    all_year_olympiads = sorted(set(years_a) | set(years_b))
    if all_year_olympiads:
        _section("Year Coverage by Olympiad")
        for olympiad in all_year_olympiads:
            ya = years_a.get(olympiad, set())
            yb = years_b.get(olympiad, set())
            added_y = sorted(yb - ya)
            removed_y = sorted(ya - yb)
            line = f"  {olympiad:12} {format_year_range(yb)}"
            if added_y:
                line += "  " + click.style(f"(+{', '.join(str(y) for y in added_y)})", fg="green")
            if removed_y:
                line += "  " + click.style(f"(-{', '.join(str(y) for y in removed_y)})", fg="red")
            click.echo(line)

    # --- Awards ---
    awards_a = _collect_awards(db_a)
    awards_b = _collect_awards(db_b)
    if awards_a or awards_b:
        _section("Awards")
        for award in AWARD_ORDER:
            a_count = awards_a[award]
            b_count = awards_b[award]
            if a_count or b_count:
                _diff_counter_row(award, a_count, b_count)
