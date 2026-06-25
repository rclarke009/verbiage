"""Extract address and storm metadata from ingested report text."""

from __future__ import annotations

import re

from app.storms.florida_storms import FLORIDA_STORMS, FloridaStorm

_REPORT_HEADER = re.compile(
    r"^engineering report\s*[-–—]\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)


def extract_address(text: str, title: str | None = None) -> str | None:
    """Parse property address from report header line or title."""
    for candidate in (title, text):
        if not candidate:
            continue
        first_line = candidate.strip().splitlines()[0].strip()
        match = _REPORT_HEADER.match(first_line)
        if match:
            addr = match.group(1).strip()
            return addr or None
    return None


def _storm_in_blob(blob: str, storm: FloridaStorm) -> bool:
    name = storm.name.lower()
    if f"hurricane {name}" in blob:
        return True
    if f"tropical storm {name}" in blob:
        return True
    if re.search(rf"\b{re.escape(name)}\b.*\b{storm.year}\b", blob):
        return True
    if re.search(rf"\b{storm.year}\b.*\b{re.escape(name)}\b", blob):
        return True
    return False


def detect_storm(text: str, title: str | None = None) -> tuple[str | None, str | None, str | None]:
    """Return (storm_id, storm_name, storm_date_iso) when a named storm is found."""
    blob = f"{title or ''}\n{text}".lower()
    for storm in FLORIDA_STORMS:
        if _storm_in_blob(blob, storm):
            return storm.id, storm.name, storm.landfall_date
    return None, None, None


def extract_document_metadata(
    text: str,
    *,
    title: str | None = None,
) -> dict[str, str | float | None]:
    """Best-effort metadata from report body and title."""
    address = extract_address(text, title)
    storm_id, storm_name, storm_date_iso = detect_storm(text, title)
    return {
        "address": address,
        "storm_id": storm_id,
        "storm_name": storm_name,
        "storm_date_iso": storm_date_iso,
        "latitude": None,
        "longitude": None,
    }
