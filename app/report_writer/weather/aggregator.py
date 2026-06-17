"""Aggregate weather candidates from all providers and apply recommendation logic."""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from app.config import WEATHER_MAX_DISTANCE_MI
from app.report_writer.weather.providers import iem_asos, open_meteo, spc_reports, visual_crossing
from app.report_writer.weather.types import WeatherCandidate, WeatherMetric, WeatherOptions
from app.report_writer.weather.utils import weather_fetch_key

logger = logging.getLogger(__name__)

_METRICS: tuple[WeatherMetric, ...] = ("wind_speed", "wind_gust", "hail_size", "precip")
_PROVIDER_TIMEOUT = 20.0


async def _safe_fetch(coro, label: str) -> list[WeatherCandidate]:
    try:
        result = await asyncio.wait_for(coro, timeout=_PROVIDER_TIMEOUT)
        return result if isinstance(result, list) else []
    except asyncio.TimeoutError:
        logger.warning("Weather provider %s timed out", label)
        return []
    except Exception as e:
        logger.warning("Weather provider %s failed: %s", label, e)
        return []


async def _safe_open_meteo(coro) -> tuple[list[WeatherCandidate], list[str]]:
    try:
        result = await asyncio.wait_for(coro, timeout=_PROVIDER_TIMEOUT)
        if isinstance(result, tuple) and len(result) == 2:
            cands, attr = result
            return cands or [], attr or []
        return [], []
    except Exception as e:
        logger.warning("Open-Meteo provider failed: %s", e)
        return [], []


def apply_recommendations(
    candidates: list[WeatherCandidate],
    max_distance_mi: float = WEATHER_MAX_DISTANCE_MI,
) -> dict[str, str]:
    """Mark recommended candidates and return metric -> candidate id map."""
    selected: dict[str, str] = {}

    for metric in _METRICS:
        pool = [c for c in candidates if c.metric == metric]
        if not pool:
            continue

        within = [
            c
            for c in pool
            if c.distance_mi is None or c.distance_mi <= max_distance_mi
        ]
        if not within:
            within = pool

        # Best tier (lowest number), then highest value, then closest distance.
        best = max(
            within,
            key=lambda c: (
                5 - c.tier,
                c.value,
                -(c.distance_mi if c.distance_mi is not None else 9999),
            ),
        )
        best.recommended = True
        best.recommendation_reason = _reason_for(best)
        selected[metric] = best.id

    return selected


def _reason_for(c: WeatherCandidate) -> str:
    parts = [f"Highest {c.metric.replace('_', ' ')}"]
    if c.station:
        parts.append(f"at {c.station}")
    if c.distance_mi is not None:
        parts.append(f"({c.distance_mi:.0f} mi)")
    parts.append(f"via {c.source.replace('_', ' ')}")
    return " ".join(parts)


def _value_for_metric(
    candidates: list[WeatherCandidate],
    selected: dict[str, str],
    metric: WeatherMetric,
) -> float | None:
    cid = selected.get(metric)
    if not cid:
        return None
    for c in candidates:
        if c.id == cid:
            return c.value
    return None


def _stations_from_candidates(candidates: list[WeatherCandidate]) -> list[str]:
    stations: list[str] = []
    for c in candidates:
        if c.station and c.station not in stations:
            stations.append(c.station)
    return stations


async def fetch_weather_options(address: str, storm_date: date) -> WeatherOptions:
    ctx = await visual_crossing.fetch_geocontext(address, storm_date)

    vc_task = _safe_fetch(visual_crossing.fetch_candidates(ctx), "visual_crossing")
    iem_task = _safe_fetch(iem_asos.fetch_candidates(ctx), "iem_asos")
    spc_task = _safe_fetch(
        spc_reports.fetch_candidates(ctx, max_distance_mi=WEATHER_MAX_DISTANCE_MI),
        "spc_reports",
    )
    om_task = _safe_open_meteo(open_meteo.fetch_candidates(ctx))

    vc_cands, iem_cands, spc_cands, (om_cands, attribution) = await asyncio.gather(
        vc_task, iem_task, spc_task, om_task
    )

    candidates = vc_cands + iem_cands + spc_cands + om_cands
    selected = apply_recommendations(candidates)

    date_iso = storm_date.isoformat()
    date_display = storm_date.strftime("%B %d, %Y")

    return WeatherOptions(
        wind_speed_mph=_value_for_metric(candidates, selected, "wind_speed"),
        wind_gust_mph=_value_for_metric(candidates, selected, "wind_gust"),
        hail_size_in=_value_for_metric(candidates, selected, "hail_size"),
        precip_in=_value_for_metric(candidates, selected, "precip"),
        stations=_stations_from_candidates(candidates) or ctx.stations,
        resolved_address=ctx.resolved_address,
        latitude=ctx.latitude,
        longitude=ctx.longitude,
        date_iso=date_iso,
        date_display=date_display,
        fetch_key=weather_fetch_key(address, date_iso),
        candidates=candidates,
        selected=selected,
        attribution=attribution,
    )


def weather_metadata_from_options(options: WeatherOptions, address: str) -> dict[str, str]:
    """Build property_metadata patch from weather options."""
    from datetime import datetime, timezone

    meta: dict[str, str] = {
        "weather_source": options.source,
        "weather_date_iso": options.date_iso,
        "weather_fetched_at": datetime.now(timezone.utc).isoformat(),
        "weather_fetch_key": options.fetch_key or weather_fetch_key(address, options.date_iso),
    }
    if options.wind_speed_mph is not None:
        meta["wind_speed_mph"] = str(round(options.wind_speed_mph))
    if options.wind_gust_mph is not None:
        meta["wind_gust_mph"] = str(round(options.wind_gust_mph))
    if options.hail_size_in is not None:
        meta["hail_size_in"] = str(round(options.hail_size_in, 2))
    if options.stations:
        meta["weather_stations"] = ", ".join(options.stations)
    if options.resolved_address:
        meta["weather_resolved_address"] = options.resolved_address
    for metric, cid in options.selected.items():
        meta[f"weather_{metric}_source"] = cid
    return meta
