"""JSON database operations for olympiad data."""

import json
from datetime import UTC, datetime
from pathlib import Path

from sigma.country_codes import ISOCountryCode, get_country_name
from sigma.schemas import Country, Database

DEFAULT_DB_PATH = Path("data/olympiad_data.json")


def create_empty_database() -> Database:
    """Create a new empty database."""
    return Database(
        version="1.0",
        last_updated=datetime.now(UTC),
        countries={},
        competitions={},
        people={},
        participations={},
        team_participations={},
    )


def load_database(path: Path = DEFAULT_DB_PATH) -> Database:
    """Load database from JSON file. Creates new if file doesn't exist."""
    if not path.exists():
        return create_empty_database()

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return Database.model_validate(data)


def save_database(db: Database, path: Path = DEFAULT_DB_PATH) -> None:
    """Save database to JSON file."""
    # Update timestamp
    db.last_updated = datetime.now(UTC)

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(db.model_dump_json(indent=2))


def get_or_create_country(
    db: Database,
    code: ISOCountryCode,
) -> Country:
    """Get existing country or create a new one.

    This is the canonical way to get/create countries in the database.
    Ingesters should normalize their source-specific codes BEFORE calling this.

    Args:
        db: The database instance
        code: Normalized ISO 3166-1 alpha-3 code (lowercase)

    Returns:
        The Country object (existing or newly created)
    """
    country_id = f"country-{code}"
    if country_id not in db.countries:
        db.countries[country_id] = Country(
            id=country_id,
            code=code,
            name=get_country_name(code),
        )

    return db.countries[country_id]
