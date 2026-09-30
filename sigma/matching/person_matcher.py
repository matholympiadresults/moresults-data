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


# Delimiters inside a single word after which the next letter starts a new
# segment that should be capitalized (hyphenated names, dotted initials,
# apostrophes). Both the ASCII and typographic apostrophe are included.
_WORD_SEGMENT_DELIMITERS = "-.'’"


def _titlecase_word(word: str) -> str:
    """Capitalize the first letter of each segment within a single word.

    ``word`` is assumed to already be lowercased. Segments are delimited by
    hyphens, periods and apostrophes, so every part of a compound name is
    capitalized while diacritics and the delimiters themselves are preserved:

        "sergiu-ionuț" -> "Sergiu-Ionuț"
        "l.k."         -> "L.K."
        "o'brien"      -> "O'Brien"

    Python's ``str.capitalize`` lowercases everything after the first letter
    (turning "SERGIU-IONUȚ" into "Sergiu-ionuț"), and ``str.title`` capitalizes
    after every apostrophe/digit, so neither is usable here.
    """
    result = []
    capitalize_next = True
    for ch in word:
        if ch in _WORD_SEGMENT_DELIMITERS:
            capitalize_next = True
            result.append(ch)
        elif capitalize_next and ch.isalpha():
            result.append(ch.upper())
            capitalize_next = False
        else:
            result.append(ch)
    return "".join(result)


def capitalize_name(name: str) -> str:
    """Convert a name to proper capitalization.

    Handles:
    - ALL CAPS names -> Title Case
    - all lowercase names -> Title Case
    - Mixed case names preserved (already properly formatted)
    - Common prefixes like "de", "van", "von", "da", "di" stay lowercase
    - Compound segments (hyphens, dotted initials) each get capitalized

    Examples:
        "JANE DOE" -> "Jane Doe"
        "john smith" -> "John Smith"
        "JEAN-PIERRE DUPONT" -> "Jean-Pierre Dupont"
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
            result.append(_titlecase_word(word))
        else:
            result.append(word)

    return " ".join(result)


# Spellings a source has since corrected, as {(normalized name, country_id):
# person_id}.
#
# `ingest_all_sources` reloads the database from disk for every (year, source)
# pair, so a rename made while ingesting one source is invisible to the next one
# unless it is remembered outside the database. Without that, renaming someone
# splits them off from any source that still lists the old name. This is process
# state on purpose: nothing about a superseded spelling is written to the stored
# data, which only ever carries the current name.
_superseded_names: dict[tuple[str, str], str] = {}


def reset_superseded_names() -> None:
    """Forget the renames seen so far. Call before a full rebuild."""
    _superseded_names.clear()


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

        # Spellings superseded earlier in this run resolve to the same person, so
        # that renaming someone here does not split them off from a source that
        # still lists the old name. Seeded second and never over an entry a
        # canonical name owns: a person's own name beats someone else's old one.
        for key, person_id in _superseded_names.items():
            if person_id in self.db.people:
                self._name_country_index.setdefault(key, person_id)

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

    def _adopt_name(
        self,
        person: Person,
        name: str,
        given_name: str | None,
        family_name: str | None,
    ) -> str | None:
        """Replace `person.name` with a newer spelling from the same source id.

        Sources correct and re-transliterate names between editions while
        keeping the same contestant id. `ingest-all` walks years in ascending
        order, so a source-id match carrying a different name is a later
        edition's spelling and supersedes what we stored.

        Names are compared exactly, so a restored diacritic ("Jamarber" ->
        "Jamarbër") or a case fix counts as a correction and is picked up.

        The superseded spelling is recorded on the Database, not on the person:
        it stays resolvable for the rest of the run so that other sources keep
        matching, but nothing about it is written to the stored data.

        Returns the previous name if it changed, else None.
        """
        new_name = capitalize_name(name)
        if new_name == person.name:
            return None

        previous_name = person.name
        person.name = new_name
        if given_name is not None:
            person.given_name = capitalize_name(given_name)
        if family_name is not None:
            person.family_name = capitalize_name(family_name)

        _superseded_names.setdefault((normalize_name(previous_name), person.country_id), person.id)
        self._name_country_index.setdefault(
            (normalize_name(new_name), person.country_id), person.id
        )
        return previous_name

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
    ) -> MatchResult:
        """
        Match incoming contestant to existing person or create new.

        Matching priority:
        1. Source ID match (same source + same ID = same person). A differing
           name is adopted as the current spelling; see `_adopt_name`.
        2. Exact name + country match (normalized: lowercase, accents stripped)
        3. Create new person
        """
        source_key = source.value.lower()

        # Phase 1: Try source ID match
        if source_contestant_id:
            person = self.find_by_source_id(source, source_contestant_id)
            if person:
                previous_name = self._adopt_name(person, name, given_name, family_name)
                reason = f"Source ID match ({source.value}: {source_contestant_id})"
                if previous_name is not None:
                    reason += f", renamed from '{previous_name}'"
                return MatchResult(
                    person_id=person.id,
                    is_new=False,
                    confidence=1.0,
                    reason=reason,
                )

        # Phase 2: Try exact name + country match
        match = self.find_by_exact_name(name, country_id)
        if match:
            person = self.db.people[match.person_id]
            if source_contestant_id and not person.source_ids.get(source_key):
                person.source_ids[source_key] = source_contestant_id
                self._source_id_index[(source_key, source_contestant_id)] = person.id
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
