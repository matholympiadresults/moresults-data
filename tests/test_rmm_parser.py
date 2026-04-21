"""Tests for sigma/sources/rmm/parser/rmm_parser.py."""

from bs4 import BeautifulSoup

from sigma.sources.rmm.parser.rmm_parser import _parse_table


def _make_table(rows_html: str) -> BeautifulSoup:
    """Create a BeautifulSoup table element with a header row and data rows."""
    html = f"""
    <table>
      <tr>
        <td><b>Pos.</b></td>
        <td><b>Name</b></td>
        <td><b>Country</b></td>
        <td><b>P1</b></td><td><b>P2</b></td><td><b>P3</b></td>
        <td><b>P4</b></td><td><b>P5</b></td><td><b>P6</b></td>
        <td><b>Total</b></td>
        <td><b>Award</b></td>
      </tr>
      {rows_html}
    </table>
    """
    return BeautifulSoup(html, "html.parser").find("table")


def _make_row(rank: str, name: str, country: str = "USA") -> str:
    """Create a single result row with dummy scores."""
    return (
        f"<tr>"
        f"<td>{rank}</td>"
        f"<td>{name}</td>"
        f"<td>{country}</td>"
        f"<td>7</td><td>7</td><td>7</td><td>7</td><td>7</td><td>7</td>"
        f"<td>42</td>"
        f"<td>GOLD</td>"
        f"</tr>"
    )


class TestNameSwapPre2018:
    """Before 2018, names are 'First Last' and should be kept as-is."""

    def test_simple_name(self):
        table = _make_table(_make_row("1", "Foo Bar"))
        results = _parse_table(table, 2017, is_online=False)
        assert results[0].name == "Foo Bar"

    def test_all_caps_name(self):
        table = _make_table(_make_row("1", "FOO BAR"))
        results = _parse_table(table, 2015, is_online=False)
        assert results[0].name == "FOO BAR"

    def test_multi_word_name(self):
        table = _make_table(_make_row("1", "FOO BAR BAZ"))
        results = _parse_table(table, 2017, is_online=False)
        assert results[0].name == "FOO BAR BAZ"


class TestNameSwapPost2018:
    """From 2018 onwards, names are 'Last First' and should be swapped."""

    def test_simple_swap(self):
        table = _make_table(_make_row("1", "BAR FOO"))
        results = _parse_table(table, 2018, is_online=False)
        assert results[0].name == "FOO BAR"

    def test_swap_mixed_case(self):
        table = _make_table(_make_row("1", "Bar Foo"))
        results = _parse_table(table, 2023, is_online=False)
        assert results[0].name == "Foo Bar"

    def test_swap_multi_word_given_name(self):
        table = _make_table(_make_row("1", "Baz Foo Bar"))
        results = _parse_table(table, 2024, is_online=False)
        assert results[0].name == "Foo Bar Baz"

    def test_single_word_name_unchanged(self):
        table = _make_table(_make_row("1", "Foo"))
        results = _parse_table(table, 2020, is_online=False)
        assert results[0].name == "Foo"

    def test_hyphenated_family_name_with_spaces(self):
        """Family names with ' - ' should stay together when swapped."""
        table = _make_table(_make_row("1", "FOO - BAR ZAR"))
        results = _parse_table(table, 2021, is_online=False)
        assert results[0].name == "ZAR FOO - BAR"

    def test_official_team_marker_stripped(self):
        table = _make_table(_make_row("1", "Bar Foo-Baz*"))
        results = _parse_table(table, 2023, is_online=False)
        assert results[0].name == "Foo-Baz Bar"
        assert results[0].is_official_team is True


class TestEarlyYearParsers:
    """2008-2010 editions used different file formats."""

    def test_2008_html_uses_four_problems_and_resolves_country_names(self):
        from pathlib import Path

        from sigma.sources.rmm.parser import parse_2008_html
        from sigma.sources.rmm.parser.rmm_parser import load_html

        path = Path(__file__).parent.parent / "data/rmm/raw/2008/rmm_2008.html"
        data = parse_2008_html(load_html(path))
        assert data.year == 2008
        assert data.total_contestants == 34
        assert data.validation.all_totals_match
        assert all(len(r.problem_scores) == 4 for r in data.results)
        first = data.results[0]
        assert first.name == "Jakub Konieczny"
        assert first.country == "POL"
        assert first.award == "GOLD"
        yakutsk = [r for r in data.results if r.country == "YAKUTSK"]
        assert len(yakutsk) == 3

    def test_2009_xls_swaps_name_order_and_handles_particles(self):
        from pathlib import Path

        from sigma.sources.rmm.parser import parse_2009_xls

        path = Path(__file__).parent.parent / "data/rmm/raw/2009/rmm_2009.xls"
        data = parse_2009_xls(path)
        assert data.year == 2009
        assert data.validation.all_totals_match
        assert all(len(r.problem_scores) == 4 for r in data.results)
        names = {r.name for r in data.results}
        assert "Teodor von Burg" in names  # leading "von" particle kept with surname
        assert "Svetozar Zlatkov Stankov" in names
        # DNS rows (empty-name "(contestant)") must be dropped.
        assert not any("contestant" in n.lower() for n in names)

    def test_2010_xls_reorders_names_and_strips_female_marker(self):
        from pathlib import Path

        from sigma.sources.rmm.parser import parse_2010_xls

        path = Path(__file__).parent.parent / "data/rmm/raw/2010/rmm_2010.xls"
        data = parse_2010_xls(path)
        assert data.year == 2010
        assert data.total_contestants == 71
        assert data.validation.all_totals_match
        assert all(len(r.problem_scores) == 6 for r in data.results)
        names = {r.name for r in data.results}
        assert "Teodor von Burg" in names  # "Burg Teodor von" reordered
        assert "Barbosa Alves Deborah" in names  # ♀ marker stripped, swap applied
