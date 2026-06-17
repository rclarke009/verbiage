"""SPC daily storm reports — spotter wind and hail near the property."""

from __future__ import annotations

import csv
import io
import logging
import re

from app.http_client import get_async_client
from app.report_writer.weather.types import GeoContext, WeatherCandidate
from app.report_writer.weather.utils import haversine_mi, parse_float

logger = logging.getLogger(__name__)

_SPC_BASE = "https://www.spc.noaa.gov/climo/reports"


async def fetch_candidates(ctx: GeoContext, max_distance_mi: float = 50.0) -> list[WeatherCandidate]:
    if ctx.latitude is None or ctx.longitude is None:
        return []

    date_str = ctx.storm_date.strftime("%y%m%d")
    url = f"{_SPC_BASE}/{date_str}_rpts_filtered.csv"

    client = get_async_client()
    try:
        resp = await client.get(url, timeout=15.0)
        if resp.status_code >= 400:
            return []
        text = resp.text.strip()
        if not text:
            return []
    except Exception as e:
        logger.warning("SPC reports request failed: %s", e)
        return []

    candidates: list[WeatherCandidate] = []
    reader = csv.DictReader(io.StringIO(text))

    for idx, row in enumerate(reader):
        row_lat = parse_float(row.get("Lat") or row.get("lat"))
        row_lon = parse_float(row.get("Lon") or row.get("lon"))
        if row_lat is None or row_lon is None:
            continue

        dist_mi = haversine_mi(ctx.latitude, ctx.longitude, row_lat, row_lon)
        if dist_mi > max_distance_mi:
            continue

        report_type = (row.get("Type") or row.get("type") or "").strip().lower()
        location = (row.get("Location") or row.get("location") or "report").strip()
        dist_label = f"{dist_mi:.0f} mi — {location}"

        if report_type == "hail":
            size_raw = row.get("Size") or row.get("size") or ""
            size_in = _parse_hail_size(size_raw)
            if size_in is not None:
                candidates.append(
                    WeatherCandidate(
                        id=f"spc:hail:{idx}",
                        metric="hail_size",
                        value=round(size_in, 2),
                        unit="in",
                        source="spc_reports",
                        label=f"SPC hail ({dist_label})",
                        tier=2,
                        distance_mi=round(dist_mi, 1),
                    )
                )
        elif report_type == "wind":
            speed_raw = row.get("Speed") or row.get("speed") or ""
            speed = parse_float(speed_raw)
            if speed is not None:
                candidates.append(
                    WeatherCandidate(
                        id=f"spc:wind:{idx}",
                        metric="wind_gust",
                        value=round(speed, 1),
                        unit="mph",
                        source="spc_reports",
                        label=f"SPC wind ({dist_label})",
                        tier=2,
                        distance_mi=round(dist_mi, 1),
                    )
                )

    return candidates


def _parse_hail_size(raw: str) -> float | None:
    text = (raw or "").strip()
    if not text:
        return None
    val = parse_float(text)
    if val is not None:
        return val
    match = re.search(r"([\d.]+)", text)
    if match:
        return float(match.group(1))
    return None
