"""Compose and split US property addresses stored in claim metadata."""

from __future__ import annotations

import re

_ZIP_RE = re.compile(r"^(\d{5})(?:-(\d{4}))?$")


def compose_full_address(meta: dict) -> str:
    """Build a single-line address from structured metadata fields."""
    line1 = (meta.get("address") or "").strip()
    line2 = (meta.get("address2") or "").strip()
    city = (meta.get("city") or "").strip()
    state = (meta.get("state") or "").strip().upper()
    zip_code = (meta.get("zip") or "").strip()

    if not line1 and not city and not state:
        return line1

    if city or state or zip_code:
        locality_parts: list[str] = []
        if city:
            locality_parts.append(city)
        state_zip = " ".join(p for p in (state, zip_code) if p)
        if state_zip:
            locality_parts.append(state_zip)
        locality = ", ".join(locality_parts)

        street_parts = [p for p in (line1, line2) if p]
        if street_parts and locality:
            return f"{', '.join(street_parts)}, {locality}"
        if street_parts:
            return ", ".join(street_parts)
        return locality

    if line2:
        return f"{line1}, {line2}" if line1 else line2
    return line1


def has_structured_address(meta: dict) -> bool:
    """True when city/state/zip (or address2) are stored separately."""
    return bool(
        (meta.get("city") or "").strip()
        or (meta.get("state") or "").strip()
        or (meta.get("zip") or "").strip()
        or (meta.get("address2") or "").strip()
    )


def split_legacy_address(raw: str) -> dict[str, str]:
    """Parse a legacy comma-separated full address into structured fields."""
    raw = (raw or "").strip()
    if not raw:
        return {"address": "", "address2": "", "city": "", "state": "", "zip": ""}

    parts = [p.strip() for p in raw.split(",")]
    if len(parts) < 2:
        return {"address": raw, "address2": "", "city": "", "state": "", "zip": ""}

    line1 = parts[0]
    remainder = parts[1:]

    if len(remainder) == 1:
        state_zip = remainder[0].split()
        if len(state_zip) >= 2 and len(state_zip[-2]) == 2 and state_zip[-2].isalpha():
            state = state_zip[-2].upper()
            zip_code = state_zip[-1] if _ZIP_RE.match(state_zip[-1]) else ""
            city = " ".join(state_zip[:-2]) if len(state_zip) > 2 else state_zip[0]
            return {
                "address": line1,
                "address2": "",
                "city": city,
                "state": state,
                "zip": zip_code,
            }
        return {"address": line1, "address2": "", "city": remainder[0], "state": "", "zip": ""}

    city = remainder[0]
    state_zip_part = remainder[-1].split()
    state = ""
    zip_code = ""
    if len(state_zip_part) >= 2 and len(state_zip_part[-2]) == 2 and state_zip_part[-2].isalpha():
        state = state_zip_part[-2].upper()
        if _ZIP_RE.match(state_zip_part[-1]):
            zip_code = state_zip_part[-1]
    elif len(state_zip_part) == 1 and len(state_zip_part[0]) == 2 and state_zip_part[0].isalpha():
        state = state_zip_part[0].upper()

    address2 = ", ".join(remainder[1:-1]) if len(remainder) > 2 else ""
    return {
        "address": line1,
        "address2": address2,
        "city": city,
        "state": state,
        "zip": zip_code,
    }


def report_address_lines(meta: dict) -> tuple[str, str, str]:
    """Return (line1, line2, full_address) for report export."""
    if has_structured_address(meta):
        line1 = (meta.get("address") or "").strip()
        address2 = (meta.get("address2") or "").strip()
        if address2:
            line1 = f"{line1}, {address2}" if line1 else address2

        city = (meta.get("city") or "").strip()
        state = (meta.get("state") or "").strip().upper()
        zip_code = (meta.get("zip") or "").strip()
        locality_parts: list[str] = []
        if city:
            locality_parts.append(city)
        state_zip = " ".join(p for p in (state, zip_code) if p)
        if state_zip:
            locality_parts.append(state_zip)
        line2 = ", ".join(locality_parts)
        full = compose_full_address(meta)
        return line1, line2, full or "Unknown"

    raw = (meta.get("address") or "").strip()
    if not raw:
        return "", "", "Unknown"
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) >= 3:
        return parts[0], ", ".join(parts[1:]), raw
    if len(parts) == 2:
        return parts[0], parts[1], raw
    return raw, "", raw
