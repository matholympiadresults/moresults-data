"""Tests for data_processing/schemas/models.py."""

from datetime import UTC, datetime

from data_processing.schemas import (
    Award,
    Competition,
    Country,
    Database,
    Participation,
    Person,
    Source,
)


class TestSource:
    def test_source_values(self):
        assert Source.IMO.value == "IMO"
        assert Source.EGMO.value == "EGMO"
        assert Source.MEMO.value == "MEMO"

    def test_source_is_string_enum(self):
        assert isinstance(Source.IMO, str)
        assert Source.IMO == "IMO"


class TestAward:
    def test_award_values(self):
        assert Award.GOLD.value == "gold"
        assert Award.SILVER.value == "silver"
        assert Award.BRONZE.value == "bronze"
        assert Award.HONOURABLE_MENTION.value == "honourable_mention"

    def test_award_is_string_enum(self):
        assert isinstance(Award.GOLD, str)
        assert Award.GOLD == "gold"


class TestCountry:
    def test_create_country(self):
        country = Country(id="country-gbr", code="gbr", name="United Kingdom")
        assert country.id == "country-gbr"
        assert country.code == "gbr"
        assert country.name == "United Kingdom"

    def test_country_serialization(self):
        country = Country(id="country-usa", code="usa", name="United States")
        data = country.model_dump()
        assert data == {"id": "country-usa", "code": "usa", "name": "United States"}


class TestCompetition:
    def test_create_competition_minimal(self):
        comp = Competition(
            id="imo-2024",
            source=Source.IMO,
            year=2024,
            num_problems=6,
        )
        assert comp.id == "imo-2024"
        assert comp.source == Source.IMO
        assert comp.year == 2024
        assert comp.num_problems == 6
        assert comp.max_score_per_problem == 7  # default
        assert comp.edition is None
        assert comp.host_country_id is None

    def test_create_competition_full(self):
        comp = Competition(
            id="imo-2024",
            source=Source.IMO,
            year=2024,
            edition=65,
            host_country_id="country-gbr",
            num_problems=6,
            max_score_per_problem=7,
        )
        assert comp.edition == 65
        assert comp.host_country_id == "country-gbr"

    def test_competition_with_egmo_source(self):
        comp = Competition(
            id="egmo-2024",
            source=Source.EGMO,
            year=2024,
            num_problems=4,
        )
        assert comp.source == Source.EGMO


class TestPerson:
    def test_create_person_minimal(self):
        person = Person(
            id="person-000001",
            name="John Smith",
            country_id="country-gbr",
        )
        assert person.id == "person-000001"
        assert person.name == "John Smith"
        assert person.country_id == "country-gbr"
        assert person.given_name is None
        assert person.family_name is None
        assert person.aliases == []
        assert person.source_ids == {}

    def test_create_person_full(self):
        person = Person(
            id="person-000001",
            name="John Smith",
            given_name="John",
            family_name="Smith",
            country_id="country-gbr",
            aliases=["J. Smith", "Johnny Smith"],
            source_ids={"imo": "12345", "egmo": None, "memo": None},
        )
        assert person.given_name == "John"
        assert person.family_name == "Smith"
        assert person.aliases == ["J. Smith", "Johnny Smith"]
        assert person.source_ids["imo"] == "12345"


class TestParticipation:
    def test_create_participation_minimal(self):
        part = Participation(
            id="imo-2024-person-000001",
            competition_id="imo-2024",
            person_id="person-000001",
            country_id="country-gbr",
            problem_scores=[7, 7, 1, 7, 7, 0],
            total=29,
        )
        assert part.id == "imo-2024-person-000001"
        assert part.competition_id == "imo-2024"
        assert part.person_id == "person-000001"
        assert part.problem_scores == [7, 7, 1, 7, 7, 0]
        assert part.total == 29
        assert part.rank is None
        assert part.award is None

    def test_create_participation_full(self):
        part = Participation(
            id="imo-2024-person-000001",
            competition_id="imo-2024",
            person_id="person-000001",
            country_id="country-gbr",
            problem_scores=[7, 7, 1, 7, 7, 0],
            total=29,
            rank=15,
            regional_rank=10,
            award=Award.GOLD,
            extra_awards="Special prize",
            source_contestant_id="12345",
        )
        assert part.rank == 15
        assert part.regional_rank == 10
        assert part.award == Award.GOLD
        assert part.extra_awards == "Special prize"
        assert part.source_contestant_id == "12345"

    def test_participation_with_none_scores(self):
        """Some problems may have None scores (not attempted or missing data)."""
        part = Participation(
            id="test-part",
            competition_id="imo-2024",
            person_id="person-000001",
            country_id="country-gbr",
            problem_scores=[7, None, 1, None, 7, 0],
            total=15,
        )
        assert part.problem_scores[1] is None
        assert part.problem_scores[3] is None


class TestDatabase:
    def test_create_empty_database(self):
        db = Database(last_updated=datetime.now(UTC))
        assert db.version == "1.0"
        assert db.countries == {}
        assert db.competitions == {}
        assert db.people == {}
        assert db.participations == {}

    def test_create_populated_database(self):
        country = Country(id="country-gbr", code="gbr", name="United Kingdom")
        comp = Competition(id="imo-2024", source=Source.IMO, year=2024, num_problems=6)
        person = Person(id="person-000001", name="John Smith", country_id="country-gbr")
        part = Participation(
            id="imo-2024-person-000001",
            competition_id="imo-2024",
            person_id="person-000001",
            country_id="country-gbr",
            problem_scores=[7, 7, 7, 7, 7, 7],
            total=42,
        )

        db = Database(
            last_updated=datetime.now(UTC),
            countries={"country-gbr": country},
            competitions={"imo-2024": comp},
            people={"person-000001": person},
            participations={"imo-2024-person-000001": part},
        )

        assert len(db.countries) == 1
        assert len(db.competitions) == 1
        assert len(db.people) == 1
        assert len(db.participations) == 1

    def test_database_serialization_roundtrip(self):
        db = Database(
            last_updated=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            countries={"country-gbr": Country(id="country-gbr", code="gbr", name="United Kingdom")},
        )
        data = db.model_dump(mode="json")
        db2 = Database.model_validate(data)
        assert db2.countries["country-gbr"].name == "United Kingdom"
