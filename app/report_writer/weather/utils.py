"""Weather utility helpers."""

from __future__ import annotations

import math
import re
from datetime import date, datetime

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%B %d, %Y",
    "%b %d, %Y",
    "%m/%d/%Y",
    "%m-%d-%Y",
)


def normalize_address_for_key(address: str) -> str:
    return re.sub(r"\s+", " ", address.strip().lower())


def weather_fetch_key(address: str, date_iso: str) -> str:
    return f"{normalize_address_for_key(address)}|{date_iso}"


def parse_storm_date(raw: str) -> date:
    text = (raw or "").strip()
    if not text:
        raise ValueError("Storm date is required")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {raw!r}")


def parse_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_stations(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(s).strip() for s in value if str(s).strip()]
    return [str(value).strip()] if str(value).strip() else []


def haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles."""
    r = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def knots_to_mph(knots: float) -> float:
    return knots * 1.15078


def mm_to_inches(mm: float) -> float:
    return mm / 25.4
