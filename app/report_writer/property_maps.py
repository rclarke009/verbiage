"""Google Maps geocoding and static map images for property location reports."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import HTTPException

from app.config import GOOGLE_MAPS_API_KEY
from app.http_client import get_async_client
from app.report_writer.image_utils import compress_image_bytes
from app.report_writer.storage import delete_claim_image_file, write_claim_image
from app.report_writer.weather.utils import normalize_address_for_key

logger = logging.getLogger(__name__)

_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
_STATIC_MAP_URL = "https://maps.googleapis.com/maps/api/staticmap"
_MAP_VARIANTS = ("satellite", "roadmap")
_MAP_ATTRIBUTION = "Map data © Google"
_PROPERTY_DETAIL_ZOOM = 20
# NW panhandle to SE Keys — frames both Florida coasts for state context map.
_FL_CONTEXT_VISIBLE = "31.0,-87.6|24.4,-79.8"


@dataclass
class GeocodeResult:
    latitude: float
    longitude: float
    resolved_address: str


@dataclass
class PropertyMapImages:
    satellite: bytes
    roadmap: bytes


@dataclass
class PropertyMapResult:
    resolved_address: str
    latitude: float
    longitude: float
    fetch_key: str
    satellite_path: str | None = None
    roadmap_path: str | None = None
    satellite_preview: str = ""
    roadmap_preview: str = ""


def property_map_fetch_key(address: str) -> str:
    return normalize_address_for_key(address)


def property_map_storage_path(user_id: str, claim_id: str, variant: str) -> str:
    return f"{user_id}/{claim_id}/property_map_{variant}.jpg"


def property_map_metadata_from_result(result: PropertyMapResult) -> dict[str, str]:
    meta: dict[str, str] = {
        "property_map_fetch_key": result.fetch_key,
        "property_map_resolved_address": result.resolved_address,
        "property_latitude": str(result.latitude),
        "property_longitude": str(result.longitude),
        "property_map_fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    if result.satellite_path:
        meta["property_map_satellite_path"] = result.satellite_path
    if result.roadmap_path:
        meta["property_map_roadmap_path"] = result.roadmap_path
    return meta


def clear_property_map_metadata(meta: dict) -> dict:
    next_meta = dict(meta)
    for key in (
        "property_map_fetch_key",
        "property_map_resolved_address",
        "property_latitude",
        "property_longitude",
        "property_map_satellite_path",
        "property_map_roadmap_path",
        "property_map_fetched_at",
    ):
        next_meta.pop(key, None)
    return next_meta


def _preview_data_url(data: bytes) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


async def geocode_address(address: str) -> GeocodeResult:
    if not GOOGLE_MAPS_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Google Maps API key is not configured (GOOGLE_MAPS_API_KEY)",
        )

    addr = address.strip()
    if len(addr) < 3:
        raise HTTPException(status_code=400, detail="Address is too short")

    client = get_async_client()
    try:
        resp = await client.get(
            _GEOCODE_URL,
            params={"address": addr, "key": GOOGLE_MAPS_API_KEY},
            timeout=15.0,
        )
    except Exception as e:
        logger.warning("Google geocode request failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Geocoding request failed: {e}") from e

    if resp.status_code >= 400:
        detail = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
        raise HTTPException(status_code=502, detail=f"Geocoding API error: {detail}")

    data = resp.json()
    status = (data.get("status") or "").upper()
    if status == "ZERO_RESULTS":
        raise HTTPException(status_code=404, detail="Address could not be geocoded")
    if status not in ("OK",):
        message = data.get("error_message") or status or "unknown error"
        raise HTTPException(status_code=502, detail=f"Geocoding API error: {message}")

    results = data.get("results") or []
    if not results:
        raise HTTPException(status_code=404, detail="Address could not be geocoded")

    top = results[0]
    location = (top.get("geometry") or {}).get("location") or {}
    lat = location.get("lat")
    lon = location.get("lng")
    if lat is None or lon is None:
        raise HTTPException(status_code=502, detail="Geocoding response missing coordinates")

    return GeocodeResult(
        latitude=float(lat),
        longitude=float(lon),
        resolved_address=(top.get("formatted_address") or addr).strip(),
    )


async def fetch_static_map(
    latitude: float,
    longitude: float,
    *,
    maptype: str,
    zoom: int = _PROPERTY_DETAIL_ZOOM,
    visible: str | None = None,
    size: str = "640x480",
) -> bytes:
    if maptype not in _MAP_VARIANTS:
        raise ValueError(f"Unsupported map type: {maptype}")

    if not GOOGLE_MAPS_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Google Maps API key is not configured (GOOGLE_MAPS_API_KEY)",
        )

    marker = quote(f"color:red|{latitude},{longitude}", safe="|,")
    params: dict[str, str] = {
        "size": size,
        "scale": "2",
        "maptype": maptype,
        "markers": marker,
        "key": GOOGLE_MAPS_API_KEY,
    }
    if visible:
        params["visible"] = visible
    else:
        params["center"] = f"{latitude},{longitude}"
        params["zoom"] = str(zoom)

    client = get_async_client()
    try:
        resp = await client.get(_STATIC_MAP_URL, params=params, timeout=20.0)
    except Exception as e:
        logger.warning("Google static map request failed (%s): %s", maptype, e)
        raise HTTPException(status_code=502, detail=f"Static map request failed: {e}") from e

    if resp.status_code >= 400:
        detail = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
        raise HTTPException(status_code=502, detail=f"Static map API error: {detail}")

    content_type = (resp.headers.get("content-type") or "").lower()
    if "image" not in content_type:
        detail = resp.text[:200] if resp.text else "non-image response"
        raise HTTPException(status_code=502, detail=f"Static map API error: {detail}")

    compressed, _ext = compress_image_bytes(resp.content, max_dimension=1280, quality=80)
    return compressed


async def fetch_florida_context_map(latitude: float, longitude: float) -> bytes:
    return await fetch_static_map(
        latitude,
        longitude,
        maptype="roadmap",
        visible=_FL_CONTEXT_VISIBLE,
    )


async def fetch_property_map_images(latitude: float, longitude: float) -> PropertyMapImages:
    satellite, roadmap = await asyncio_gather_maps(latitude, longitude)
    return PropertyMapImages(satellite=satellite, roadmap=roadmap)


async def asyncio_gather_maps(latitude: float, longitude: float) -> tuple[bytes, bytes]:
    import asyncio

    satellite_task = fetch_static_map(latitude, longitude, maptype="satellite")
    roadmap_task = fetch_florida_context_map(latitude, longitude)
    satellite, roadmap = await asyncio.gather(satellite_task, roadmap_task)
    return satellite, roadmap


def persist_property_maps(
    user_id: str,
    claim_id: str,
    images: PropertyMapImages,
    *,
    previous_meta: dict | None = None,
) -> tuple[str, str]:
    prev = previous_meta or {}
    for variant in _MAP_VARIANTS:
        old_path = prev.get(f"property_map_{variant}_path")
        if old_path:
            try:
                delete_claim_image_file(old_path)
            except OSError:
                pass

    satellite_path = property_map_storage_path(user_id, claim_id, "satellite")
    roadmap_path = property_map_storage_path(user_id, claim_id, "roadmap")
    write_claim_image(satellite_path, images.satellite)
    write_claim_image(roadmap_path, images.roadmap)
    return satellite_path, roadmap_path


async def fetch_property_maps(
    address: str,
    *,
    user_id: str | None = None,
    claim_id: str | None = None,
    previous_meta: dict | None = None,
) -> PropertyMapResult:
    geocoded = await geocode_address(address)
    images = await fetch_property_map_images(geocoded.latitude, geocoded.longitude)
    fetch_key = property_map_fetch_key(address)

    satellite_path: str | None = None
    roadmap_path: str | None = None
    if user_id and claim_id:
        satellite_path, roadmap_path = persist_property_maps(
            user_id,
            claim_id,
            images,
            previous_meta=previous_meta,
        )

    return PropertyMapResult(
        resolved_address=geocoded.resolved_address,
        latitude=geocoded.latitude,
        longitude=geocoded.longitude,
        fetch_key=fetch_key,
        satellite_path=satellite_path,
        roadmap_path=roadmap_path,
        satellite_preview=_preview_data_url(images.satellite),
        roadmap_preview=_preview_data_url(images.roadmap),
    )


def read_property_map_bytes(meta: dict, variant: str) -> bytes | None:
    path = (meta.get(f"property_map_{variant}_path") or "").strip()
    if not path:
        return None
    try:
        from app.report_writer.storage import read_claim_image_bytes

        return read_claim_image_bytes(path)
    except OSError:
        return None
