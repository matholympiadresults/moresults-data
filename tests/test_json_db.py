"""Tests for data_processing/database/json_db.py."""

import json
from datetime import UTC, datetime

from data_processing.database import create_empty_database, load_database, save_database
from data_processing.schemas import (
    Award,
    Competition,
    Country,
    Participation,
    Person,
    Source,
)


class TestCreateEmptyDatabase:
    def test_creates_database_with_defaults(self):
        db = create_empty_database()
        assert db.version == "1.0"
        assert db.countries == {}
        assert db.competitions == {}
        assert db.people == {}
        assert db.participations == {}

    def test_has_timestamp(self):
        before = datetime.now(UTC)
        db = create_empty_database()
        after = datetime.now(UTC)
        assert before <= db.last_updated <= after


class TestSaveAndLoadDatabase:
    def test_save_creates_file(self, tmp_path):
        db = create_empty_database()
        path = tmp_path / "test_db.json"
        save_database(db, path)
        assert path.exists()

    def test_save_creates_parent_directories(self, tmp_path):
        db = create_empty_database()
        path = tmp_path / "nested" / "dir" / "test_db.json"
        save_database(db, path)
        assert path.exists()

    def test_load_nonexistent_creates_empty(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        db = load_database(path)
        assert db.version == "1.0"
        assert db.countries == {}

    def test_roundtrip_empty_database(self, tmp_path):
        path = tmp_path / "test_db.json"
        db1 = create_empty_database()
        save_database(db1, path)
        db2 = load_database(path)
        assert db2.version == db1.version
        assert db2.countries == {}
        assert db2.competitions == {}

    def test_roundtrip_populated_database(self, tmp_path):
        path = tmp_path / "test_db.json"

        # Create populated database
        db1 = create_empty_database()
        db1.countries["country-gbr"] = Country(id="country-gbr", code="gbr", name="United Kingdom")
        db1.competitions["imo-2024"] = Competition(
            id="imo-2024",
            source=Source.IMO,
            year=2024,
            edition=65,
            host_country_id="country-gbr",
            num_problems=6,
        )
        db1.people["person-000001"] = Person(
            id="person-000001",
            name="John Smith",
            given_name="John",
            family_name="Smith",
            country_id="country-gbr",
            aliases=["J. Smith"],
            source_ids={"imo": "12345", "egmo": None, "memo": None},
        )
        db1.participations["imo-2024-person-000001"] = Participation(
            id="imo-2024-person-000001",
            competition_id="imo-2024",
            person_id="person-000001",
            country_id="country-gbr",
            problem_scores=[7, 7, 1, 7, 7, 0],
            total=29,
            rank=15,
            award=Award.GOLD,
            source_contestant_id="12345",
        )

        save_database(db1, path)
        db2 = load_database(path)

        # Verify countries
        assert "country-gbr" in db2.countries
        assert db2.countries["country-gbr"].name == "United Kingdom"

        # Verify competitions
        assert "imo-2024" in db2.competitions
        assert db2.competitions["imo-2024"].source == Source.IMO
        assert db2.competitions["imo-2024"].edition == 65

        # Verify people
        assert "person-000001" in db2.people
        assert db2.people["person-000001"].name == "John Smith"
        assert db2.people["person-000001"].aliases == ["J. Smith"]
        assert db2.people["person-000001"].source_ids["imo"] == "12345"

        # Verify participations
        assert "imo-2024-person-000001" in db2.participations
        part = db2.participations["imo-2024-person-000001"]
        assert part.problem_scores == [7, 7, 1, 7, 7, 0]
        assert part.total == 29
        assert part.award == Award.GOLD

    def test_save_updates_timestamp(self, tmp_path):
        path = tmp_path / "test_db.json"
        db = create_empty_database()
        old_timestamp = db.last_updated

        # Small delay to ensure timestamp changes
        import time

        time.sleep(0.01)

        save_database(db, path)
        assert db.last_updated > old_timestamp

    def test_saved_json_is_valid(self, tmp_path):
        path = tmp_path / "test_db.json"
        db = create_empty_database()
        db.countries["country-usa"] = Country(id="country-usa", code="usa", name="United States")
        save_database(db, path)

        # Verify it's valid JSON
        with open(path) as f:
            data = json.load(f)

        assert data["version"] == "1.0"
        assert "country-usa" in data["countries"]
        assert data["countries"]["country-usa"]["name"] == "United States"

    def test_saved_json_is_formatted(self, tmp_path):
        path = tmp_path / "test_db.json"
        db = create_empty_database()
        save_database(db, path)

        # Check indentation (should be pretty-printed)
        content = path.read_text()
        assert "\n" in content  # Has newlines
        assert "  " in content  # Has indentation
