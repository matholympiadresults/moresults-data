"""ISO 3166-1 alpha-3 country codes - canonical source of truth.

This module provides the canonical list of valid ISO 3166-1 alpha-3 country codes
with their full names. This is the single source of truth for country codes in the system.

Competition-specific code normalization (IOC codes, B-teams, historical codes, etc.)
should be handled in the respective ingester modules.
"""

from typing import Annotated

from pydantic import AfterValidator

# ISO 3166-1 alpha-3 country codes with full names
# This is the canonical list of valid country codes
COUNTRY_NAMES: dict[str, str] = {
    # A
    "afg": "Afghanistan",
    "alb": "Albania",
    "dza": "Algeria",
    "ago": "Angola",
    "arg": "Argentina",
    "are": "United Arab Emirates",
    "arm": "Armenia",
    "aus": "Australia",
    "aut": "Austria",
    "aze": "Azerbaijan",
    # B
    "bdi": "Burundi",
    "bel": "Belgium",
    "ben": "Benin",
    "bfa": "Burkina Faso",
    "bgd": "Bangladesh",
    "bgr": "Bulgaria",
    "bhr": "Bahrain",
    "bhs": "Bahamas",
    "bih": "Bosnia and Herzegovina",
    "blr": "Belarus",
    "bol": "Bolivia",
    "bra": "Brazil",
    "brn": "Brunei",
    "btn": "Bhutan",
    "bwa": "Botswana",
    # C
    "can": "Canada",
    "che": "Switzerland",
    "chl": "Chile",
    "chn": "China",
    "civ": "Côte d'Ivoire",
    "cmr": "Cameroon",
    "cod": "Democratic Republic of the Congo",
    "cog": "Republic of the Congo",
    "col": "Colombia",
    "cri": "Costa Rica",
    "cub": "Cuba",
    "cyp": "Cyprus",
    "cze": "Czechia",
    # D
    "deu": "Germany",
    "dji": "Djibouti",
    "dnk": "Denmark",
    "dom": "Dominican Republic",
    # E
    "ecu": "Ecuador",
    "egy": "Egypt",
    "esp": "Spain",
    "est": "Estonia",
    "eth": "Ethiopia",
    "swz": "Eswatini",
    # F
    "fin": "Finland",
    "fra": "France",
    # G
    "gbr": "United Kingdom",
    "geo": "Georgia",
    "gha": "Ghana",
    "gmb": "Gambia",
    "grc": "Greece",
    "gtm": "Guatemala",
    # H
    "hkg": "Hong Kong",
    "hnd": "Honduras",
    "hrv": "Croatia",
    "hun": "Hungary",
    # I
    "idn": "Indonesia",
    "ind": "India",
    "irl": "Ireland",
    "irn": "Iran",
    "irq": "Iraq",
    "isl": "Iceland",
    "isr": "Israel",
    "ita": "Italy",
    # J
    "jam": "Jamaica",
    "jpn": "Japan",
    # K
    "kaz": "Kazakhstan",
    "ken": "Kenya",
    "kgz": "Kyrgyzstan",
    "khm": "Cambodia",
    "kor": "South Korea",
    "kwt": "Kuwait",
    "xkx": "Kosovo",  # XKX is the unofficial but widely used code
    # L
    "lao": "Laos",
    "lbr": "Liberia",
    "lby": "Libya",
    "lso": "Lesotho",
    "lie": "Liechtenstein",
    "lka": "Sri Lanka",
    "ltu": "Lithuania",
    "lux": "Luxembourg",
    "lva": "Latvia",
    # M
    "mac": "Macau",
    "mar": "Morocco",
    "mda": "Moldova",
    "mdg": "Madagascar",
    "mex": "Mexico",
    "mkd": "North Macedonia",
    "mli": "Mali",
    "mwi": "Malawi",
    "mmr": "Myanmar",
    "mne": "Montenegro",
    "mng": "Mongolia",
    "moz": "Mozambique",
    "mrt": "Mauritania",
    "mus": "Mauritius",
    "mys": "Malaysia",
    # N
    "nam": "Namibia",
    "ncy": "Northern Cyprus",  # Non-standard, used in some competitions
    "nga": "Nigeria",
    "nic": "Nicaragua",
    "nld": "Netherlands",
    "nor": "Norway",
    "npl": "Nepal",
    "nzl": "New Zealand",
    # O
    "omn": "Oman",
    # P
    "pak": "Pakistan",
    "pan": "Panama",
    "pry": "Paraguay",
    "per": "Peru",
    "phl": "Philippines",
    "pol": "Poland",
    "prk": "North Korea",
    "prt": "Portugal",
    "pri": "Puerto Rico",
    "pse": "Palestine",
    # Q
    "qat": "Qatar",
    # R
    "rou": "Romania",
    "rus": "Russia",
    "rwa": "Rwanda",
    # S
    "sau": "Saudi Arabia",
    "sen": "Senegal",
    "sgp": "Singapore",
    "sle": "Sierra Leone",
    "slv": "El Salvador",
    "srb": "Serbia",
    "ssd": "South Sudan",
    "svk": "Slovakia",
    "svn": "Slovenia",
    "swe": "Sweden",
    "syr": "Syria",
    # T
    "tgo": "Togo",
    "tha": "Thailand",
    "tjk": "Tajikistan",
    "tkm": "Turkmenistan",
    "tun": "Tunisia",
    "tur": "Türkiye",
    "twn": "Taiwan",
    "tza": "Tanzania",
    "tto": "Trinidad and Tobago",
    # U
    "uga": "Uganda",
    "ukr": "Ukraine",
    "ury": "Uruguay",
    "usa": "United States",
    "uzb": "Uzbekistan",
    # V
    "ven": "Venezuela",
    "vnm": "Vietnam",
    # Z
    "zaf": "South Africa",
    "zwe": "Zimbabwe",
    # Historical countries (no longer exist but appear in historical data)
    "uss": "Soviet Union",
    "yug": "Yugoslavia",
    "scg": "Serbia and Montenegro",
    "gdr": "East Germany",
    "csk": "Czechoslovakia",
    "cis": "Commonwealth of Independent States",
    # Special codes
    "unknown": "Unknown",  # Used for teams/countries that cannot be parsed
}

# Valid ISO codes (frozen for performance)
VALID_ISO_CODES: frozenset[str] = frozenset(COUNTRY_NAMES.keys())


def _validate_iso_country_code(code: str) -> str:
    """Validate that a code is a valid ISO country code."""
    if code not in VALID_ISO_CODES:
        raise ValueError(f"Invalid ISO country code: {code!r}")
    return code


# Type alias for validated ISO country codes
# When used with Pydantic, this validates at runtime
ISOCountryCode = Annotated[str, AfterValidator(_validate_iso_country_code)]


def get_country_name(code: str) -> str:
    """Get the full country name for an ISO code.

    Args:
        code: ISO 3166-1 alpha-3 code (lowercase)

    Returns:
        Full country name

    Raises:
        KeyError: If the code is not a valid ISO country code
    """
    return COUNTRY_NAMES[code.lower()]
