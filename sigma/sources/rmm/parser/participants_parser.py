"""
RMM Participants Page Parser

Parses the participants page (id=participants_math) to extract contestant names
in their correct first-last order. This is used to fix multi-word names from the
results page, where the "Last First" format (2018+) can't be reliably split when
names have more than 2 words.
"""

import re

from unidecode import unidecode


def parse_participants_html(html: str) -> dict[tuple[str, int], str]:
    """Parse participants page HTML to extract contestant names by country and number.

    The participants page lists contestants grouped by country, with names in the
    correct first-last order and contestant numbers (e.g., "Contestant 1").

    Args:
        html: Raw HTML content of the participants page

    Returns:
        Dict mapping (country_code, contestant_number) to contestant name.
        Country codes are uppercase (e.g., "BGR", "USA").
    """
    flag_pattern = r"_flags/(\w+)\.gif"
    contestant_pattern = r"Name:\s*<b>([^<]+)</b>\s*\(Contestant<[^>]+>\s*(\d+)\)"

    flag_matches = list(re.finditer(flag_pattern, html))
    contestant_matches = list(re.finditer(contestant_pattern, html))

    participants: dict[tuple[str, int], str] = {}
    for i, fm in enumerate(flag_matches):
        country_code = fm.group(1).upper()
        start = fm.start()
        end = flag_matches[i + 1].start() if i + 1 < len(flag_matches) else len(html)

        for cm in contestant_matches:
            if start <= cm.start() < end:
                # Normalize whitespace (some entries have double spaces)
                name = " ".join(cm.group(1).split())
                num = int(cm.group(2))
                participants[(country_code, num)] = name

    return participants


def _normalize_for_comparison(name: str) -> set[str]:
    """Normalize a name into a set of lowercase, accent-stripped word tokens."""
    return {unidecode(w).lower() for w in name.split()}


def resolve_multiword_name(
    results_name: str,
    participants: dict[tuple[str, int], str],
    country_code: str,
    contestant_num: int | None,
) -> str | None:
    """Look up a multi-word name from the participants page.

    Only returns a name if:
    - The contestant number is known
    - A matching entry exists in the participants data
    - The name words overlap (same person, different ordering — not a roster change)

    Args:
        results_name: The name as it appears on the results page (before any swap)
        participants: Parsed participants data from parse_participants_html()
        country_code: Uppercase country code (e.g., "HUN")
        contestant_num: Contestant number from the country column (e.g., 1 for "HUN 1")

    Returns:
        The correctly ordered name from the participants page, or None if no
        reliable match was found.
    """
    if contestant_num is None:
        return None

    key = (country_code, contestant_num)
    if key not in participants:
        return None

    participant_name = participants[key]

    # Verify the names refer to the same person by checking word overlap.
    # This guards against roster changes (common for ROU) where the contestant
    # numbers don't correspond between the two pages.
    results_words = _normalize_for_comparison(results_name)
    participant_words = _normalize_for_comparison(participant_name)

    if results_words != participant_words:
        return None

    return participant_name
