"""USGS/USDA NAIP historical aerial imagery for claim reports (opt-in export)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.http_client import get_async_client
from app.report_writer.image_utils import compress_image_bytes
from app.report_writer.property_maps import geocode_address
from app.report_writer.storage import delete_claim_image_file, write_claim_image
from app.report_writer.weather.utils import normalize_address_for_key, parse_storm_date

logger = logging.getLogger(__name__)

_GEOPLATFORM_NAIP_FOLDER = "https://imagery.geoplatform.gov/iipp/rest/services/NAIP"
_NAIP_YEAR_SERVICE = (
    "https://imagery.geoplatform.gov/iipp/rest/services/NAIP/NAIP{year}_CONUS/ImageServer"
)
_ATTRIBUTION = "NAIP / USGS The National Map / USDA"
_MAX_AERIALS = 5
_HALF_SPAN_DEG = 0.0015  # ~165 m — property-scale framing
_EXPORT_SIZE = "640,480"
_MIN_JPEG_BYTES = 12_000  # blank / no-coverage exports are typically tiny
_YEAR_NAME_RE = re.compile(r"NAIP(\d{4})_CONUS$")

# Fallback catalog if folder listing fails (GeoPlatform CONUS NAIP years).
_FALLBACK_YEARS = list(range(2004, 2024))


@dataclass
class HistoricalAerialItem:
    year: int
    path: str | None = None
    include: bool = False
    preview: str = ""
    image_url: str | None = None


@dataclass
class HistoricalAerialsResult:
    resolved_address: str
    latitude: float
    longitude: float
    fetch_key: str
    dol_year: int
    aerials: list[HistoricalAerialItem] = field(default_factory=list)
    comment: str = ""
    attribution: str = _ATTRIBUTION


def historical_aerials_fetch_key(address: str, dol_year: int) -> str:
    return f"{normalize_address_for_key(address)}|{dol_year}"


def historical_aerial_storage_path(user_id: str, claim_id: str, year: int) -> str:
    return f"{user_id}/{claim_id}/historical_aerial_{year}.jpg"


def select_years(available: list[int], max_count: int = _MAX_AERIALS) -> list[int]:
    """Pick up to max_count years, always including earliest and latest when capping."""
    years = sorted({int(y) for y in available})
    if not years:
        return []
    if max_count <= 0:
        return []
    if len(years) <= max_count:
        return years
    if max_count == 1:
        return [years[-1]]
    indices: list[int] = []
    for i in range(max_count):
        idx = round(i * (len(years) - 1) / (max_count - 1))
        if idx not in indices:
            indices.append(idx)
    # If rounding collapsed slots, fill from unused indices.
    unused = [i for i in range(len(years)) if i not in indices]
    while len(indices) < max_count and unused:
        indices.append(unused.pop(0))
    indices.sort()
    return [years[i] for i in indices]


def parse_historical_aerials_list(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, str) and raw.strip():
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            year = int(item.get("year"))
        except (TypeError, ValueError):
            continue
        include = item.get("include")
        if isinstance(include, str):
            include = include.strip().lower() in ("1", "true", "yes")
        else:
            include = bool(include)
        path = (item.get("path") or "").strip() or None
        out.append({"year": year, "path": path, "include": include})
    return out


def _preview_data_url(data: bytes) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _bbox_for_point(latitude: float, longitude: float) -> str:
    return (
        f"{longitude - _HALF_SPAN_DEG},{latitude - _HALF_SPAN_DEG},"
        f"{longitude + _HALF_SPAN_DEG},{latitude + _HALF_SPAN_DEG}"
    )


async def list_naip_catalog_years() -> list[int]:
    client = get_async_client()
    try:
        resp = await client.get(f"{_GEOPLATFORM_NAIP_FOLDER}?f=json", timeout=20.0)
    except Exception as e:
        logger.warning("NAIP catalog listing failed: %s", e)
        return list(_FALLBACK_YEARS)

    if resp.status_code >= 400:
        logger.warning("NAIP catalog listing HTTP %s", resp.status_code)
        return list(_FALLBACK_YEARS)

    try:
        data = resp.json()
    except Exception:
        return list(_FALLBACK_YEARS)

    years: list[int] = []
    for svc in data.get("services") or []:
        name = svc.get("name") or ""
        match = _YEAR_NAME_RE.search(name)
        if match:
            years.append(int(match.group(1)))
    return sorted(set(years)) if years else list(_FALLBACK_YEARS)


async def export_naip_year_image(latitude: float, longitude: float, year: int) -> bytes | None:
    url = f"{_NAIP_YEAR_SERVICE.format(year=year)}/exportImage"
    params = {
        "bbox": _bbox_for_point(latitude, longitude),
        "bboxSR": "4326",
        "size": _EXPORT_SIZE,
        "imageSR": "4326",
        "format": "jpg",
        "f": "image",
    }
    client = get_async_client()
    try:
        resp = await client.get(url, params=params, timeout=30.0)
    except Exception as e:
        logger.warning("NAIP export failed for %s: %s", year, e)
        return None

    if resp.status_code >= 400:
        return None
    content_type = (resp.headers.get("content-type") or "").lower()
    if "image" not in content_type:
        return None
    if len(resp.content) < _MIN_JPEG_BYTES:
        return None

    compressed, _ext = compress_image_bytes(resp.content, max_dimension=1280, quality=80)
    return compressed


async def _fetch_years_with_backfill(
    latitude: float,
    longitude: float,
    candidate_years: list[int],
    selected: list[int],
) -> dict[int, bytes]:
    """Fetch selected years; replace blanks from remaining candidates (nearest first)."""
    remaining = [y for y in candidate_years if y not in selected]
    images: dict[int, bytes] = {}

    async def _one(year: int) -> tuple[int, bytes | None]:
        data = await export_naip_year_image(latitude, longitude, year)
        return year, data

    results = await asyncio.gather(*[_one(y) for y in selected])
    failed: list[int] = []
    for year, data in results:
        if data:
            images[year] = data
        else:
            failed.append(year)

    # Backfill gaps from unused years closest to each failed slot.
    for failed_year in failed:
        if len(images) >= _MAX_AERIALS:
            break
        remaining.sort(key=lambda y: abs(y - failed_year))
        for alt in list(remaining):
            if alt in images:
                remaining.remove(alt)
                continue
            data = await export_naip_year_image(latitude, longitude, alt)
            remaining.remove(alt)
            if data:
                images[alt] = data
                break

    return images


def _coords_from_meta(meta: dict | None) -> tuple[float, float] | None:
    if not meta:
        return None
    try:
        lat = float(meta.get("property_latitude"))
        lon = float(meta.get("property_longitude"))
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def persist_historical_aerials(
    user_id: str,
    claim_id: str,
    year_images: dict[int, bytes],
    *,
    previous_meta: dict | None = None,
) -> dict[int, str]:
    prev_items = parse_historical_aerials_list((previous_meta or {}).get("historical_aerials"))
    keep_years = set(year_images)
    for item in prev_items:
        path = item.get("path")
        if path and item["year"] not in keep_years:
            try:
                delete_claim_image_file(path)
            except OSError:
                pass

    paths: dict[int, str] = {}
    for year, data in year_images.items():
        path = historical_aerial_storage_path(user_id, claim_id, year)
        write_claim_image(path, data)
        paths[year] = path
    return paths


def merge_historical_aerials_metadata(
    result: HistoricalAerialsResult,
    *,
    previous_meta: dict | None = None,
) -> dict[str, Any]:
    prev = previous_meta or {}
    prev_by_year = {
        item["year"]: item for item in parse_historical_aerials_list(prev.get("historical_aerials"))
    }
    comment = (result.comment or prev.get("historical_aerials_comment") or "")
    if isinstance(comment, str):
        comment = comment.strip()
    else:
        comment = ""

    aerials: list[dict[str, Any]] = []
    for item in result.aerials:
        prev_item = prev_by_year.get(item.year) or {}
        include = bool(prev_item.get("include")) if prev_item else False
        aerials.append(
            {
                "year": item.year,
                "path": item.path,
                "include": include,
            }
        )

    return {
        "historical_aerials_fetch_key": result.fetch_key,
        "historical_aerials_fetched_at": datetime.now(timezone.utc).isoformat(),
        "historical_aerials_comment": comment,
        "historical_aerials": aerials,
        "historical_aerials_resolved_address": result.resolved_address,
        "historical_aerials_latitude": str(result.latitude),
        "historical_aerials_longitude": str(result.longitude),
        "historical_aerials_dol_year": str(result.dol_year),
    }


def clear_historical_aerials_metadata(meta: dict) -> dict:
    next_meta = dict(meta)
    for key in (
        "historical_aerials_fetch_key",
        "historical_aerials_fetched_at",
        "historical_aerials_comment",
        "historical_aerials",
        "historical_aerials_resolved_address",
        "historical_aerials_latitude",
        "historical_aerials_longitude",
        "historical_aerials_dol_year",
    ):
        next_meta.pop(key, None)
    return next_meta


async def fetch_historical_aerials(
    address: str,
    storm_date: str,
    *,
    user_id: str | None = None,
    claim_id: str | None = None,
    previous_meta: dict | None = None,
) -> HistoricalAerialsResult:
    try:
        dol = parse_storm_date(storm_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    dol_year = dol.year
    coords = _coords_from_meta(previous_meta)
    resolved_address = (previous_meta or {}).get("property_map_resolved_address") or address.strip()
    if coords:
        latitude, longitude = coords
    else:
        geocoded = await geocode_address(address)
        latitude = geocoded.latitude
        longitude = geocoded.longitude
        resolved_address = geocoded.resolved_address

    catalog = await list_naip_catalog_years()
    candidate_years = [y for y in catalog if y >= dol_year]
    if not candidate_years:
        return HistoricalAerialsResult(
            resolved_address=resolved_address,
            latitude=latitude,
            longitude=longitude,
            fetch_key=historical_aerials_fetch_key(address, dol_year),
            dol_year=dol_year,
            comment=str((previous_meta or {}).get("historical_aerials_comment") or ""),
        )

    selected = select_years(candidate_years, _MAX_AERIALS)
    year_images = await _fetch_years_with_backfill(
        latitude, longitude, candidate_years, selected
    )
    ordered_years = sorted(year_images)

    paths: dict[int, str] = {}
    if user_id and claim_id and year_images:
        paths = persist_historical_aerials(
            user_id,
            claim_id,
            year_images,
            previous_meta=previous_meta,
        )

    prev_by_year = {
        item["year"]: item
        for item in parse_historical_aerials_list((previous_meta or {}).get("historical_aerials"))
    }
    aerials: list[HistoricalAerialItem] = []
    for year in ordered_years:
        data = year_images[year]
        prev_item = prev_by_year.get(year) or {}
        aerials.append(
            HistoricalAerialItem(
                year=year,
                path=paths.get(year),
                include=bool(prev_item.get("include")),
                preview=_preview_data_url(data),
            )
        )

    return HistoricalAerialsResult(
        resolved_address=resolved_address,
        latitude=latitude,
        longitude=longitude,
        fetch_key=historical_aerials_fetch_key(address, dol_year),
        dol_year=dol_year,
        aerials=aerials,
        comment=str((previous_meta or {}).get("historical_aerials_comment") or ""),
    )


def read_historical_aerial_bytes(meta: dict, year: int) -> bytes | None:
    for item in parse_historical_aerials_list(meta.get("historical_aerials")):
        if item["year"] != year:
            continue
        path = (item.get("path") or "").strip()
        if not path:
            return None
        try:
            from app.report_writer.storage import read_claim_image_bytes

            return read_claim_image_bytes(path)
        except OSError:
            return None
    return None


def included_historical_aerials(meta: dict) -> list[dict[str, Any]]:
    return [
        item
        for item in parse_historical_aerials_list(meta.get("historical_aerials"))
        if item.get("include") and item.get("path")
    ]
