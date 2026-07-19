"""
TEMPORARY IMO 2026 pipeline (download -> parse -> ingest).

IMO 2026 (67th, Shanghai) is not on imo-official.org yet, so this standalone
script pulls the provisional individual results the Local Organizing Committee
published at https://www.imo2026.com/Results/Individual_Results.htm and ingests
them under the usual ``imo-2026`` competition / ``IMO`` source.

The LOC page renders its table client-side from a semicolon-delimited CSV
embedded in a ``const csvInput = `...`;`` block, so there is no results table in
the served HTML to feed the regular IMO parser — hence this throwaway script.

Delete this file once imo-official.org publishes 2026 and the normal
``sigma download/parse/ingest-all imo`` flow can take over.

Usage:
    uv run python scripts/imo2026_temp.py all -d data/ -o data/olympiad_data.json

    # or step by step:
    uv run python scripts/imo2026_temp.py download -d data/
    uv run python scripts/imo2026_temp.py parse    -d data/
    uv run python scripts/imo2026_temp.py ingest    -d data/ -o data/olympiad_data.json
"""

import json
import re
from pathlib import Path

import click
import requests

from sigma.database import (
    create_empty_database,
    get_or_create_country,
    load_database,
    save_database,
)
from sigma.matching import PersonMatcher
from sigma.schemas import Participation, Source
from sigma.sources.imo.ingester.imo_ingester import (
    convert_award,
    create_competition,
    normalize_country_code,
    sanitize_name,
    scores_to_list,
)
from sigma.sources.imo.parser.imo_parser import validate_totals
from sigma.sources.imo.parser.models import (
    ContestantResult,
    IMOYearResults,
    ProblemScores,
    ValidationResult,
)

YEAR = 2026
RESULTS_URL = "https://www.imo2026.com/Results/Individual_Results.htm"

# The LOC embeds the results as a semicolon-delimited, double-quoted CSV inside a
# JS template literal: ``const csvInput = `HEADER\n"row";...` ``.
_CSV_RE = re.compile(r"const csvInput = `(.*?)`", re.S)

# P_AWARD codes used on the LOC page -> the medal labels convert_award() expects.
_AWARD_LABELS: dict[str, str] = {
    "1": "Gold medal",
    "2": "Silver medal",
    "3": "Bronze medal",
    "4": "Honourable mention",
}


def _year_dir(base_dir: Path) -> Path:
    return base_dir / "imo2026_temp" / str(YEAR)


def _raw_html_path(base_dir: Path) -> Path:
    return _year_dir(base_dir) / "results.html"


def _parsed_json_path(base_dir: Path) -> Path:
    return _year_dir(base_dir) / "results.json"


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #
def download_html(timeout: int = 30) -> str:
    """Fetch the raw LOC individual-results page."""
    response = requests.get(RESULTS_URL, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    return response.text


# --------------------------------------------------------------------------- #
# Parse
# --------------------------------------------------------------------------- #
def _extract_csv(html: str) -> str:
    """Pull the embedded CSV payload out of the page's ``csvInput`` literal."""
    match = _CSV_RE.search(html)
    if not match:
        raise ValueError("Could not find embedded csvInput block in HTML")
    return match.group(1).strip()


def _parse_fields(line: str) -> list[str]:
    """Split one CSV line the same way the page's JS does (``;`` separated, quoted)."""
    line = line.strip()
    if line.startswith('"') and line.endswith('"'):
        line = line[1:-1]
    return [part.strip().strip('"').replace('"', "") for part in line.split(";")]


def _assign_ranks(contestants: list[ContestantResult]) -> None:
    """Assign standard competition ranking (ties share the higher rank).

    Mirrors the LOC page: sort by total descending, then rank by position with
    equal totals sharing a rank. Mutates ``rank`` in place; leaves list sorted.
    """
    contestants.sort(key=lambda c: c.total, reverse=True)
    for i, c in enumerate(contestants):
        if i > 0 and c.total == contestants[i - 1].total:
            c.rank = contestants[i - 1].rank
        else:
            c.rank = i + 1


def parse_html(html: str) -> IMOYearResults:
    """Parse the LOC page into the standard IMO year-results structure."""
    csv = _extract_csv(html)
    lines = [ln for ln in csv.split("\n") if ln.strip()]

    header = _parse_fields(lines[0])
    expected = [
        "GIVEN_NAME",
        "FAMILY_NAME",
        "ID_C",
        "P_1",
        "P_2",
        "P_3",
        "P_4",
        "P_5",
        "P_6",
        "P_SUM",
        "P_AWARD",
    ]
    if header != expected:
        raise ValueError(f"Unexpected CSV header: {header}")

    contestants: list[ContestantResult] = []
    for line_no, line in enumerate(lines[1:], start=2):
        fields = _parse_fields(line)
        # The page keeps only rows with all 11 columns; do the same.
        if len(fields) != 11:
            continue

        given, family, country_code = fields[0], fields[1], fields[2]
        name = " ".join(f"{given} {family}".split())

        score_values: list[int] = []
        for i in range(6):
            text = fields[3 + i]
            try:
                score = int(text)
            except ValueError as err:
                raise ValueError(f"Line {line_no}: bad score {text!r} for {name}") from err
            if not 0 <= score <= 7:
                raise ValueError(f"Line {line_no}: score {score} out of range for {name}")
            score_values.append(score)

        total = int(fields[9])
        award = _AWARD_LABELS.get(fields[10])  # empty string -> None

        contestants.append(
            ContestantResult(
                contestant_id=None,  # LOC data carries no per-contestant IDs
                name=name,
                country_code=country_code,
                scores=ProblemScores(
                    p1=score_values[0],
                    p2=score_values[1],
                    p3=score_values[2],
                    p4=score_values[3],
                    p5=score_values[4],
                    p6=score_values[5],
                    p7=None,
                ),
                total=total,
                rank=None,
                award=award,
            )
        )

    if not contestants:
        raise ValueError("No contestant rows parsed")

    _assign_ranks(contestants)

    mismatches = validate_totals(contestants)
    return IMOYearResults(
        year=YEAR,
        total_contestants=len(contestants),
        results=contestants,
        validation=ValidationResult(
            all_totals_match=len(mismatches) == 0,
            mismatches=mismatches,
        ),
    )


# --------------------------------------------------------------------------- #
# Ingest
# --------------------------------------------------------------------------- #
def ingest_year_results(db, year_results: IMOYearResults) -> dict:
    """Ingest IMO 2026 results, matching people by name (no source IDs available)."""
    matcher = PersonMatcher(db)
    competition = create_competition(db, year_results)

    new_people = 0
    matched_people = 0

    for contestant in year_results.results:
        country_code = normalize_country_code(contestant.country_code)
        if country_code is not None:
            country_id = get_or_create_country(db, country_code).id
        else:
            country_id = None

        # No per-contestant source IDs on the LOC page, so match on name+country
        # like the other ID-less sources (e.g. BMO).
        match_result = matcher.match_or_create(
            name=sanitize_name(contestant.name),
            country_id=country_id,
            source=Source.IMO,
            source_contestant_id=None,
        )
        if match_result.is_new:
            new_people += 1
        else:
            matched_people += 1

        participation_id = f"{competition.id}-{match_result.person_id}"
        db.participations[participation_id] = Participation(
            id=participation_id,
            competition_id=competition.id,
            person_id=match_result.person_id,
            country_id=country_id,
            problem_scores=scores_to_list(contestant),
            total=contestant.total,
            rank=contestant.rank,
            regional_rank=None,
            award=convert_award(contestant.award),
            extra_awards=None,
            source_contestant_id=None,
        )

    return {
        "contestants": len(year_results.results),
        "new_people": new_people,
        "matched_people": matched_people,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
@click.group()
def cli() -> None:
    """Temporary IMO 2026 download/parse/ingest pipeline."""


@cli.command()
@click.option("-d", "--data-dir", type=click.Path(path_type=Path), default=Path("data"))
def download(data_dir: Path) -> None:
    """Download the LOC results page."""
    html = download_html()
    path = _raw_html_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    click.echo(f"Downloaded {len(html):,} bytes -> {path}")


@cli.command()
@click.option("-d", "--data-dir", type=click.Path(path_type=Path), default=Path("data"))
def parse(data_dir: Path) -> None:
    """Parse the downloaded page into results.json."""
    html = _raw_html_path(data_dir).read_text(encoding="utf-8")
    results = parse_html(html)
    path = _parsed_json_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(results.model_dump_json(indent=2), encoding="utf-8")
    status = "all totals match" if results.validation.all_totals_match else "TOTAL MISMATCHES!"
    click.echo(f"Parsed {results.total_contestants} contestants ({status}) -> {path}")


@cli.command()
@click.option("-d", "--data-dir", type=click.Path(path_type=Path), default=Path("data"))
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    required=True,
    help="Path to olympiad_data.json to update in place.",
)
def ingest(data_dir: Path, output: Path) -> None:
    """Ingest results.json into the normalized database."""
    with open(_parsed_json_path(data_dir), encoding="utf-8") as f:
        year_results = IMOYearResults.model_validate(json.load(f))

    db = load_database(output) if output.exists() else create_empty_database()
    stats = ingest_year_results(db, year_results)
    save_database(db, output)
    click.echo(
        f"Ingested {stats['contestants']} contestants "
        f"({stats['new_people']} new, {stats['matched_people']} matched) -> {output}"
    )


@cli.command(name="all")
@click.option("-d", "--data-dir", type=click.Path(path_type=Path), default=Path("data"))
@click.option("-o", "--output", type=click.Path(path_type=Path), required=True)
@click.pass_context
def run_all(ctx: click.Context, data_dir: Path, output: Path) -> None:
    """Download, parse, and ingest in one go."""
    ctx.invoke(download, data_dir=data_dir)
    ctx.invoke(parse, data_dir=data_dir)
    ctx.invoke(ingest, data_dir=data_dir, output=output)


if __name__ == "__main__":
    cli()
