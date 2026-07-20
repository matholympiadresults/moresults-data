"""Person matching logic for cross-competition tracking."""

from dataclasses import dataclass

from unidecode import unidecode

from sigma.schemas import Database, Person, Source


def normalize_name(name: str) -> str:
    """Normalize a name for comparison: lowercase, strip accents, normalize whitespace."""
    return " ".join(unidecode(name).lower().strip().split())


def compute_initials(name: str) -> str:
    """Compute lowercase initials from a name, using unidecode for non-ASCII characters.

    Examples:
        "John Smith" → "js"
        "Johannes van der Berg" → "jvdb"
        "Jane" → "j"
        "José García" → "jg"
    """
    transliterated = unidecode(name).strip()
    words = transliterated.split()
    return "".join(w[0].lower() for w in words if w)


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
        self._next_person_ids = self._compute_next_ids()
        self._build_indexes()

    def _compute_next_ids(self) -> dict[str, int]:
        """Compute the next available person ID number per initials group."""
        next_ids: dict[str, int] = {}
        for pid in self.db.people:
            initials, _, num_str = pid.rpartition("-")
            if initials and num_str.isdigit():
                num = int(num_str)
                next_ids[initials] = max(next_ids.get(initials, 0), num + 1)
        return next_ids

    def _build_indexes(self):
        """Build lookup indexes for O(1) matching."""
        # (source_key, source_id) -> person_id
        self._source_id_index: dict[tuple[str, str], str] = {}
        # (normalized_name, country_id) -> person_id
        self._name_country_index: dict[tuple[str, str], str] = {}

        for person in self.db.people.values():
            for source_key, source_id in person.source_ids.items():
                if source_id is not None:
                    self._source_id_index[(source_key, source_id)] = person.id
            self._name_country_index[(normalize_name(person.name), person.country_id)] = person.id

    def _generate_person_id(self, name: str) -> str:
        """Generate a new unique person ID based on name initials."""
        initials = compute_initials(name)
        num = self._next_person_ids.get(initials, 1)
        person_id = f"{initials}-{num}"
        self._next_person_ids[initials] = num + 1
        return person_id

    def find_by_source_id(self, source: Source, source_id: str) -> Person | None:
        """Find a person by their source-specific ID."""
        source_key = source.value.lower()
        person_id = self._source_id_index.get((source_key, source_id))
        if person_id is not None:
            return self.db.people[person_id]
        return None

    @staticmethod
    def _merge_aliases(person: Person, incoming: list[str] | None) -> None:
        """Add incoming names to person.aliases, skipping duplicates and the canonical name."""
        if not incoming:
            return
        seen = {normalize_name(a) for a in person.aliases}
        canonical = normalize_name(person.name)
        for alias in incoming:
            key = normalize_name(alias)
            if key and key != canonical and key not in seen:
                person.aliases.append(alias)
                seen.add(key)

    def find_by_exact_name(self, name: str, country_id: str) -> MatchCandidate | None:
        """Find a person with exact name match in the same country."""
        name_normalized = normalize_name(name)
        person_id = self._name_country_index.get((name_normalized, country_id))
        if person_id is not None:
            return MatchCandidate(
                person_id=person_id,
                confidence=1.0,
                reason="Exact name + country match",
            )
        return None

    def match_or_create(
        self,
        name: str,
        country_id: str,
        source: Source,
        source_contestant_id: str | None = None,
        given_name: str | None = None,
        family_name: str | None = None,
        aliases: list[str] | None = None,
    ) -> MatchResult:
        """
        Match incoming contestant to existing person or create new.

        Matching priority:
        1. Source ID match (same source + same ID = same person)
        2. Exact name + country match (normalized: lowercase, accents stripped)
        3. Create new person

        Any ``aliases`` supplied are recorded as known name variations on the
        matched or newly created person (see :meth:`_merge_aliases`).
        """
        source_key = source.value.lower()

        # Phase 1: Try source ID match
        if source_contestant_id:
            person = self.find_by_source_id(source, source_contestant_id)
            if person:
                self._merge_aliases(person, aliases)
                return MatchResult(
                    person_id=person.id,
                    is_new=False,
                    confidence=1.0,
                    reason=f"Source ID match ({source.value}: {source_contestant_id})",
                )

        # Phase 2: Try exact name + country match
        match = self.find_by_exact_name(name, country_id)
        if match:
            person = self.db.people[match.person_id]
            if source_contestant_id and not person.source_ids.get(source_key):
                person.source_ids[source_key] = source_contestant_id
                self._source_id_index[(source_key, source_contestant_id)] = person.id
            self._merge_aliases(person, aliases)
            return MatchResult(
                person_id=match.person_id,
                is_new=False,
                confidence=match.confidence,
                reason=match.reason,
            )

        # Phase 3: Create new person
        # Normalize name capitalization (e.g., "ROBERT DRAGOMIRESCU" -> "Robert Dragomirescu")
        normalized_name = capitalize_name(name)
        person_id = self._generate_person_id(normalized_name)
        source_ids = {
            "imo": None,
            "egmo": None,
            "memo": None,
            "rmm": None,
            "apmo": None,
            "bmo": None,
        }
        source_ids[source_key] = source_contestant_id

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
        self._merge_aliases(new_person, aliases)
        self.db.people[person_id] = new_person

        # Update indexes
        if source_contestant_id:
            self._source_id_index[(source_key, source_contestant_id)] = person_id
        self._name_country_index[(normalize_name(normalized_name), country_id)] = person_id

        return MatchResult(
            person_id=person_id,
            is_new=True,
            confidence=1.0,
            reason="New person created",
        )
