"""Tests for the BMO parser's name-correction pass."""

from sigma.sources.bmo.parser.bmo_parser import _country_key, apply_name_corrections
from sigma.sources.bmo.parser.models import ContestantResult


def make_result(name: str, country: str, **kwargs) -> ContestantResult:
    return ContestantResult(
        name=name,
        country=country,
        problem_scores=[1, 0, 0, 1],
        total=2,
        rank=None,
        award=None,
        **kwargs,
    )


class TestCountryKey:
    """The corrections table keys on the bare team code."""

    def test_strips_trailing_contestant_number(self):
        assert _country_key("ALG5") == "ALG"

    def test_strips_space_separated_contestant_number(self):
        assert _country_key("ALG 6") == "ALG"

    def test_leaves_bare_code_alone(self):
        assert _country_key("ALG") == "ALG"

    def test_keeps_b_team_marker(self):
        # country_base() in code_utils would reduce this to "SR".
        assert _country_key("SRB1") == "SRB"
        assert _country_key("ROMB1") == "ROMB"


class TestApplyNameCorrections:
    """Corrections canonicalize names so the person matcher merges records."""

    def test_reorders_given_names_to_match_imo(self):
        results = [make_result("Wacyl Mohamed Meddour", "ALG 6")]
        apply_name_corrections(2023, results)
        assert results[0].name == "Mohamed Wacyl Meddour"
        assert results[0].given_name == "Mohamed Wacyl"
        assert results[0].family_name == "Meddour"

    def test_rescues_multi_word_family_name(self):
        # The surname-first split keeps only "Si" as the family name.
        results = [make_result("Ahmed Abderrahmane Si", "ALG4", given_name="Ahmed Abderrahmane")]
        apply_name_corrections(2026, results)
        assert results[0].name == "Abderrahmane Si Ahmed"
        assert results[0].given_name == "Abderrahmane"
        assert results[0].family_name == "Si Ahmed"

    def test_correction_applies_regardless_of_contestant_number(self):
        results = [make_result("Chams Eddine Abdelali Derreche", "ALG")]
        apply_name_corrections(2024, results)
        assert results[0].name == "Chams Eddine Abd El Ali Derreche"

    def test_leaves_uncorrected_names_untouched(self):
        results = [make_result("Mohamed Boukra", "ALG")]
        apply_name_corrections(2024, results)
        assert results[0].name == "Mohamed Boukra"
        assert results[0].given_name is None
        assert results[0].family_name is None

    def test_correction_is_year_scoped(self):
        # "Ikbal Mohamed Tebib" is corrected for 2024 and 2025 only.
        results = [make_result("Ikbal Mohamed Tebib", "ALG")]
        apply_name_corrections(2019, results)
        assert results[0].name == "Ikbal Mohamed Tebib"
