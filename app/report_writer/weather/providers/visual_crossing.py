"""Visual Crossing Timeline API — daily/hourly wind, precip, and storm events."""

from __future__ import annotations

import logging
from datetime import date
from urllib.parse import quote

from fastapi import HTTPException

from app.config import VISUAL_CROSSING_API_KEY
from app.http_client import get_async_client
from app.report_writer.weather.types import GeoContext, WeatherCandidate
from app.report_writer.weather.utils import haversine_mi, parse_float, parse_stations

logger = logging.getLogger(__name__)

_TIMELINE_BASE = (
    "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
)


async def fetch_geocontext(address: str, storm_date: date) -> GeoContext:
    """Geocode address and return lat/lon via a minimal Visual Crossing request."""
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
        logger.warning("Visual Crossing geocode request failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Weather API request failed: {e}") from e

    if resp.status_code == 401:
        raise HTTPException(status_code=502, detail="Visual Crossing API key is invalid")
    if resp.status_code == 429:
        raise HTTPException(status_code=503, detail="Weather API rate limit exceeded; try again later")
    if resp.status_code >= 400:
        detail = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
        raise HTTPException(status_code=502, detail=f"Weather API error: {detail}")

    data = resp.json()
    days = data.get("days") or []
    day = days[0] if days else {}
    stations = parse_stations(day.get("stations"))

    return GeoContext(
        address=addr,
        storm_date=storm_date,
        latitude=parse_float(data.get("latitude")),
        longitude=parse_float(data.get("longitude")),
        resolved_address=(data.get("resolvedAddress") or data.get("address") or "").strip(),
        stations=stations,
    )


async def fetch_candidates(ctx: GeoContext) -> list[WeatherCandidate]:
    if not VISUAL_CROSSING_API_KEY:
        return []

    date_str = ctx.storm_date.isoformat()
    encoded_addr = quote(ctx.address, safe="")
    url = f"{_TIMELINE_BASE}/{encoded_addr}/{date_str}"

    client = get_async_client()
    try:
        resp = await client.get(
            url,
            params={
                "key": VISUAL_CROSSING_API_KEY,
                "unitGroup": "us",
                "include": "days,hours,events",
                "elements": "datetime,windspeed,windgust,precip,stations",
            },
            timeout=20.0,
        )
    except Exception as e:
        logger.warning("Visual Crossing full request failed: %s", e)
        return []

    if resp.status_code >= 400:
        logger.warning("Visual Crossing full request HTTP %s", resp.status_code)
        return []

    data = resp.json()
    lat = parse_float(data.get("latitude")) or ctx.latitude
    lon = parse_float(data.get("longitude")) or ctx.longitude
    days = data.get("days") or []
    if not days:
        return []

    day = days[0]
    candidates: list[WeatherCandidate] = []

    daily_speed = parse_float(day.get("windspeed"))
    daily_gust = parse_float(day.get("windgust"))
    daily_precip = parse_float(day.get("precip"))
    stations = parse_stations(day.get("stations")) or ctx.stations
    station_label = ", ".join(stations) if stations else "interpolated"

    if daily_speed is not None:
        candidates.append(
            WeatherCandidate(
                id="vc:daily:wind_speed",
                metric="wind_speed",
                value=round(daily_speed, 1),
                unit="mph",
                source="visual_crossing",
                label=f"Visual Crossing daily ({station_label})",
                tier=3,
                station=stations[0] if stations else None,
            )
        )
    if daily_gust is not None:
        candidates.append(
            WeatherCandidate(
                id="vc:daily:wind_gust",
                metric="wind_gust",
                value=round(daily_gust, 1),
                unit="mph",
                source="visual_crossing",
                label=f"Visual Crossing daily ({station_label})",
                tier=3,
                station=stations[0] if stations else None,
            )
        )
    if daily_precip is not None and daily_precip > 0:
        candidates.append(
            WeatherCandidate(
                id="vc:daily:precip",
                metric="precip",
                value=round(daily_precip, 2),
                unit="in",
                source="visual_crossing",
                label=f"Visual Crossing daily ({station_label})",
                tier=3,
            )
        )

    hours = day.get("hours") or []
    hourly_speeds = [parse_float(h.get("windspeed")) for h in hours]
    hourly_gusts = [parse_float(h.get("windgust")) for h in hours]
    max_hourly_speed = max((v for v in hourly_speeds if v is not None), default=None)
    max_hourly_gust = max((v for v in hourly_gusts if v is not None), default=None)

    if max_hourly_speed is not None and (daily_speed is None or max_hourly_speed > daily_speed):
        candidates.append(
            WeatherCandidate(
                id="vc:hourly:wind_speed",
                metric="wind_speed",
                value=round(max_hourly_speed, 1),
                unit="mph",
                source="visual_crossing",
                label=f"Visual Crossing hourly max ({station_label})",
                tier=3,
                station=stations[0] if stations else None,
            )
        )
    if max_hourly_gust is not None and (daily_gust is None or max_hourly_gust > daily_gust):
        candidates.append(
            WeatherCandidate(
                id="vc:hourly:wind_gust",
                metric="wind_gust",
                value=round(max_hourly_gust, 1),
                unit="mph",
                source="visual_crossing",
                label=f"Visual Crossing hourly max ({station_label})",
                tier=3,
                station=stations[0] if stations else None,
            )
        )

    for idx, event in enumerate(day.get("events") or []):
        event_type = (event.get("type") or event.get("event") or "").lower()
        dist_km = parse_float(event.get("distance"))
        dist_mi = dist_km * 0.621371 if dist_km is not None else None
        event_lat = parse_float(event.get("latitude"))
        event_lon = parse_float(event.get("longitude"))
        if dist_mi is None and lat is not None and lon is not None and event_lat and event_lon:
            dist_mi = haversine_mi(lat, lon, event_lat, event_lon)

        if "hail" in event_type:
            size = parse_float(event.get("size")) or parse_float(event.get("magnitude"))
            if size is not None:
                candidates.append(
                    WeatherCandidate(
                        id=f"vc:event:hail:{idx}",
                        metric="hail_size",
                        value=round(size, 2),
                        unit="in",
                        source="visual_crossing",
                        label=_event_label("Hail report", dist_mi),
                        tier=2,
                        distance_mi=round(dist_mi, 1) if dist_mi is not None else None,
                    )
                )
        elif "wind" in event_type:
            wind_val = parse_float(event.get("windSpeed")) or parse_float(event.get("magnitude"))
            if wind_val is not None:
                candidates.append(
                    WeatherCandidate(
                        id=f"vc:event:wind:{idx}",
                        metric="wind_gust",
                        value=round(wind_val, 1),
                        unit="mph",
                        source="visual_crossing",
                        label=_event_label("Wind damage report", dist_mi),
                        tier=2,
                        distance_mi=round(dist_mi, 1) if dist_mi is not None else None,
                    )
                )

    return candidates


def _event_label(prefix: str, dist_mi: float | None) -> str:
    if dist_mi is not None:
        return f"{prefix} ({dist_mi:.0f} mi)"
    return prefix
