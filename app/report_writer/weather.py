"""Visual Crossing Timeline API — historical wind for claim address + storm date."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from urllib.parse import quote

from fastapi import HTTPException

from app.config import VISUAL_CROSSING_API_KEY
from app.http_client import get_async_client

logger = logging.getLogger(__name__)

_TIMELINE_BASE = (
    "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
)

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%B %d, %Y",
    "%b %d, %Y",
    "%m/%d/%Y",
    "%m-%d-%Y",
)


@dataclass(frozen=True)
class WeatherSnapshot:
    wind_speed_mph: float | None
    wind_gust_mph: float | None
    stations: list[str]
    resolved_address: str
    latitude: float | None
    longitude: float | None
    date_iso: str
    date_display: str
    source: str = "visual_crossing"


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


def _parse_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_stations(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(s).strip() for s in value if str(s).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _snapshot_from_response(data: dict, storm_date: date) -> WeatherSnapshot:
    days = data.get("days") or []
    if not days:
        raise HTTPException(status_code=502, detail="Visual Crossing returned no daily weather data")

    day = days[0]
    wind_speed = _parse_float(day.get("windspeed"))
    wind_gust = _parse_float(day.get("windgust"))
    stations = _parse_stations(day.get("stations"))

    resolved = (data.get("resolvedAddress") or data.get("address") or "").strip()
    lat = _parse_float(data.get("latitude"))
    lon = _parse_float(data.get("longitude"))

    date_iso = storm_date.isoformat()
    date_display = storm_date.strftime("%B %d, %Y")

    return WeatherSnapshot(
        wind_speed_mph=wind_speed,
        wind_gust_mph=wind_gust,
        stations=stations,
        resolved_address=resolved,
        latitude=lat,
        longitude=lon,
        date_iso=date_iso,
        date_display=date_display,
    )


def weather_metadata_from_snapshot(snapshot: WeatherSnapshot, address: str) -> dict[str, str]:
    meta: dict[str, str] = {
        "weather_source": snapshot.source,
        "weather_date_iso": snapshot.date_iso,
        "weather_fetched_at": datetime.now(timezone.utc).isoformat(),
        "weather_fetch_key": weather_fetch_key(address, snapshot.date_iso),
    }
    if snapshot.wind_speed_mph is not None:
        meta["wind_speed_mph"] = str(round(snapshot.wind_speed_mph))
    if snapshot.wind_gust_mph is not None:
        meta["wind_gust_mph"] = str(round(snapshot.wind_gust_mph))
    if snapshot.stations:
        meta["weather_stations"] = ", ".join(snapshot.stations)
    if snapshot.resolved_address:
        meta["weather_resolved_address"] = snapshot.resolved_address
    return meta


async def fetch_weather_for_location(address: str, storm_date: date) -> WeatherSnapshot:
    if not VISUAL_CROSSING_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Visual Crossing API key is not configured (VISUAL_CROSSING_API_KEY)",
        )

    addr = address.strip()
    if len(addr) < 3:
        raise HTTPException(status_code=400, detail="Address is too short")

    date_str = storm_date.isoformat()
    encoded_addr = quote(addr, safe="")
    url = f"{_TIMELINE_BASE}/{encoded_addr}/{date_str}"

    client = get_async_client()
    try:
        resp = await client.get(
            url,
            params={
                "key": VISUAL_CROSSING_API_KEY,
                "unitGroup": "us",
                "include": "days",
                "elements": "windspeed,windgust,stations",
            },
            timeout=15.0,
        )
    except Exception as e:
        logger.warning("Visual Crossing request failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Weather API request failed: {e}") from e

    if resp.status_code == 401:
        raise HTTPException(status_code=502, detail="Visual Crossing API key is invalid")
    if resp.status_code == 429:
        raise HTTPException(status_code=503, detail="Weather API rate limit exceeded; try again later")
    if resp.status_code >= 400:
        detail = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
        raise HTTPException(status_code=502, detail=f"Weather API error: {detail}")

    try:
        data = resp.json()
    except ValueError as e:
        raise HTTPException(status_code=502, detail="Weather API returned invalid JSON") from e

    return _snapshot_from_response(data, storm_date)
