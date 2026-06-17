"""IEM ASOS — observed wind at nearby airport stations."""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, timedelta

from app.http_client import get_async_client
from app.report_writer.weather.types import GeoContext, WeatherCandidate
from app.report_writer.weather.utils import haversine_mi, knots_to_mph, parse_float

logger = logging.getLogger(__name__)

_IEM_ASOS_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
_NWS_POINTS_URL = "https://api.weather.gov/points/{lat},{lon}"
_MAX_STATIONS = 6


async def _nws_station_ids(lat: float, lon: float) -> list[str]:
    client = get_async_client()
    try:
        resp = await client.get(
            _NWS_POINTS_URL.format(lat=round(lat, 4), lon=round(lon, 4)),
            headers={"User-Agent": "verbiage-report-writer/1.0"},
            timeout=10.0,
        )
        if resp.status_code >= 400:
            return []
        data = resp.json()
        stations_url = (data.get("properties") or {}).get("observationStations")
        if not stations_url:
            return []
        stations_resp = await client.get(
            stations_url,
            headers={"User-Agent": "verbiage-report-writer/1.0"},
            timeout=10.0,
        )
        if stations_resp.status_code >= 400:
            return []
        features = stations_resp.json().get("features") or []
        ids: list[str] = []
        for feat in features[:_MAX_STATIONS]:
            station_id = (feat.get("properties") or {}).get("stationIdentifier")
            if station_id:
                ids.append(str(station_id))
        return ids
    except Exception as e:
        logger.warning("NWS station lookup failed: %s", e)
        return []


async def _fetch_station_obs(
    station_id: str,
    storm_date: date,
    prop_lat: float | None,
    prop_lon: float | None,
) -> tuple[float | None, float | None, float | None, float | None]:
    """Return max sustained mph, max gust mph, station lat, station lon."""
    client = get_async_client()
    end = storm_date + timedelta(days=1)
    params = {
        "station": station_id,
        "data": "sknt,gust,peak_wind_gust,lat,lon",
        "year1": storm_date.year,
        "month1": storm_date.month,
        "day1": storm_date.day,
        "year2": end.year,
        "month2": end.month,
        "day2": end.day,
        "tz": "Etc/UTC",
        "format": "onlycomma",
        "latlon": "yes",
    }
    try:
        resp = await client.get(_IEM_ASOS_URL, params=params, timeout=15.0)
        if resp.status_code >= 400:
            return None, None, None, None
        text = resp.text.strip()
        if not text or text.startswith("ERROR"):
            return None, None, None, None
    except Exception as e:
        logger.warning("IEM ASOS request failed for %s: %s", station_id, e)
        return None, None, None, None

    reader = csv.DictReader(io.StringIO(text))
    max_sknt: float | None = None
    max_gust: float | None = None
    st_lat: float | None = None
    st_lon: float | None = None

    for row in reader:
        if st_lat is None:
            st_lat = parse_float(row.get("lat"))
            st_lon = parse_float(row.get("lon"))
        sknt = parse_float(row.get("sknt"))
        gust = parse_float(row.get("gust")) or parse_float(row.get("peak_wind_gust"))
        if sknt is not None:
            mph = knots_to_mph(sknt)
            max_sknt = mph if max_sknt is None else max(max_sknt, mph)
        if gust is not None:
            mph = knots_to_mph(gust)
            max_gust = mph if max_gust is None else max(max_gust, mph)

    if prop_lat is not None and prop_lon is not None and st_lat is not None and st_lon is not None:
        pass  # distance computed by caller

    return max_sknt, max_gust, st_lat, st_lon


async def fetch_candidates(ctx: GeoContext) -> list[WeatherCandidate]:
    if ctx.latitude is None or ctx.longitude is None:
        return []

    station_ids = list(dict.fromkeys(ctx.stations))
    nws_ids = await _nws_station_ids(ctx.latitude, ctx.longitude)
    for sid in nws_ids:
        if sid not in station_ids:
            station_ids.append(sid)
    station_ids = station_ids[:_MAX_STATIONS]

    candidates: list[WeatherCandidate] = []
    for station_id in station_ids:
        max_speed, max_gust, st_lat, st_lon = await _fetch_station_obs(
            station_id,
            ctx.storm_date,
            ctx.latitude,
            ctx.longitude,
        )
        dist_mi: float | None = None
        if st_lat is not None and st_lon is not None:
            dist_mi = haversine_mi(ctx.latitude, ctx.longitude, st_lat, st_lon)
        elif ctx.latitude is not None and ctx.longitude is not None:
            dist_mi = None

        dist_label = f"{dist_mi:.0f} mi" if dist_mi is not None else "nearby"
        if max_speed is not None:
            candidates.append(
                WeatherCandidate(
                    id=f"iem:{station_id}:wind_speed",
                    metric="wind_speed",
                    value=round(max_speed, 1),
                    unit="mph",
                    source="iem_asos",
                    label=f"{station_id} ASOS ({dist_label})",
                    tier=1,
                    station=station_id,
                    distance_mi=round(dist_mi, 1) if dist_mi is not None else None,
                )
            )
        if max_gust is not None:
            candidates.append(
                WeatherCandidate(
                    id=f"iem:{station_id}:wind_gust",
                    metric="wind_gust",
                    value=round(max_gust, 1),
                    unit="mph",
                    source="iem_asos",
                    label=f"{station_id} ASOS ({dist_label})",
                    tier=1,
                    station=station_id,
                    distance_mi=round(dist_mi, 1) if dist_mi is not None else None,
                )
            )

    return candidates
