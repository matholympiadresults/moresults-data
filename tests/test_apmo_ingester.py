"""Tests for data_processing/sources/apmo/ingester.py."""

import json

from data_processing.database import create_empty_database, get_or_create_country
from data_processing.schemas import Award, Source
from data_processing.sources.apmo.apmo_downloader import (
    APMOScoreboard,
    Contestant,
)
from data_processing.sources.apmo.apmo_downloader import (
    Award as APMOAward,
)
from data_processing.sources.apmo.ingester import (
    apmo_year_to_edition,
    convert_award,
    create_competition,
    ingest_scoreboard,
    load_scoreboard_from_file,
)


class TestYearToEdition:
    def test_first_apmo(self):
        assert apmo_year_to_edition(1989) == 1

    def test_recent_apmo(self):
        assert apmo_year_to_edition(2024) == 36

    def test_middle_apmo(self):
        assert apmo_year_to_edition(2000) == 12


class TestConvertAward:
    def test_gold(self):
        assert convert_award(APMOAward.GOLD) == Award.GOLD

    def test_silver(self):
        assert convert_award(APMOAward.SILVER) == Award.SILVER

    def test_bronze(self):
        assert convert_award(APMOAward.BRONZE) == Award.BRONZE

    def test_honourable_mention(self):
        assert convert_award(APMOAward.HONOURABLE_MENTION) == Award.HONOURABLE_MENTION

    def test_none(self):
        assert convert_award(None) is None


class TestGetOrCreateCountry:
    def test_creates_new_country(self):
        db = create_empty_database()
        country = get_or_create_country(db, "jpn")

        assert country.id == "country-jpn"
        assert country.code == "jpn"
        assert country.name == "Japan"
        assert "country-jpn" in db.countries

    def test_returns_existing_country(self):
        db = create_empty_database()
        country1 = get_or_create_country(db, "jpn")
        country2 = get_or_create_country(db, "jpn")

        assert country1.id == country2.id
        assert len(db.countries) == 1


class TestCreateCompetition:
    def test_creates_competition(self):
        db = create_empty_database()
        scoreboard = APMOScoreboard(
            year=2024,
            scraped_at="2024-01-01T00:00:00Z",
            contestants=[
                Contestant(
                    country_name="Japan",
                    country_code="JPN",
                    given_name="Test",
                    family_name="User",
                    problem_scores=[7, 7, 7, 7, 7],
                    total=35,
                )
            ],
        )

        competition = create_competition(db, scoreboard)

        assert competition.id == "apmo-2024"
        assert competition.source == Source.APMO
        assert competition.year == 2024
        assert competition.edition == 36
        assert competition.num_problems == 5
        assert competition.max_score_per_problem == 7

    def test_returns_existing_competition(self):
        db = create_empty_database()
        scoreboard = APMOScoreboard(
            year=2024,
            scraped_at="2024-01-01T00:00:00Z",
            contestants=[
                Contestant(
                    country_name="Japan",
                    country_code="JPN",
                    given_name="Test",
                    family_name="User",
                    problem_scores=[7, 7, 7, 7, 7],
                    total=35,
                )
            ],
        )

        comp1 = create_competition(db, scoreboard)
        comp2 = create_competition(db, scoreboard)

        assert comp1.id == comp2.id
        assert len(db.competitions) == 1


class TestIngestScoreboard:
    def test_ingests_contestants(self):
        db = create_empty_database()
        scoreboard = APMOScoreboard(
            year=2024,
            scraped_at="2024-01-01T00:00:00Z",
            contestants=[
                Contestant(
                    country_name="Japan",
                    country_code="JPN",
                    given_name="Foo",
                    family_name="Bar",
                    problem_scores=[7, 7, 0, 0, 7],
                    total=21,
                    award=APMOAward.GOLD,
                    rank=1,
                ),
                Contestant(
                    country_name="Japan",
                    country_code="JPN",
                    given_name="Baz",
                    family_name="Qux",
                    problem_scores=[7, 6, 0, 0, 7],
                    total=20,
                    award=APMOAward.SILVER,
                    rank=2,
                ),
            ],
        )

        stats = ingest_scoreboard(db, scoreboard)

        assert stats["competition_id"] == "apmo-2024"
        assert stats["year"] == 2024
        assert stats["contestants"] == 2
        assert stats["new_people"] == 2
        assert stats["matched_people"] == 0

        assert len(db.countries) == 1
        assert len(db.competitions) == 1
        assert len(db.people) == 2
        assert len(db.participations) == 2

    def test_participation_data(self):
        db = create_empty_database()
        scoreboard = APMOScoreboard(
            year=2024,
            scraped_at="2024-01-01T00:00:00Z",
            contestants=[
                Contestant(
                    country_name="Japan",
                    country_code="JPN",
                    given_name="Foo",
                    family_name="Bar",
                    problem_scores=[7, 7, 0, 0, 7],
                    total=21,
                    award=APMOAward.GOLD,
                    rank=1,
                ),
            ],
        )

        ingest_scoreboard(db, scoreboard)

        participation = list(db.participations.values())[0]

        assert participation.competition_id == "apmo-2024"
        assert participation.country_id == "country-jpn"
        assert participation.problem_scores == [7, 7, 0, 0, 7]
        assert participation.total == 21
        assert participation.rank == 1
        assert participation.regional_rank is None  # APMO doesn't have regional rank
        assert participation.award == Award.GOLD
        assert participation.source_contestant_id is None  # APMO doesn't have IDs

    def test_person_matching_across_years(self):
        db = create_empty_database()

        # Year 1 - new person
        scoreboard1 = APMOScoreboard(
            year=2023,
            scraped_at="2023-01-01T00:00:00Z",
            contestants=[
                Contestant(
                    country_name="Japan",
                    country_code="JPN",
                    given_name="Foo",
                    family_name="Bar",
                    problem_scores=[7, 7, 7, 0, 0],
                    total=21,
                    award=APMOAward.GOLD,
                    rank=1,
                ),
            ],
        )
        stats1 = ingest_scoreboard(db, scoreboard1)
        assert stats1["new_people"] == 1

        # Year 2 - same person (matched by name and country)
        scoreboard2 = APMOScoreboard(
            year=2024,
            scraped_at="2024-01-01T00:00:00Z",
            contestants=[
                Contestant(
                    country_name="Japan",
                    country_code="JPN",
                    given_name="Foo",
                    family_name="Bar",
                    problem_scores=[7, 7, 0, 0, 7],
                    total=21,
                    award=APMOAward.GOLD,
                    rank=1,
                ),
            ],
        )
        stats2 = ingest_scoreboard(db, scoreboard2)
        assert stats2["new_people"] == 0
        assert stats2["matched_people"] == 1

        # Only 1 person in database
        assert len(db.people) == 1
        # But 2 participations
        assert len(db.participations) == 2


class TestLoadScoreboardFromFile:
    def test_loads_json_file(self, tmp_path):
        test_data = {
            "year": 2024,
            "scraped_at": "2024-01-01T00:00:00Z",
            "contestants": [
                {
                    "country_name": "Japan",
                    "country_code": "JPN",
                    "given_name": "Test",
                    "family_name": "User",
                    "problem_scores": [7, 7, 7, 7, 7],
                    "total": 35,
                    "award": None,
                    "rank": 1,
                }
            ],
        }

        file_path = tmp_path / "apmo_2024.json"
        with open(file_path, "w") as f:
            json.dump(test_data, f)

        scoreboard = load_scoreboard_from_file(file_path)

        assert scoreboard.year == 2024
        assert len(scoreboard.contestants) == 1
        assert scoreboard.contestants[0].given_name == "Test"
