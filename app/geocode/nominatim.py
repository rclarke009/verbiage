"""OpenStreetMap Nominatim address search and formatting."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from app.geocode.address_format import compose_full_address
from app.config import NOMINATIM_BASE_URL, NOMINATIM_USER_AGENT
from app.http_client import get_async_client

logger = logging.getLogger(__name__)

# Nominatim public API: max 1 request per second.
_MIN_REQUEST_INTERVAL_S = 1.0
_last_request_at = 0.0
_request_lock = asyncio.Lock()

_US_STATE_ABBREV: dict[str, str] = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}


@dataclass(frozen=True)
class AddressSuggestion:
    id: str
    label: str
    address: str
    address2: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""


@dataclass(frozen=True)
class GeocodeResult:
    latitude: float
    longitude: float
    resolved_address: str


def _pick_city(address: dict[str, Any]) -> str:
    for key in ("city", "town", "village", "hamlet", "municipality"):
        value = (address.get(key) or "").strip()
        if value:
            return value
    return ""


def _state_abbrev(state_raw: str) -> str | None:
    state = (state_raw or "").strip()
    if not state:
        return None
    if len(state) == 2 and state.isalpha():
        return state.upper()
    return _US_STATE_ABBREV.get(state.lower())


def _street_line(address: dict[str, Any]) -> str:
    house = (address.get("house_number") or "").strip()
    road = (address.get("road") or address.get("street") or "").strip()
    if house and road:
        return f"{house} {road}"
    return road or house


def _pick_address2(address: dict[str, Any]) -> str:
    for key in ("unit", "apartment", "suite", "level"):
        value = (address.get(key) or "").strip()
        if value:
            return value
    return ""


def format_nominatim_result(item: dict[str, Any]) -> AddressSuggestion | None:
    """Convert a Nominatim jsonv2 result into a suggestion, or None if unusable."""
    place_id = item.get("place_id")
    if place_id is None:
        return None

    addr = item.get("address") or {}
    street = _street_line(addr)
    address2 = _pick_address2(addr)
    city = _pick_city(addr)
    state_abbr = _state_abbrev(addr.get("state") or "")
    postcode = (addr.get("postcode") or "").strip()

    if not street or not city or not state_abbr:
        return None

    formatted = f"{street}, {city}, {state_abbr}"
    label = f"{formatted}{f' {postcode}' if postcode else ''}"
    return AddressSuggestion(
        id=str(place_id),
        label=label,
        address=street,
        address2=address2,
        city=city,
        state=state_abbr,
        zip=postcode,
    )


async def _throttled_get(url: str, *, params: dict[str, str | int]) -> Any:
    global _last_request_at

    async with _request_lock:
        now = time.monotonic()
        wait = _MIN_REQUEST_INTERVAL_S - (now - _last_request_at)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request_at = time.monotonic()

    client = get_async_client()
    resp = await client.get(
        url,
        params=params,
        headers={"User-Agent": NOMINATIM_USER_AGENT},
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()


async def search_addresses(query: str, *, limit: int = 5) -> list[AddressSuggestion]:
    """Search Nominatim for US street addresses matching query."""
    q = (query or "").strip()
    if len(q) < 3:
        return []

    limit = max(1, min(limit, 10))
    params = {
        "q": q,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": limit,
        "countrycodes": "us",
        "dedupe": 1,
    }
    url = f"{NOMINATIM_BASE_URL.rstrip('/')}/search"

    try:
        data = await _throttled_get(url, params=params)
    except Exception as e:
        logger.warning("Nominatim search failed for %r: %s", q, e)
        return []

    if not isinstance(data, list):
        return []

    suggestions: list[AddressSuggestion] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        suggestion = format_nominatim_result(item)
        if not suggestion:
            continue
        dedupe_key = f"{suggestion.address}|{suggestion.city}|{suggestion.state}|{suggestion.zip}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        suggestions.append(suggestion)
    return suggestions


async def geocode_address(address: str) -> GeocodeResult | None:
    """Resolve a US address to coordinates via Nominatim search."""
    q = (address or "").strip()
    if len(q) < 3:
        return None

    params = {
        "q": q,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 1,
        "countrycodes": "us",
    }
    url = f"{NOMINATIM_BASE_URL.rstrip('/')}/search"

    try:
        data = await _throttled_get(url, params=params)
    except Exception as e:
        logger.warning("Nominatim geocode failed for %r: %s", q, e)
        return None

    if not isinstance(data, list) or not data:
        return None

    item = data[0]
    if not isinstance(item, dict):
        return None

    lat = item.get("lat")
    lon = item.get("lon")
    if lat is None or lon is None:
        return None

    suggestion = format_nominatim_result(item)
    if suggestion:
        resolved = compose_full_address(
            {
                "address": suggestion.address,
                "address2": suggestion.address2,
                "city": suggestion.city,
                "state": suggestion.state,
                "zip": suggestion.zip,
            }
        )
    else:
        resolved = q
    try:
        return GeocodeResult(
            latitude=float(lat),
            longitude=float(lon),
            resolved_address=resolved,
        )
    except (TypeError, ValueError):
        return None
