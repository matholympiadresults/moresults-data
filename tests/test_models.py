"""Tests for data_processing/schemas/models.py."""

from datetime import UTC, datetime

from data_processing.schemas import (
    Award,
    Competition,
    CompetitionType,
    Country,
    Database,
    Participation,
    Person,
    Source,
    TeamParticipation,
)


class TestCompetitionType:
    def test_competition_type_values(self):
        assert CompetitionType.INDIVIDUAL.value == "individual"
        assert CompetitionType.TEAM.value == "team"

    def test_competition_type_is_string_enum(self):
        assert isinstance(CompetitionType.INDIVIDUAL, str)
        assert CompetitionType.INDIVIDUAL == "individual"


class TestSource:
    def test_source_values(self):
        assert Source.IMO.value == "IMO"
        assert Source.EGMO.value == "EGMO"
        assert Source.MEMO.value == "MEMO"
        assert Source.MEMO_TEAM.value == "MEMO_TEAM"
        assert Source.BALTICWAY.value == "BALTICWAY"

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
        assert comp.competition_type == CompetitionType.INDIVIDUAL  # default
        assert comp.edition is None
        assert comp.host_country_id is None

    def test_create_team_competition(self):
        comp = Competition(
            id="memo_team-2024",
            source=Source.MEMO_TEAM,
            year=2024,
            competition_type=CompetitionType.TEAM,
            num_problems=8,
        )
        assert comp.source == Source.MEMO_TEAM
        assert comp.competition_type == CompetitionType.TEAM

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
            id="js-1",
            name="John Smith",
            country_id="country-gbr",
        )
        assert person.id == "js-1"
        assert person.name == "John Smith"
        assert person.country_id == "country-gbr"
        assert person.given_name is None
        assert person.family_name is None
        assert person.aliases == []
        assert person.source_ids == {}

    def test_create_person_full(self):
        person = Person(
            id="js-1",
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
            id="imo-2024-js-1",
            competition_id="imo-2024",
            person_id="js-1",
            country_id="country-gbr",
            problem_scores=[7, 7, 1, 7, 7, 0],
            total=29,
        )
        assert part.id == "imo-2024-js-1"
        assert part.competition_id == "imo-2024"
        assert part.person_id == "js-1"
        assert part.problem_scores == [7, 7, 1, 7, 7, 0]
        assert part.total == 29
        assert part.rank is None
        assert part.award is None

    def test_create_participation_full(self):
        part = Participation(
            id="imo-2024-js-1",
            competition_id="imo-2024",
            person_id="js-1",
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
            person_id="js-1",
            country_id="country-gbr",
            problem_scores=[7, None, 1, None, 7, 0],
            total=15,
        )
        assert part.problem_scores[1] is None
        assert part.problem_scores[3] is None


class TestTeamParticipation:
    def test_create_team_participation_minimal(self):
        tp = TeamParticipation(
            id="memo_team-2024-country-aut",
            competition_id="memo_team-2024",
            country_id="country-aut",
            problem_scores=[8, 8, 7, 8, 6, 8, 7, 8],
            total=60,
        )
        assert tp.id == "memo_team-2024-country-aut"
        assert tp.competition_id == "memo_team-2024"
        assert tp.country_id == "country-aut"
        assert tp.total == 60
        assert tp.rank is None
        assert tp.award is None
        assert tp.extra_awards is None

    def test_create_team_participation_full(self):
        tp = TeamParticipation(
            id="memo_team-2024-country-aut",
            competition_id="memo_team-2024",
            country_id="country-aut",
            problem_scores=[8, 8, 7, 8, 6, 8, 7, 8],
            total=60,
            rank=1,
            award=Award.GOLD,
            extra_awards="Best team",
        )
        assert tp.rank == 1
        assert tp.award == Award.GOLD
        assert tp.extra_awards == "Best team"

    def test_team_participation_with_none_scores(self):
        tp = TeamParticipation(
            id="test-tp",
            competition_id="balticway-2024",
            country_id="country-ltu",
            problem_scores=[5, None, 3, None, 5],
            total=13,
        )
        assert tp.problem_scores[1] is None
        assert tp.problem_scores[3] is None


class TestDatabase:
    def test_create_empty_database(self):
        db = Database(last_updated=datetime.now(UTC))
        assert db.version == "1.0"
        assert db.countries == {}
        assert db.competitions == {}
        assert db.people == {}
        assert db.participations == {}
        assert db.team_participations == {}

    def test_create_populated_database(self):
        country = Country(id="country-gbr", code="gbr", name="United Kingdom")
        comp = Competition(id="imo-2024", source=Source.IMO, year=2024, num_problems=6)
        person = Person(id="js-1", name="John Smith", country_id="country-gbr")
        part = Participation(
            id="imo-2024-js-1",
            competition_id="imo-2024",
            person_id="js-1",
            country_id="country-gbr",
            problem_scores=[7, 7, 7, 7, 7, 7],
            total=42,
        )

        db = Database(
            last_updated=datetime.now(UTC),
            countries={"country-gbr": country},
            competitions={"imo-2024": comp},
            people={"js-1": person},
            participations={"imo-2024-js-1": part},
        )

        assert len(db.countries) == 1
        assert len(db.competitions) == 1
        assert len(db.people) == 1
        assert len(db.participations) == 1

    def test_create_database_with_team_participations(self):
        comp = Competition(
            id="memo_team-2024",
            source=Source.MEMO_TEAM,
            year=2024,
            competition_type=CompetitionType.TEAM,
            num_problems=8,
        )
        tp = TeamParticipation(
            id="memo_team-2024-country-aut",
            competition_id="memo_team-2024",
            country_id="country-aut",
            problem_scores=[8, 8, 7, 8, 6, 8, 7, 8],
            total=60,
            rank=1,
            award=Award.GOLD,
        )
        db = Database(
            last_updated=datetime.now(UTC),
            competitions={"memo_team-2024": comp},
            team_participations={"memo_team-2024-country-aut": tp},
        )
        assert len(db.team_participations) == 1
        assert db.team_participations["memo_team-2024-country-aut"].total == 60

    def test_database_serialization_roundtrip(self):
        db = Database(
            last_updated=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            countries={"country-gbr": Country(id="country-gbr", code="gbr", name="United Kingdom")},
        )
        data = db.model_dump(mode="json")
        db2 = Database.model_validate(data)
        assert db2.countries["country-gbr"].name == "United Kingdom"
