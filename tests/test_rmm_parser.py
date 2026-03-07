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
        table = _make_table(_make_row("1", "Joe Benton"))
        results = _parse_table(table, 2017, is_online=False)
        assert results[0].name == "Joe Benton"

    def test_all_caps_name(self):
        table = _make_table(_make_row("1", "HARVEY YAU"))
        results = _parse_table(table, 2015, is_online=False)
        assert results[0].name == "HARVEY YAU"

    def test_multi_word_name(self):
        table = _make_table(_make_row("1", "KYU HYEON CHOI"))
        results = _parse_table(table, 2017, is_online=False)
        assert results[0].name == "KYU HYEON CHOI"


class TestNameSwapPost2018:
    """From 2018 onwards, names are 'Last First' and should be swapped."""

    def test_simple_swap(self):
        table = _make_table(_make_row("1", "SINGHAL MIHIR"))
        results = _parse_table(table, 2018, is_online=False)
        assert results[0].name == "MIHIR SINGHAL"

    def test_swap_mixed_case(self):
        table = _make_table(_make_row("1", "Wang Alexander"))
        results = _parse_table(table, 2023, is_online=False)
        assert results[0].name == "Alexander Wang"

    def test_swap_multi_word_given_name(self):
        table = _make_table(_make_row("1", "Simon László Bence"))
        results = _parse_table(table, 2024, is_online=False)
        assert results[0].name == "László Bence Simon"

    def test_single_word_name_unchanged(self):
        table = _make_table(_make_row("1", "Mononym"))
        results = _parse_table(table, 2020, is_online=False)
        assert results[0].name == "Mononym"

    def test_hyphenated_family_name_with_spaces(self):
        """Family names with ' - ' should stay together when swapped."""
        table = _make_table(_make_row("1", "FOO - BAR ZAR"))
        results = _parse_table(table, 2021, is_online=False)
        assert results[0].name == "ZAR FOO - BAR"

    def test_official_team_marker_stripped(self):
        table = _make_table(_make_row("1", "Anghel David-Andrei*"))
        results = _parse_table(table, 2023, is_online=False)
        assert results[0].name == "David-Andrei Anghel"
        assert results[0].is_official_team is True
