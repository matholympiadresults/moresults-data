"""Tests for RMM parser name ordering fix.

RMM's HTML tables list names as "Surname GivenName(s)" which is the opposite
of the "GivenName(s) Surname" format used by all other sources (IMO, EGMO, etc.).
The parser should swap the name order so that person matching works correctly
across competitions.
"""

from sigma.sources.rmm.parser.rmm_parser import parse_html


def _make_html_table(
    rows: list[tuple[str, str, str, list[int], str]], is_online: bool = False
) -> str:
    """Build a minimal RMM HTML page with a results table.

    Args:
        rows: List of (rank, name, country, scores, award) tuples.
              scores must be a list of 6 ints.
        is_online: If True, mark as online competition.
    """
    header_text = (
        "Individual Results (Online contestants)"
        if is_online
        else "Individual Results (Provisional)"
    )
    header_row = (
        "<tr><td><b>Pos.</b></td><td><b>Name</b></td><td><b>Country</b></td>"
        "<td><b>P1</b></td><td><b>P2</b></td><td><b>P3</b></td>"
        "<td><b>P4</b></td><td><b>P5</b></td><td><b>P6</b></td>"
        "<td><b>Total</b></td><td><b>Award</b></td></tr>"
    )

    data_rows = []
    for rank, name, country, scores, award in rows:
        score_cells = "".join(f"<td>{s}</td>" for s in scores)
        total = sum(scores)
        data_rows.append(
            f"<tr><td>{rank}</td><td>{name}</td><td>{country}</td>"
            f"{score_cells}<td>{total}</td><td>{award}</td></tr>"
        )

    return (
        f'<table><tr><td><h2 class="title_content">{header_text}</h2></td></tr>'
        f'<tr><td id="inside_content"><table>{header_row}{"".join(data_rows)}</table></td></tr>'
        f"</table>"
    )


def _make_2011_html_table(rows: list[tuple[str, str, str, str, list[int], str]]) -> str:
    """Build a minimal RMM 2011-format HTML page (separate first/last name columns).

    Args:
        rows: List of (rank, first_name, last_name, country, scores, award) tuples.
    """
    header_row = (
        "<tr><td><b>Nr.</b></td><td><b>First name</b></td><td><b>Last name</b></td>"
        "<td><b>Country</b></td>"
        "<td><b>P1</b></td><td><b>P2</b></td><td><b>P3</b></td>"
        "<td><b>P4</b></td><td><b>P5</b></td><td><b>P6</b></td>"
        "<td><b>Total</b></td><td><b>Medal</b></td></tr>"
    )

    data_rows = []
    for rank, first_name, last_name, country, scores, award in rows:
        score_cells = "".join(f"<td>{s}</td>" for s in scores)
        total = sum(scores)
        data_rows.append(
            f"<tr><td>{rank}</td><td>{first_name}</td><td>{last_name}</td>"
            f"<td>{country}</td>{score_cells}<td>{total}</td><td>{award}</td></tr>"
        )

    return (
        '<table><tr><td><h2 class="title_content">Mathematics - Individual Results</h2></td></tr>'
        f'<tr><td id="inside_content"><table>{header_row}{"".join(data_rows)}</table></td></tr>'
        f"</table>"
    )


class TestNameOrderSwap:
    """Standard format names should be swapped from 'Surname GivenName' to 'GivenName Surname'."""

    def test_two_word_name(self):
        html = _make_html_table([("1", "Anghel David-Andrei", "ROU", [7, 7, 7, 7, 7, 7], "GOLD")])
        results = parse_html(html, year=2023)
        assert results[0].name == "David-Andrei Anghel"

    def test_all_caps_name(self):
        html = _make_html_table([("1", "WANG Haokun", "CHN", [7, 7, 7, 7, 7, 7], "GOLD")])
        results = parse_html(html, year=2024)
        assert results[0].name == "Haokun WANG"

    def test_three_word_name(self):
        """Multi-part given name: 'Surname Given1 Given2' -> 'Given1 Given2 Surname'."""
        html = _make_html_table([("1", "Simon László Bence", "HUN", [7, 7, 7, 7, 7, 7], "GOLD")])
        results = parse_html(html, year=2024)
        assert results[0].name == "László Bence Simon"

    def test_single_word_name(self):
        """Single word names should be kept as-is."""
        html = _make_html_table([("1", "Mononym", "ROU", [7, 7, 7, 7, 7, 7], "GOLD")])
        results = parse_html(html, year=2023)
        assert results[0].name == "Mononym"

    def test_official_team_asterisk_preserved(self):
        """Name marked with * (official team) should have name swapped but asterisk stripped."""
        html = _make_html_table([("1", "Ciurea Pavel*", "ROU", [7, 7, 7, 7, 7, 7], "GOLD")])
        results = parse_html(html, year=2024)
        assert results[0].name == "Pavel Ciurea"
        assert results[0].is_official_team is True

    def test_multiple_contestants(self):
        html = _make_html_table(
            [
                ("1", "Zhang Qiao", "CHN", [7, 7, 7, 7, 7, 7], "GOLD"),
                ("2", "Bouton Anatole", "FRA", [7, 7, 6, 7, 7, 7], "GOLD"),
                ("3", "Carratu Andrew", "USA", [7, 6, 7, 7, 7, 7], "GOLD"),
            ]
        )
        results = parse_html(html, year=2024)
        assert results[0].name == "Qiao Zhang"
        assert results[1].name == "Anatole Bouton"
        assert results[2].name == "Andrew Carratu"


class TestNameOrder2011Format:
    """2011 format has separate first/last name columns - should produce 'GivenName Surname'."""

    def test_2011_format_name_order(self):
        html = _make_2011_html_table(
            [("1", "Robert", "Dragomirescu", "ROU", [7, 7, 7, 7, 7, 7], "GOLD")]
        )
        results = parse_html(html, year=2011)
        assert results[0].name == "Robert Dragomirescu"
