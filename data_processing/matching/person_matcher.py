"""Person matching logic for cross-competition tracking."""

from dataclasses import dataclass

from unidecode import unidecode

from data_processing.schemas import Database, Person, Source


def normalize_name(name: str) -> str:
    """Normalize a name for comparison: lowercase, strip accents, normalize whitespace."""
    return " ".join(unidecode(name).lower().strip().split())


def capitalize_name(name: str) -> str:
    """Convert a name to proper capitalization.

    Handles:
    - ALL CAPS names -> Title Case
    - all lowercase names -> Title Case
    - Mixed case names preserved (already properly formatted)
    - Common prefixes like "de", "van", "von", "da", "di" stay lowercase

    Examples:
        "JANE DOE" -> "Jane Doe"
        "john smith" -> "John Smith"
        "Johannes van der Berg" -> "Johannes van der Berg" (preserved)
        "JOHANNES VAN DER BERG" -> "Johannes van der Berg"
    """
    if not name:
        return name

    # Normalize whitespace first
    name = " ".join(name.strip().split())

    # Check if name is all uppercase or all lowercase (needs conversion)
    # Mixed case names are assumed to be already properly formatted
    if not (name.isupper() or name.islower()):
        return name

    # Common lowercase prefixes in names
    lowercase_prefixes = {"de", "van", "von", "da", "di", "del", "der", "la", "le", "du"}

    words = name.lower().split()
    result = []

    for i, word in enumerate(words):
        # First word is always capitalized, others check for prefixes
        if i == 0 or word not in lowercase_prefixes:
            result.append(word.capitalize())
        else:
            result.append(word)

    return " ".join(result)


@dataclass
class MatchCandidate:
    """A potential match for a person."""

    person_id: str
    confidence: float  # 0.0 to 1.0
    reason: str


@dataclass
class MatchResult:
    """Result of attempting to match a person."""

    person_id: str | None  # None if no match found
    is_new: bool  # True if a new person was created
    confidence: float
    reason: str


class PersonMatcher:
    """Matches incoming contestant data to existing people in the database."""

    def __init__(self, db: Database):
        self.db = db
        self._next_person_id = self._compute_next_id()

    def _compute_next_id(self) -> int:
        """Compute the next available person ID number."""
        if not self.db.people:
            return 1
        max_id = max(
            int(pid.replace("person-", ""))
            for pid in self.db.people.keys()
            if pid.startswith("person-")
        )
        return max_id + 1

    def _generate_person_id(self) -> str:
        """Generate a new unique person ID."""
        person_id = f"person-{self._next_person_id:06d}"
        self._next_person_id += 1
        return person_id

    def find_by_source_id(self, source: Source, source_id: str) -> Person | None:
        """Find a person by their source-specific ID."""
        source_key = source.value.lower()
        for person in self.db.people.values():
            if person.source_ids.get(source_key) == source_id:
                return person
        return None

    def find_by_exact_name(self, name: str, country_id: str) -> list[MatchCandidate]:
        """Find people with exact name match in the same country.

        Uses normalized comparison (lowercase, accents stripped, whitespace normalized).
        e.g., ė -> e, ü -> u, ž -> z
        """
        candidates = []
        name_normalized = normalize_name(name)

        for person in self.db.people.values():
            if person.country_id != country_id:
                continue

            # Check main name
            if normalize_name(person.name) == name_normalized:
                candidates.append(
                    MatchCandidate(
                        person_id=person.id,
                        confidence=1.0,
                        reason="Exact name + country match",
                    )
                )
                continue

            # Check aliases
            for alias in person.aliases:
                if normalize_name(alias) == name_normalized:
                    candidates.append(
                        MatchCandidate(
                            person_id=person.id,
                            confidence=0.95,
                            reason=f"Alias match: {alias}",
                        )
                    )
                    break

        return candidates

    def match_or_create(
        self,
        name: str,
        country_id: str,
        source: Source,
        source_contestant_id: str | None = None,
        given_name: str | None = None,
        family_name: str | None = None,
    ) -> MatchResult:
        """
        Match incoming contestant to existing person or create new.

        Matching priority:
        1. Source ID match (same source + same ID = same person)
        2. Exact name + country match (normalized: lowercase, accents stripped)
        3. Create new person
        """
        source_key = source.value.lower()

        # Phase 1: Try source ID match
        if source_contestant_id:
            person = self.find_by_source_id(source, source_contestant_id)
            if person:
                return MatchResult(
                    person_id=person.id,
                    is_new=False,
                    confidence=1.0,
                    reason=f"Source ID match ({source.value}: {source_contestant_id})",
                )

        # Phase 2: Try exact name + country match
        candidates = self.find_by_exact_name(name, country_id)
        if candidates:
            best = max(candidates, key=lambda c: c.confidence)
            # Update source_ids for the matched person
            person = self.db.people[best.person_id]
            if source_contestant_id and not person.source_ids.get(source_key):
                person.source_ids[source_key] = source_contestant_id
            return MatchResult(
                person_id=best.person_id,
                is_new=False,
                confidence=best.confidence,
                reason=best.reason,
            )

        # Phase 3: Create new person
        person_id = self._generate_person_id()
        source_ids = {
            "imo": None,
            "egmo": None,
            "memo": None,
            "rmm": None,
            "apmo": None,
            "bmo": None,
        }
        source_ids[source_key] = source_contestant_id

        # Normalize name capitalization (e.g., "ROBERT DRAGOMIRESCU" -> "Robert Dragomirescu")
        normalized_name = capitalize_name(name)
        normalized_given_name = capitalize_name(given_name) if given_name else None
        normalized_family_name = capitalize_name(family_name) if family_name else None

        new_person = Person(
            id=person_id,
            name=normalized_name,
            given_name=normalized_given_name,
            family_name=normalized_family_name,
            country_id=country_id,
            aliases=[],
            source_ids=source_ids,
        )
        self.db.people[person_id] = new_person

        return MatchResult(
            person_id=person_id,
            is_new=True,
            confidence=1.0,
            reason="New person created",
        )
