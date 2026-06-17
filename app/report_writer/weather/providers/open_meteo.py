"""Open-Meteo ERA5 reanalysis — gap-fill when observations are sparse."""

from __future__ import annotations

import logging

from app.config import OPEN_METEO_ATTRIBUTION, WEATHER_ENABLE_OPEN_METEO
from app.http_client import get_async_client
from app.report_writer.weather.types import GeoContext, WeatherCandidate
from app.report_writer.weather.utils import parse_float

logger = logging.getLogger(__name__)

_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


async def fetch_candidates(ctx: GeoContext) -> tuple[list[WeatherCandidate], list[str]]:
    if not WEATHER_ENABLE_OPEN_METEO:
        return [], []
    if ctx.latitude is None or ctx.longitude is None:
        return [], []

    date_str = ctx.storm_date.isoformat()
    client = get_async_client()
    try:
        resp = await client.get(
            _ARCHIVE_URL,
            params={
                "latitude": ctx.latitude,
                "longitude": ctx.longitude,
                "start_date": date_str,
                "end_date": date_str,
                "daily": "wind_speed_10m_max,wind_gusts_10m_max,precipitation_sum",
                "wind_speed_unit": "mph",
                "wind_gust_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "UTC",
            },
            timeout=15.0,
        )
        if resp.status_code >= 400:
            return [], []
        data = resp.json()
    except Exception as e:
        logger.warning("Open-Meteo request failed: %s", e)
        return [], []

    daily = data.get("daily") or {}
    speeds = daily.get("wind_speed_10m_max") or []
    gusts = daily.get("wind_gusts_10m_max") or []
    precips = daily.get("precipitation_sum") or []

    candidates: list[WeatherCandidate] = []
    if speeds and speeds[0] is not None:
        val = parse_float(speeds[0])
        if val is not None:
            candidates.append(
                WeatherCandidate(
                    id="open_meteo:wind_speed",
                    metric="wind_speed",
                    value=round(val, 1),
                    unit="mph",
                    source="open_meteo_era5",
                    label="Open-Meteo ERA5 reanalysis",
                    tier=4,
                )
            )
    if gusts and gusts[0] is not None:
        val = parse_float(gusts[0])
        if val is not None:
            candidates.append(
                WeatherCandidate(
                    id="open_meteo:wind_gust",
                    metric="wind_gust",
                    value=round(val, 1),
                    unit="mph",
                    source="open_meteo_era5",
                    label="Open-Meteo ERA5 reanalysis",
                    tier=4,
                )
            )
    if precips and precips[0] is not None:
        val = parse_float(precips[0])
        if val is not None and val > 0:
            candidates.append(
                WeatherCandidate(
                    id="open_meteo:precip",
                    metric="precip",
                    value=round(val, 2),
                    unit="in",
                    source="open_meteo_era5",
                    label="Open-Meteo ERA5 reanalysis",
                    tier=4,
                )
            )

    attribution = [OPEN_METEO_ATTRIBUTION] if candidates else []
    return candidates, attribution
