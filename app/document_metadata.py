"""Extract address and storm metadata from ingested report text."""

from __future__ import annotations

import re

from app.storms.florida_storms import FLORIDA_STORMS, FloridaStorm

_REPORT_HEADER = re.compile(
    r"^engineering report\s*[-–—]\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)

_ADDRESS_LABEL = re.compile(
    r"^Address:\s*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)

# Single-line US FL street address ending in ZIP (e.g. "1200 NE Example CR 100, Sampleville, FL 30070").
_FL_STREET_ZIP_LINE = re.compile(
    r"^\s*(\d{1,6}\s+.+?,\s*[^,\n]+,\s*FL\s+\d{5}(?:-\d{4})?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_FL_ZIP_IN_TEXT = re.compile(r",\s*FL\s+\d{5}(?:-\d{4})?\b", re.IGNORECASE)

# Stop collecting Address: continuation when a new labeled field or TOC-ish line appears.
_STOP_CONTINUATION = re.compile(
    r"^(Prepared\s+(for|by)|Owner|Report\s+Number|Date\s+of|"
    r"ENGINEERING|OVERVIEW|TABLE\s+OF|PAGE\s+\d|Contents)\b",
    re.IGNORECASE,
)


_ANY_STATE_ZIP = re.compile(
    r"^(.*?\b[A-Z]{2}\s+\d{5}(?:-\d{4})?)\b",
    re.IGNORECASE,
)


def _normalize_address(addr: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", addr).strip(" ,\t")
    cleaned = re.sub(r"\s*,\s*,+", ", ", cleaned)
    # Drop trailing junk after a state+ZIP (e.g. "… KS 66547 ROOF REPORT").
    zip_cut = _ANY_STATE_ZIP.match(cleaned)
    if zip_cut:
        cleaned = zip_cut.group(1).strip(" ,\t")
    return cleaned or None


def _has_fl_zip(addr: str) -> bool:
    return bool(_FL_ZIP_IN_TEXT.search(addr))


def _extract_from_report_header(text: str, title: str | None) -> str | None:
    for candidate in (title, text):
        if not candidate:
            continue
        first_line = candidate.strip().splitlines()[0].strip()
        match = _REPORT_HEADER.match(first_line)
        if match:
            return _normalize_address(match.group(1))
    return None


def _join_address_parts(parts: list[str]) -> str | None:
    cleaned = [p.strip(" ,\t") for p in parts if p and p.strip(" ,\t")]
    if not cleaned:
        return None
    if len(cleaned) == 1 or _has_fl_zip(cleaned[0]):
        return _normalize_address(" ".join(cleaned))
    # Street on one line, city/state/ZIP on the next.
    return _normalize_address(f"{cleaned[0]}, {' '.join(cleaned[1:])}")


def _extract_from_address_label(text: str) -> str | None:
    """Parse `Address:` lines, including street then city/state/zip on the next line(s)."""
    match = _ADDRESS_LABEL.search(text)
    if not match:
        return None

    parts: list[str] = []
    first = match.group(1).strip()
    if first:
        parts.append(first)
    if parts and _has_fl_zip(parts[0]):
        return _join_address_parts(parts)

    # Continuation lines after the Address: match (for multi-line property headers).
    # Skip the remainder of the Address: line / following newline before scanning.
    after = text[match.end() :]
    if after.startswith("\n") or after.startswith("\r"):
        after = after.lstrip("\r\n")

    seen_content = False
    for raw_line in after.splitlines():
        line = raw_line.strip()
        if not line:
            # Blank after we already collected a continuation → done.
            if seen_content:
                break
            continue
        if _STOP_CONTINUATION.match(line):
            break
        if re.match(r"^[A-Za-z][A-Za-z0-9 /_-]{0,40}:\s*", line) and not line.lower().startswith(
            "address:"
        ):
            break
        parts.append(line)
        seen_content = True
        if _has_fl_zip(" ".join(parts)):
            break
        # Cap runaway continuation (photo captions, etc.).
        if len(parts) >= 4:
            break

    return _join_address_parts(parts)


def _extract_fl_street_zip_fallback(text: str, title: str | None = None) -> str | None:
    """First FL street+city+ZIP line in title or early body when labels are missing."""
    for candidate in (title, text):
        if not candidate:
            continue
        # Prefer early header region to avoid appendix false positives.
        head = "\n".join(candidate.splitlines()[:60])
        match = _FL_STREET_ZIP_LINE.search(head)
        if match:
            return _normalize_address(match.group(1))
    return None


def extract_address(text: str, title: str | None = None) -> str | None:
    """Parse property address from report header, Address: label, or FL street/ZIP line."""
    for extractor in (
        lambda: _extract_from_report_header(text, title),
        lambda: _extract_from_address_label(text) if text else None,
        lambda: _extract_fl_street_zip_fallback(text, title),
    ):
        addr = extractor()
        if addr:
            return addr
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
