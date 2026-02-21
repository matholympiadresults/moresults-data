"""Tests for data_processing/matching/person_matcher.py."""

import pytest

from data_processing.database import create_empty_database
from data_processing.matching import PersonMatcher
from data_processing.matching.person_matcher import capitalize_name, compute_initials
from data_processing.schemas import Country, Person, Source


class TestCapitalizeName:
    def test_uppercase_name(self):
        assert capitalize_name("JANE DOE") == "Jane Doe"

    def test_lowercase_name(self):
        assert capitalize_name("john smith") == "John Smith"

    def test_mixed_case_preserved(self):
        """Mixed case names are assumed to be already properly formatted."""
        assert capitalize_name("John Smith") == "John Smith"
        assert capitalize_name("Jean-Pierre Dupont") == "Jean-Pierre Dupont"

    def test_lowercase_prefixes(self):
        """Common prefixes like 'van', 'de', 'von' stay lowercase."""
        assert capitalize_name("JOHANNES VAN DER BERG") == "Johannes van der Berg"
        assert capitalize_name("MARIA DE LA CRUZ") == "Maria de la Cruz"
        assert capitalize_name("LUDWIG VON BEETHOVEN") == "Ludwig von Beethoven"

    def test_first_word_always_capitalized(self):
        """First word is always capitalized, even if it's a prefix."""
        assert capitalize_name("VAN MORRISON") == "Van Morrison"
        assert capitalize_name("DE GAULLE") == "De Gaulle"

    def test_whitespace_normalization(self):
        assert capitalize_name("  JOHN   SMITH  ") == "John Smith"

    def test_empty_string(self):
        assert capitalize_name("") == ""

    def test_none_handling(self):
        assert capitalize_name(None) is None


class TestComputeInitials:
    def test_two_word_name(self):
        assert compute_initials("John Smith") == "js"

    def test_single_name(self):
        assert compute_initials("Jane") == "j"

    def test_multi_word_name(self):
        assert compute_initials("Johannes van der Berg") == "jvdb"

    def test_accented_characters(self):
        assert compute_initials("José García") == "jg"

    def test_uppercase_name(self):
        assert compute_initials("JANE DOE") == "jd"

    def test_extra_whitespace(self):
        assert compute_initials("  John   Smith  ") == "js"


@pytest.fixture
def db_with_countries():
    """Create a database with some countries."""
    db = create_empty_database()
    db.countries["country-gbr"] = Country(id="country-gbr", code="gbr", name="United Kingdom")
    db.countries["country-usa"] = Country(id="country-usa", code="usa", name="United States")
    db.countries["country-deu"] = Country(id="country-deu", code="deu", name="Germany")
    return db


@pytest.fixture
def db_with_people(db_with_countries):
    """Create a database with some people."""
    db = db_with_countries
    db.people["js-1"] = Person(
        id="js-1",
        name="John Smith",
        given_name="John",
        family_name="Smith",
        country_id="country-gbr",
        aliases=["J. Smith"],
        source_ids={"imo": "12345", "egmo": None, "memo": None},
    )
    db.people["jd-1"] = Person(
        id="jd-1",
        name="Jane Doe",
        country_id="country-usa",
        aliases=[],
        source_ids={"imo": None, "egmo": "67890", "memo": None},
    )
    return db


class TestPersonMatcherInit:
    def test_init_with_empty_db(self, db_with_countries):
        matcher = PersonMatcher(db_with_countries)
        assert matcher._next_person_ids == {}

    def test_init_with_existing_people(self, db_with_people):
        matcher = PersonMatcher(db_with_people)
        assert matcher._next_person_ids == {"js": 2, "jd": 2}


class TestGeneratePersonId:
    def test_generates_sequential_ids_same_initials(self, db_with_countries):
        matcher = PersonMatcher(db_with_countries)
        id1 = matcher._generate_person_id("John Smith")
        id2 = matcher._generate_person_id("Jack Sparrow")
        assert id1 == "js-1"
        assert id2 == "js-2"

    def test_generates_ids_per_initials(self, db_with_countries):
        matcher = PersonMatcher(db_with_countries)
        id1 = matcher._generate_person_id("John Smith")
        id2 = matcher._generate_person_id("Jane Doe")
        id3 = matcher._generate_person_id("Jack Sparrow")
        assert id1 == "js-1"
        assert id2 == "jd-1"
        assert id3 == "js-2"

    def test_continues_from_existing(self, db_with_people):
        matcher = PersonMatcher(db_with_people)
        new_id = matcher._generate_person_id("John Smith")
        assert new_id == "js-2"


class TestFindBySourceId:
    def test_finds_existing_person_by_imo_id(self, db_with_people):
        matcher = PersonMatcher(db_with_people)
        person = matcher.find_by_source_id(Source.IMO, "12345")
        assert person is not None
        assert person.id == "js-1"
        assert person.name == "John Smith"

    def test_finds_existing_person_by_egmo_id(self, db_with_people):
        matcher = PersonMatcher(db_with_people)
        person = matcher.find_by_source_id(Source.EGMO, "67890")
        assert person is not None
        assert person.id == "jd-1"
        assert person.name == "Jane Doe"

    def test_returns_none_for_unknown_id(self, db_with_people):
        matcher = PersonMatcher(db_with_people)
        person = matcher.find_by_source_id(Source.IMO, "unknown")
        assert person is None

    def test_returns_none_for_empty_db(self, db_with_countries):
        matcher = PersonMatcher(db_with_countries)
        person = matcher.find_by_source_id(Source.IMO, "12345")
        assert person is None


class TestFindByExactName:
    def test_finds_by_exact_name_and_country(self, db_with_people):
        matcher = PersonMatcher(db_with_people)
        match = matcher.find_by_exact_name("John Smith", "country-gbr")
        assert match is not None
        assert match.person_id == "js-1"
        assert match.confidence == 1.0

    def test_case_insensitive_matching(self, db_with_people):
        matcher = PersonMatcher(db_with_people)
        match = matcher.find_by_exact_name("JOHN SMITH", "country-gbr")
        assert match is not None
        assert match.person_id == "js-1"

    def test_no_match_wrong_country(self, db_with_people):
        matcher = PersonMatcher(db_with_people)
        match = matcher.find_by_exact_name("John Smith", "country-usa")
        assert match is None

    def test_no_match_unknown_name(self, db_with_people):
        matcher = PersonMatcher(db_with_people)
        match = matcher.find_by_exact_name("Unknown Person", "country-gbr")
        assert match is None

    def test_strips_whitespace(self, db_with_people):
        matcher = PersonMatcher(db_with_people)
        match = matcher.find_by_exact_name("  John Smith  ", "country-gbr")
        assert match is not None


class TestMatchOrCreate:
    def test_creates_new_person_when_no_match(self, db_with_countries):
        matcher = PersonMatcher(db_with_countries)
        result = matcher.match_or_create(
            name="New Person",
            country_id="country-gbr",
            source=Source.IMO,
            source_contestant_id="99999",
        )
        assert result.is_new is True
        assert result.person_id == "np-1"
        assert result.confidence == 1.0
        assert "New person created" in result.reason

        # Verify person was added to database
        assert "np-1" in db_with_countries.people
        person = db_with_countries.people["np-1"]
        assert person.name == "New Person"
        assert person.source_ids["imo"] == "99999"

    def test_matches_by_source_id(self, db_with_people):
        matcher = PersonMatcher(db_with_people)
        result = matcher.match_or_create(
            name="Different Name",  # Name doesn't matter when source ID matches
            country_id="country-deu",  # Country doesn't matter either
            source=Source.IMO,
            source_contestant_id="12345",  # This matches js-1
        )
        assert result.is_new is False
        assert result.person_id == "js-1"
        assert result.confidence == 1.0
        assert "Source ID match" in result.reason

    def test_matches_by_exact_name(self, db_with_people):
        matcher = PersonMatcher(db_with_people)
        result = matcher.match_or_create(
            name="John Smith",
            country_id="country-gbr",
            source=Source.MEMO,  # Different source, no source ID
        )
        assert result.is_new is False
        assert result.person_id == "js-1"
        assert result.confidence == 1.0
        assert "Exact name" in result.reason

    def test_updates_source_id_on_name_match(self, db_with_people):
        matcher = PersonMatcher(db_with_people)
        # js-1 has imo=12345, egmo=None
        result = matcher.match_or_create(
            name="John Smith",
            country_id="country-gbr",
            source=Source.EGMO,
            source_contestant_id="new-egmo-id",
        )
        assert result.is_new is False
        # Should have updated the EGMO source ID
        person = db_with_people.people["js-1"]
        assert person.source_ids["egmo"] == "new-egmo-id"

    def test_creates_with_given_and_family_name(self, db_with_countries):
        matcher = PersonMatcher(db_with_countries)
        result = matcher.match_or_create(
            name="Alice Johnson",
            country_id="country-usa",
            source=Source.EGMO,
            given_name="Alice",
            family_name="Johnson",
        )
        person = db_with_countries.people[result.person_id]
        assert person.given_name == "Alice"
        assert person.family_name == "Johnson"

    def test_normalizes_uppercase_names(self, db_with_countries):
        """Uppercase names should be normalized to proper capitalization."""
        matcher = PersonMatcher(db_with_countries)
        result = matcher.match_or_create(
            name="JANE DOE",
            country_id="country-gbr",
            source=Source.IMO,
            given_name="JANE",
            family_name="DOE",
        )
        person = db_with_countries.people[result.person_id]
        assert person.name == "Jane Doe"
        assert person.given_name == "Jane"
        assert person.family_name == "Doe"

    def test_source_id_priority_over_name(self, db_with_people):
        """Source ID match should take priority over name match."""
        matcher = PersonMatcher(db_with_people)
        # Jane Doe has egmo=67890
        result = matcher.match_or_create(
            name="John Smith",  # This name matches js-1
            country_id="country-gbr",
            source=Source.EGMO,
            source_contestant_id="67890",  # But this ID matches jd-1
        )
        assert result.person_id == "jd-1"  # Source ID wins

    def test_no_source_id_match_without_id(self, db_with_people):
        """When no source_contestant_id is provided, should fall back to name matching."""
        matcher = PersonMatcher(db_with_people)
        result = matcher.match_or_create(
            name="John Smith",
            country_id="country-gbr",
            source=Source.IMO,
            source_contestant_id=None,
        )
        assert result.is_new is False
        assert "Exact name" in result.reason


class TestMultipleCreations:
    def test_creates_multiple_people(self, db_with_countries):
        matcher = PersonMatcher(db_with_countries)

        result1 = matcher.match_or_create(
            name="Person One",
            country_id="country-gbr",
            source=Source.IMO,
        )
        result2 = matcher.match_or_create(
            name="Person Two",
            country_id="country-usa",
            source=Source.IMO,
        )
        result3 = matcher.match_or_create(
            name="Person Three",
            country_id="country-deu",
            source=Source.IMO,
        )

        assert result1.person_id == "po-1"
        assert result2.person_id == "pt-1"
        assert result3.person_id == "pt-2"
        assert len(db_with_countries.people) == 3

    def test_same_name_different_countries(self, db_with_countries):
        """Same name in different countries should create different people."""
        matcher = PersonMatcher(db_with_countries)

        result1 = matcher.match_or_create(
            name="Common Name",
            country_id="country-gbr",
            source=Source.IMO,
        )
        result2 = matcher.match_or_create(
            name="Common Name",
            country_id="country-usa",
            source=Source.IMO,
        )

        assert result1.person_id != result2.person_id
        assert result1.is_new is True
        assert result2.is_new is True
