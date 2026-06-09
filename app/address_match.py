"""
Street-address normalization and fuzzy matching for Drive job folder lookup.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.similar_titles import normalize_for_similarity

_UNIT_SUFFIX_RE = re.compile(
    r"\s+(?:apt|apartment|unit|ste|suite|#)\s*[\w-]+$",
    re.IGNORECASE,
)
_HOUSE_NUMBER_RE = re.compile(r"^(\d+)\b")

# USPS-style suffix abbreviations -> canonical long form.
_STREET_SUFFIXES: dict[str, str] = {
    "st": "street",
    "str": "street",
    "street": "street",
    "dr": "drive",
    "driv": "drive",
    "drive": "drive",
    "ave": "avenue",
    "av": "avenue",
    "avenue": "avenue",
    "blvd": "boulevard",
    "boulevard": "boulevard",
    "ln": "lane",
    "lane": "lane",
    "rd": "road",
    "road": "road",
    "ct": "court",
    "court": "court",
    "cir": "circle",
    "circle": "circle",
    "pl": "place",
    "place": "place",
    "way": "way",
    "pkwy": "parkway",
    "parkway": "parkway",
    "hwy": "highway",
    "highway": "highway",
    "ter": "terrace",
    "terrace": "terrace",
    "trl": "trail",
    "trail": "trail",
}

# Directional abbreviations -> canonical long form (checked before suffixes).
_DIRECTIONALS: dict[str, str] = {
    "n": "north",
    "north": "north",
    "s": "south",
    "south": "south",
    "e": "east",
    "east": "east",
    "w": "west",
    "west": "west",
    "ne": "northeast",
    "northeast": "northeast",
    "nw": "northwest",
    "northwest": "northwest",
    "se": "southeast",
    "southeast": "southeast",
    "sw": "southwest",
    "southwest": "southwest",
}


def extract_street_line(address: str) -> str:
    """First comma-separated segment, with trailing unit designators removed."""
    street = (address or "").split(",", 1)[0].strip()
    street = _UNIT_SUFFIX_RE.sub("", street).strip()
    return street


def extract_folder_street_segment(folder_name: str) -> str:
    """Street portion of a folder name before ' - owner - client' suffix."""
    name = (folder_name or "").strip()
    if " - " in name:
        return name.split(" - ", 1)[0].strip()
    return name


def extract_house_number(s: str) -> str | None:
    """Leading house number digits, if present."""
    m = _HOUSE_NUMBER_RE.search((s or "").strip())
    return m.group(1) if m else None


def _expand_token(token: str, mapping: dict[str, str]) -> str:
    bare = token.rstrip(".")
    return mapping.get(bare, token)


def normalize_street_address(s: str) -> str:
    """
    Normalize a street address for fuzzy comparison.

    Lowercases, collapses whitespace, expands directionals and street suffixes
    to canonical long forms.
    """
    s = normalize_for_similarity(s)
    if not s:
        return ""
    tokens = s.split()
    expanded: list[str] = []
    for token in tokens:
        bare = token.rstrip(".")
        if bare in _DIRECTIONALS:
            expanded.append(_DIRECTIONALS[bare])
        elif bare in _STREET_SUFFIXES:
            expanded.append(_STREET_SUFFIXES[bare])
        else:
            expanded.append(token.rstrip("."))
    return " ".join(expanded)


def _similarity_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def house_numbers_conflict(addr: str, folder_name: str) -> bool:
    """True when both sides have a house number and they differ."""
    addr_num = extract_house_number(extract_street_line(addr))
    folder_num = extract_house_number(extract_folder_street_segment(folder_name))
    if addr_num and folder_num and addr_num != folder_num:
        return True
    return False


def address_folder_similarity(address: str, folder_name: str) -> float:
    """
    Score how well a claim address matches a Drive folder name.

    Compares normalized street line against the folder's street segment (before
    ' - ') and against the full folder base name; returns the higher score.
    """
    street = extract_street_line(address)
    addr_norm = normalize_street_address(street)
    if not addr_norm:
        return 0.0

    segment = extract_folder_street_segment(folder_name)
    segment_norm = normalize_street_address(segment)
    full_norm = normalize_street_address(folder_name)

    scores = [_similarity_ratio(addr_norm, segment_norm)]
    if full_norm != segment_norm:
        scores.append(_similarity_ratio(addr_norm, full_norm))
    return max(scores)
