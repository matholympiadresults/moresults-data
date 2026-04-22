"""Helpers for normalising raw BMO team codes into a canonical form the
ingester understands.

The ingester strips a trailing contestant number (``\\s*\\d+$``) from the
country field, then looks the remainder up in `BMO_CODE_MAPPING`,
`VALID_ISO_CODES`, or `BMO_NAME_MAPPING`. Secondary teams are recognised by
either a concatenated suffix like ``"ROMB"``, ``"SRBB"``, ``"MKDB"``, ``"MDAB"``,
``"TURB"`` — or by a ``" - B"`` / ``" B"`` suffix on a no-digit code.

Year-specific parsers receive codes in many shapes (``"ROM1A"``, ``"ROM A1"``,
``"ROM B1"``, ``"SRBB1"``, ``"MDA2_1"``, ``"MKD-B"``). `canonical_team_code`
collapses them all into the canonical ``"<ISO><optional B><digit>"`` form.
"""

from __future__ import annotations

import re

# "ROM A1" / "ROM-B1" / "ROM_B_1" — A/B letter between base and contestant number.
_SPLIT_RE = re.compile(r"^\s*([A-Za-z]+)\s*[\s_\-]\s*([AB])\s*[\s_\-]?\s*(\d+)?\s*$")
# "MDA2_1" / "MDA2_6": the host country's second team, numbered as <base>2_<N>.
_HOST_SECOND_RE = re.compile(r"^\s*([A-Za-z]+)\s*2\s*_\s*(\d+)\s*$")
# "ALB1" / "UNK&IRL1" / "MKD1A" — base (any non-digit) followed by contestant
# number, with optional trailing letter.
_PLAIN_RE = re.compile(r"^\s*([A-Za-z&]+)\s*(\d+)?\s*([A-Za-z])?\s*$")


def canonical_team_code(raw: str) -> str:
    """Collapse a raw BMO team/contestant code into a canonical form.

    Handles shapes that are unambiguous across years:
      - ``"ROM A1"`` / ``"ROM-A1"`` → ``"ROM1"`` (A before number = main team)
      - ``"ROM B1"`` / ``"ROM-B1"`` → ``"ROMB1"`` (B before number = secondary)
      - ``"MDA2_1"`` → ``"MDAB1"`` (host's second team)
      - ``"ALB1"`` / ``"SRBB1"`` / ``"UNK&IRL1"`` → passthrough (with '&' stripped)

    Ambiguous shapes (such as ``"ROM1A"`` / ``"MKD1A"`` where the trailing
    letter means different things in different editions) are handled by the
    year-specific parsers rather than here.
    """
    raw = (raw or "").strip()

    m = _HOST_SECOND_RE.match(raw)
    if m:
        base, num = m.group(1), m.group(2)
        return f"{base.upper()}B{num}"

    m = _SPLIT_RE.match(raw)
    if m:
        base, letter, num = m.group(1), m.group(2).upper(), m.group(3) or ""
        if letter == "A":
            return f"{base.upper()}{num}"
        return f"{base.upper()}B{num}"

    m = _PLAIN_RE.match(raw)
    if m:
        base, num, trail = m.group(1), m.group(2) or "", m.group(3) or ""
        cleaned = (base + trail).upper().replace("&", "")
        return f"{cleaned}{num}"

    return raw.upper().replace(" ", "").replace("&", "")


# Family-name particles that absorb the following token (e.g. "Von Burg",
# "Al Saeed", "Di Bello"). Lowercased for comparison.
_FAMILY_PARTICLES = {
    "al",
    "da",
    "de",
    "del",
    "der",
    "di",
    "du",
    "la",
    "le",
    "van",
    "von",
}

_COUNTRY_BASE_RE = re.compile(r"^([A-Za-z]+?)B?\d*$")


def country_base(canonical: str) -> str:
    """Extract the letter-only country prefix of a canonical code.

    ``"SRB1"`` → ``"SRB"``, ``"ROMB1"`` → ``"ROM"`` (the trailing ``B``
    marker is dropped so callers can key on the base country alone).
    """
    m = _COUNTRY_BASE_RE.match(canonical)
    return m.group(1).upper() if m else canonical.upper()


def split_name(raw: str, *, surname_first: bool) -> tuple[str, str | None, str | None]:
    """Title-case ``raw`` and split it into ``(display, given, family)``.

    Handles particles like "von" and "al" that belong with the following
    family-name token. ``surname_first=True`` flips the tokens into the
    canonical "Given Surname" order used elsewhere in the database.
    """
    # Imported lazily to avoid a circular import with sigma.matching.
    from sigma.matching.person_matcher import capitalize_name

    titled = capitalize_name(raw)
    tokens = titled.split()
    if len(tokens) < 2:
        return titled, None, None

    if surname_first:
        if len(tokens) >= 3 and tokens[0].lower() in _FAMILY_PARTICLES:
            family_tokens = [tokens[0].lower(), tokens[1]]
            given_tokens = tokens[2:]
        else:
            family_tokens = [tokens[0]]
            given_tokens = tokens[1:]
    else:
        family_tokens = [tokens[-1]]
        given_tokens = tokens[:-1]

    family_name = " ".join(family_tokens)
    given_name = " ".join(given_tokens)
    name = f"{given_name} {family_name}"
    return name, given_name, family_name
