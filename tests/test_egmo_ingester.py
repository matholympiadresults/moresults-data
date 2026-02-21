"""Tests for data_processing/sources/EGMO/ingester/egmo_ingester.py."""

import json

from data_processing.database import create_empty_database, get_or_create_country
from data_processing.schemas import Award, Source
from data_processing.sources.egmo.ingester.egmo_ingester import (
    convert_award,
    create_competition,
    ingest_results,
    load_results_from_file,
)
from data_processing.sources.egmo.scraper import (
    FIRST_EGMO_YEAR,
    edition_to_year,
)
from data_processing.sources.egmo.scraper.models import (
    ContestantResult,
    EGMOYearResults,
    ValidationResult,
)


def make_year_results(
    year: int,
    results: list[ContestantResult],
) -> EGMOYearResults:
    """Helper to create EGMOYearResults for testing."""
    edition = year - FIRST_EGMO_YEAR + 1
    return EGMOYearResults(
        year=year,
        edition=edition,
        source_url=f"https://www.egmo.org/egmos/egmo{edition}/scoreboard/",
        total_contestants=len(results),
        num_problems=len(results[0].problem_scores) if results else 0,
        results=results,
        validation=ValidationResult(all_totals_match=True, mismatches=[]),
    )


class TestEditionToYear:
    def test_first_egmo(self):
        assert edition_to_year(1) == 2012

    def test_recent_egmo(self):
        assert edition_to_year(13) == 2024

    def test_middle_egmo(self):
        assert edition_to_year(5) == 2016


class TestConvertAward:
    def test_gold(self):
        assert convert_award("Gold Medal") == Award.GOLD

    def test_silver(self):
        assert convert_award("Silver Medal") == Award.SILVER

    def test_bronze(self):
        assert convert_award("Bronze Medal") == Award.BRONZE

    def test_honourable_mention(self):
        assert convert_award("Honourable Mention") == Award.HONOURABLE_MENTION

    def test_none(self):
        assert convert_award(None) is None


class TestGetOrCreateCountry:
    def test_creates_new_country(self):
        db = create_empty_database()
        country = get_or_create_country(db, "gbr")

        assert country.id == "country-gbr"
        assert country.code == "gbr"
        assert country.name == "United Kingdom"
        assert "country-gbr" in db.countries

    def test_returns_existing_country(self):
        db = create_empty_database()
        # Create first
        country1 = get_or_create_country(db, "gbr")
        # Get existing
        country2 = get_or_create_country(db, "gbr")

        assert country1.id == country2.id
        assert len(db.countries) == 1


class TestCreateCompetition:
    def test_creates_competition(self):
        db = create_empty_database()
        data = make_year_results(
            year=2012,
            results=[
                ContestantResult(
                    person_id=1,
                    country_name="Test",
                    country_code="TST",
                    contestant_code="TST1",
                    given_name="Test",
                    family_name="User",
                    problem_scores=[7, 7, 7, 7, 7, 7],
                    total=42,
                    rank=1,
                    european_rank=1,
                    award=None,
                    extra_awards=None,
                )
            ],
        )

        competition = create_competition(db, data)

        assert competition.id == "egmo-2012"
        assert competition.source == Source.EGMO
        assert competition.year == 2012
        assert competition.edition == 1
        assert competition.num_problems == 6
        assert competition.max_score_per_problem == 7

    def test_returns_existing_competition(self):
        db = create_empty_database()
        data = make_year_results(
            year=2012,
            results=[
                ContestantResult(
                    person_id=1,
                    country_name="Test",
                    country_code="TST",
                    contestant_code="TST1",
                    given_name="Test",
                    family_name="User",
                    problem_scores=[7, 7, 7, 7, 7, 7],
                    total=42,
                    rank=1,
                    european_rank=1,
                    award=None,
                    extra_awards=None,
                )
            ],
        )

        comp1 = create_competition(db, data)
        comp2 = create_competition(db, data)

        assert comp1.id == comp2.id
        assert len(db.competitions) == 1


class TestIngestResults:
    def test_ingests_contestants(self):
        db = create_empty_database()
        data = make_year_results(
            year=2012,
            results=[
                ContestantResult(
                    person_id=1,
                    country_name="Bulgaria",
                    country_code="BGR",
                    contestant_code="BGR1",
                    given_name="Alice",
                    family_name="Example",
                    problem_scores=[7, 7, 7, 0, 7, 6, 7, 0],
                    total=41,
                    award="Gold Medal",
                    rank=1,
                    european_rank=1,
                    extra_awards=None,
                ),
                ContestantResult(
                    person_id=2,
                    country_name="Bulgaria",
                    country_code="BGR",
                    contestant_code="BGR2",
                    given_name="Test",
                    family_name="Person",
                    problem_scores=[7, 0, 0, 0, 0, 0, 0, 0],
                    total=7,
                    award=None,
                    rank=50,
                    european_rank=45,
                    extra_awards=None,
                ),
            ],
        )

        stats = ingest_results(db, data)

        assert stats["competition_id"] == "egmo-2012"
        assert stats["year"] == 2012
        assert stats["contestants"] == 2
        assert stats["new_people"] == 2
        assert stats["matched_people"] == 0

        # Check database
        assert len(db.countries) == 1
        assert len(db.competitions) == 1
        assert len(db.people) == 2
        assert len(db.participations) == 2

    def test_participation_data(self):
        db = create_empty_database()
        data = make_year_results(
            year=2012,
            results=[
                ContestantResult(
                    person_id=1,
                    country_name="Bulgaria",
                    country_code="BGR",
                    contestant_code="BGR1",
                    given_name="Alice",
                    family_name="Example",
                    problem_scores=[7, 7, 7, 0, 7, 6, 7, 0],
                    total=41,
                    award="Gold Medal",
                    rank=1,
                    european_rank=1,
                    extra_awards=None,
                ),
            ],
        )

        ingest_results(db, data)

        # Find the participation
        participation = list(db.participations.values())[0]

        assert participation.competition_id == "egmo-2012"
        assert participation.country_id == "country-bgr"
        assert participation.problem_scores == [7, 7, 7, 0, 7, 6, 7, 0]
        assert participation.total == 41
        assert participation.rank == 1
        assert participation.regional_rank == 1
        assert participation.award == Award.GOLD
        assert participation.source_contestant_id == "1"

    def test_person_matching_across_years(self):
        db = create_empty_database()

        # Year 1 - new person
        data1 = make_year_results(
            year=2012,
            results=[
                ContestantResult(
                    person_id=1,
                    country_name="Bulgaria",
                    country_code="BGR",
                    contestant_code="BGR1",
                    given_name="Alice",
                    family_name="Example",
                    problem_scores=[7, 7, 7, 0, 7, 6, 7, 0],
                    total=41,
                    award="Gold Medal",
                    rank=1,
                    european_rank=1,
                    extra_awards=None,
                ),
            ],
        )
        stats1 = ingest_results(db, data1)
        assert stats1["new_people"] == 1

        # Year 2 - same person (same source ID)
        data2 = make_year_results(
            year=2013,
            results=[
                ContestantResult(
                    person_id=1,  # Same person_id
                    country_name="Bulgaria",
                    country_code="BGR",
                    contestant_code="BGR1",
                    given_name="Alice",
                    family_name="Example",
                    problem_scores=[7, 7, 7, 7, 7, 7],
                    total=42,
                    award="Gold Medal",
                    rank=1,
                    european_rank=1,
                    extra_awards=None,
                ),
            ],
        )
        stats2 = ingest_results(db, data2)
        assert stats2["new_people"] == 0
        assert stats2["matched_people"] == 1

        # Only 1 person in database
        assert len(db.people) == 1
        # But 2 participations
        assert len(db.participations) == 2


class TestLoadResultsFromFile:
    def test_loads_json_file(self, tmp_path):
        # Create a test JSON file
        test_data = {
            "year": 2012,
            "edition": 1,
            "scraped_at": "2024-01-01T00:00:00+00:00",
            "source_url": "https://www.egmo.org/egmos/egmo1/scoreboard/",
            "total_contestants": 1,
            "num_problems": 6,
            "results": [
                {
                    "person_id": 1,
                    "country_name": "Test",
                    "country_code": "TST",
                    "contestant_code": "TST1",
                    "given_name": "Test",
                    "family_name": "User",
                    "problem_scores": [7, 7, 7, 7, 7, 7],
                    "total": 42,
                    "award": None,
                    "extra_awards": None,
                    "rank": 1,
                    "european_rank": 1,
                }
            ],
            "validation": {
                "all_totals_match": True,
                "mismatches": [],
            },
        }

        file_path = tmp_path / "egmo_2012.json"
        with open(file_path, "w") as f:
            json.dump(test_data, f)

        data = load_results_from_file(file_path)

        assert data.year == 2012
        assert data.edition == 1
        assert len(data.results) == 1
        assert data.results[0].given_name == "Test"
