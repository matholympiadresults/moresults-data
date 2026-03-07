"""Tests for the compare CLI command."""

import json

import click
from click.testing import CliRunner

from sigma.cli.commands.compare import compare

EMPTY_DB = {
    "version": "1.0",
    "last_updated": "2024-01-01T00:00:00Z",
    "countries": {},
    "competitions": {},
    "people": {},
    "participations": {},
    "team_participations": {},
}

POPULATED_DB = {
    "version": "1.0",
    "last_updated": "2024-06-01T00:00:00Z",
    "countries": {"US": {"name": "United States"}, "UK": {"name": "United Kingdom"}},
    "competitions": {
        "imo-2023": {"year": 2023},
        "egmo-2024": {"year": 2024},
    },
    "people": {"p1": {"name": "Alice"}, "p2": {"name": "Bob"}},
    "participations": {
        "part1": {"competition_id": "imo-2023", "person_id": "p1", "award": "gold"},
        "part2": {"competition_id": "egmo-2024", "person_id": "p2", "award": "silver"},
        "part3": {"competition_id": "imo-2023", "person_id": "p2"},
    },
    "team_participations": {
        "tp1": {"competition_id": "imo-2023", "country": "US"},
    },
}


def _write_db(tmp_path, name, db):
    path = tmp_path / name
    path.write_text(json.dumps(db), encoding="utf-8")
    return str(path)


def _run(tmp_path, db_a, db_b, args=None):
    a = _write_db(tmp_path, "a.json", db_a)
    b = _write_db(tmp_path, "b.json", db_b)
    result = CliRunner().invoke(compare, [a, b, *(args or [])], color=True)
    return result, click.unstyle(result.output)


class TestCompareEmptyDatabases:
    def test_both_empty(self, tmp_path):
        result, plain = _run(tmp_path, EMPTY_DB, EMPTY_DB)
        assert result.exit_code == 0
        assert "0 vs 0 (diff: 0)" in plain

    def test_all_entity_types_shown(self, tmp_path):
        _, plain = _run(tmp_path, EMPTY_DB, EMPTY_DB)
        for label in [
            "Countries:",
            "Competitions:",
            "People:",
            "Participations:",
            "Team Participations:",
            "Unique Sources:",
        ]:
            assert label in plain


class TestCompareEmptyVsPopulated:
    def test_shows_positive_diffs(self, tmp_path):
        result, plain = _run(tmp_path, EMPTY_DB, POPULATED_DB)
        assert result.exit_code == 0
        assert "Countries:" in plain
        assert "0 vs 2 (diff: +2)" in plain

    def test_shows_negative_diffs(self, tmp_path):
        result, plain = _run(tmp_path, POPULATED_DB, EMPTY_DB)
        assert result.exit_code == 0
        assert "2 vs 0 (diff: -2)" in plain

    def test_sources(self, tmp_path):
        _, plain = _run(tmp_path, EMPTY_DB, POPULATED_DB)
        assert "Unique Sources:" in plain


class TestCompareVerbose:
    def test_verbose_shows_added_keys(self, tmp_path):
        result, plain = _run(tmp_path, EMPTY_DB, POPULATED_DB, ["-v"])
        assert result.exit_code == 0
        assert "Added:" in plain
        assert "US" in plain

    def test_verbose_shows_removed_keys(self, tmp_path):
        result, plain = _run(tmp_path, POPULATED_DB, EMPTY_DB, ["-v"])
        assert result.exit_code == 0
        assert "Removed:" in plain

    def test_verbose_shows_source_diffs(self, tmp_path):
        _, plain = _run(tmp_path, EMPTY_DB, POPULATED_DB, ["-v"])
        assert "IMO" in plain
        assert "EGMO" in plain

    def test_no_verbose_hides_keys(self, tmp_path):
        _, plain = _run(tmp_path, EMPTY_DB, POPULATED_DB)
        assert "Added:" not in plain
        assert "Removed:" not in plain

    def test_diff_colors(self, tmp_path):
        result, _ = _run(tmp_path, EMPTY_DB, POPULATED_DB)
        assert "\x1b[32m" in result.output
        result, _ = _run(tmp_path, POPULATED_DB, EMPTY_DB)
        assert "\x1b[31m" in result.output


class TestCompareParticipationsByOlympiad:
    def test_shows_per_olympiad_counts(self, tmp_path):
        _, plain = _run(tmp_path, EMPTY_DB, POPULATED_DB)
        assert "Participations by Olympiad" in plain
        # IMO has 2 individual + 1 team = 3
        assert "IMO:" in plain
        assert "0 vs 3" in plain
        # EGMO has 1 individual
        assert "EGMO:" in plain
        assert "0 vs 1" in plain

    def test_hidden_when_both_empty(self, tmp_path):
        _, plain = _run(tmp_path, EMPTY_DB, EMPTY_DB)
        assert "Participations by Olympiad" not in plain


class TestCompareYearCoverage:
    def test_shows_end_result_and_added_years(self, tmp_path):
        _, plain = _run(tmp_path, EMPTY_DB, POPULATED_DB)
        assert "Year Coverage by Olympiad" in plain
        # Shows the end result range
        assert "2023" in plain
        assert "2024" in plain
        # Shows added years
        assert "(+2023)" in plain or "(+2023, 2024)" in plain

    def test_no_change_no_diff(self, tmp_path):
        _, plain = _run(tmp_path, POPULATED_DB, POPULATED_DB)
        # No +/- markers when unchanged
        assert "(+" not in plain
        assert "(-" not in plain


class TestCompareAwards:
    def test_shows_award_diffs(self, tmp_path):
        _, plain = _run(tmp_path, EMPTY_DB, POPULATED_DB)
        assert "Awards" in plain
        assert "gold:" in plain
        assert "silver:" in plain
        assert "no_award:" in plain

    def test_hidden_when_both_empty(self, tmp_path):
        _, plain = _run(tmp_path, EMPTY_DB, EMPTY_DB)
        assert "Awards" not in plain
