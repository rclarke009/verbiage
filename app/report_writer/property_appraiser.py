"""County property-appraiser parcel screenshots for claim reports."""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import HTTPException

from app.report_writer.image_utils import compress_image_bytes
from app.report_writer.property_maps import geocode_address
from app.report_writer.storage import delete_claim_image_file, write_claim_image
from app.report_writer.weather.utils import normalize_address_for_key

logger = logging.getLogger(__name__)

_ATTRIBUTION = "County property appraiser public records"
_SCRAPE_TIMEOUT_SEC = 30
_NAV_TIMEOUT_MS = 25_000
DESOTO_GIS_URL = "https://www.desotopa.com/gis/"

_PLAYWRIGHT_LOCK = asyncio.Lock()

_COUNTY_ALIASES = {
    "desoto": "desoto",
    "de soto": "desoto",
}


@dataclass
class ParcelFields:
    parcel_id: str = ""
    owner: str = ""
    site_address: str = ""
    use_code: str = ""
    acreage: str = ""
    legal: str = ""
    source_url: str = ""


@dataclass
class ParcelPage:
    screenshot: bytes
    fields: ParcelFields
    source_url: str = ""


@dataclass
class PropertyAppraiserResult:
    resolved_address: str
    latitude: float
    longitude: float
    county: str
    fetch_key: str
    path: str | None = None
    preview: str = ""
    source_url: str = ""
    attribution: str = _ATTRIBUTION
    fields: ParcelFields = field(default_factory=ParcelFields)
    unsupported: bool = False
    message: str = ""


def property_appraiser_fetch_key(address: str) -> str:
    return normalize_address_for_key(address)


def property_appraiser_storage_path(user_id: str, claim_id: str) -> str:
    return f"{user_id}/{claim_id}/property_appraiser.jpg"


def normalize_county_name(raw: str) -> str:
    name = re.sub(r"\s+county$", "", (raw or "").strip(), flags=re.I)
    name = re.sub(r"\s+", " ", name).strip().lower()
    return _COUNTY_ALIASES.get(name, name.replace(" ", ""))


def county_supported(county: str) -> bool:
    return normalize_county_name(county) in _ADAPTERS


def property_appraiser_metadata_from_result(result: PropertyAppraiserResult) -> dict[str, str]:
    meta: dict[str, str] = {
        "property_appraiser_fetch_key": result.fetch_key,
        "property_appraiser_resolved_address": result.resolved_address,
        "property_appraiser_county": result.county,
        "property_appraiser_fetched_at": datetime.now(timezone.utc).isoformat(),
        "property_latitude": str(result.latitude),
        "property_longitude": str(result.longitude),
    }
    if result.path:
        meta["property_appraiser_path"] = result.path
    if result.source_url:
        meta["property_appraiser_source_url"] = result.source_url
    fields = result.fields
    for key, value in (
        ("property_appraiser_parcel_id", fields.parcel_id),
        ("property_appraiser_owner", fields.owner),
        ("property_appraiser_site_address", fields.site_address),
        ("property_appraiser_use_code", fields.use_code),
        ("property_appraiser_acreage", fields.acreage),
        ("property_appraiser_legal", fields.legal),
    ):
        if value:
            meta[key] = value
    return meta


_META_KEYS = (
    "property_appraiser_fetch_key",
    "property_appraiser_resolved_address",
    "property_appraiser_county",
    "property_appraiser_fetched_at",
    "property_appraiser_path",
    "property_appraiser_source_url",
    "property_appraiser_parcel_id",
    "property_appraiser_owner",
    "property_appraiser_site_address",
    "property_appraiser_use_code",
    "property_appraiser_acreage",
    "property_appraiser_legal",
)


def clear_property_appraiser_metadata(meta: dict) -> dict:
    next_meta = dict(meta)
    for key in _META_KEYS:
        next_meta.pop(key, None)
    return next_meta


def _preview_data_url(data: bytes) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def parse_street_search(address: str) -> tuple[str, str]:
    line1 = (address or "").split(",")[0].strip()
    match = re.match(r"^(\d+)\s+(.+)$", line1)
    if not match:
        return "", line1
    return match.group(1), match.group(2)


def parse_appraiser_text(text: str, *, source_url: str = "") -> ParcelFields:
    def grab(*labels: str) -> str:
        for label in labels:
            pattern = rf"{re.escape(label)}\s*[:#]?\s*(.+)"
            match = re.search(pattern, text, flags=re.I)
            if match:
                value = match.group(1).strip()
                value = re.split(r"\s{2,}|\n", value)[0].strip()
                if value:
                    return value[:400]
        return ""

    legal = grab("Legal Description", "Legal")
    return ParcelFields(
        parcel_id=grab("Parcel ID", "ParcelId", "Parcel #"),
        owner=grab("Owner"),
        site_address=grab("Site Address", "Situs Address", "Location Address"),
        use_code=grab("Use Code", "DOR Code"),
        acreage=grab("Area", "Acres", "Acreage"),
        legal=legal,
        source_url=source_url,
    )


def persist_property_appraiser(
    user_id: str,
    claim_id: str,
    screenshot: bytes,
    *,
    previous_meta: dict | None = None,
) -> str:
    prev = previous_meta or {}
    old_path = (prev.get("property_appraiser_path") or "").strip()
    if old_path:
        try:
            delete_claim_image_file(old_path)
        except OSError:
            pass
    path = property_appraiser_storage_path(user_id, claim_id)
    write_claim_image(path, screenshot)
    return path


def read_property_appraiser_bytes(meta: dict) -> bytes | None:
    path = (meta.get("property_appraiser_path") or "").strip()
    if not path:
        return None
    try:
        from app.report_writer.storage import read_claim_image_bytes as _read

        return _read(path)
    except OSError:
        return None


def _result_from_cache(
    *,
    geocoded,
    county: str,
    fetch_key: str,
    previous_meta: dict,
    data: bytes,
) -> PropertyAppraiserResult:
    fields = ParcelFields(
        parcel_id=str(previous_meta.get("property_appraiser_parcel_id") or ""),
        owner=str(previous_meta.get("property_appraiser_owner") or ""),
        site_address=str(previous_meta.get("property_appraiser_site_address") or ""),
        use_code=str(previous_meta.get("property_appraiser_use_code") or ""),
        acreage=str(previous_meta.get("property_appraiser_acreage") or ""),
        legal=str(previous_meta.get("property_appraiser_legal") or ""),
        source_url=str(previous_meta.get("property_appraiser_source_url") or ""),
    )
    return PropertyAppraiserResult(
        resolved_address=geocoded.resolved_address,
        latitude=geocoded.latitude,
        longitude=geocoded.longitude,
        county=county,
        fetch_key=fetch_key,
        path=str(previous_meta.get("property_appraiser_path") or "") or None,
        preview=_preview_data_url(data),
        source_url=fields.source_url,
        fields=fields,
    )


async def scrape_parcel_page(county: str, address: str) -> ParcelPage:
    key = normalize_county_name(county)
    adapter = _ADAPTERS.get(key)
    if adapter is None:
        raise HTTPException(
            status_code=422,
            detail=f"Property appraiser lookup is not supported yet for {county} County.",
        )
    return await adapter(address)


async def _scrape_desoto(address: str) -> ParcelPage:
    try:
        from playwright.async_api import TimeoutError as PlaywrightTimeout
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail="Property appraiser browser is not available on this server",
        ) from e

    house_no, street = parse_street_search(address)
    search_query = street or address.split(",")[0].strip()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            page.set_default_timeout(_NAV_TIMEOUT_MS)
            await page.goto(DESOTO_GIS_URL, wait_until="domcontentloaded")

            street_tab = page.get_by_text("Street", exact=True)
            if await street_tab.count():
                await street_tab.first.click()

            search_box = page.locator(
                "input[type='text'], input[type='search'], input:not([type])"
            ).first
            await search_box.wait_for(state="visible")
            await search_box.fill(search_query)
            await search_box.press("Enter")

            try:
                await page.wait_for_timeout(1500)
                if house_no:
                    hit = page.get_by_text(house_no, exact=False)
                    if await hit.count():
                        await hit.first.click()
                else:
                    result_row = page.locator("table tr, .results a, a").nth(1)
                    if await result_row.count():
                        await result_row.click()
                await page.wait_for_timeout(1500)
            except PlaywrightTimeout:
                logger.info("MYDEBUG → DeSoto PA result click timed out; capturing current page")

            text = await page.inner_text("body")
            source_url = page.url
            png = await page.screenshot(full_page=True, type="png")
        finally:
            await browser.close()

    screenshot, _ext = compress_image_bytes(png, max_dimension=1600, quality=80)
    fields = parse_appraiser_text(text, source_url=source_url)
    fields.source_url = source_url
    return ParcelPage(screenshot=screenshot, fields=fields, source_url=source_url)


_ADAPTERS = {
    "desoto": _scrape_desoto,
}


async def fetch_property_appraiser(
    address: str,
    *,
    user_id: str | None = None,
    claim_id: str | None = None,
    previous_meta: dict | None = None,
    force: bool = False,
) -> PropertyAppraiserResult:
    geocoded = await geocode_address(address)
    county = (geocoded.county or "").strip()
    fetch_key = property_appraiser_fetch_key(address)
    prev = previous_meta or {}

    if not county:
        raise HTTPException(status_code=422, detail="Could not determine county for this address.")

    if not county_supported(county):
        raise HTTPException(
            status_code=422,
            detail=f"Property appraiser lookup is not supported yet for {county} County.",
        )

    if not force and user_id and claim_id:
        cached_key = (prev.get("property_appraiser_fetch_key") or "").strip()
        cached_path = (prev.get("property_appraiser_path") or "").strip()
        if cached_key == fetch_key and cached_path:
            data = read_property_appraiser_bytes(prev)
            if data:
                return _result_from_cache(
                    geocoded=geocoded,
                    county=county,
                    fetch_key=fetch_key,
                    previous_meta=prev,
                    data=data,
                )

    try:
        async with _PLAYWRIGHT_LOCK:
            page = await asyncio.wait_for(
                scrape_parcel_page(county, address),
                timeout=_SCRAPE_TIMEOUT_SEC,
            )
    except HTTPException:
        raise
    except TimeoutError as e:
        logger.warning("Property appraiser scrape timed out for %s: %s", address, e)
        raise HTTPException(
            status_code=502,
            detail="Property appraiser lookup timed out. Try Refresh.",
        ) from e
    except Exception as e:
        logger.warning("Property appraiser scrape failed for %s: %s", address, e)
        raise HTTPException(
            status_code=502,
            detail=f"Property appraiser lookup failed: {e}",
        ) from e

    path: str | None = None
    if user_id and claim_id:
        path = persist_property_appraiser(
            user_id,
            claim_id,
            page.screenshot,
            previous_meta=prev,
        )

    return PropertyAppraiserResult(
        resolved_address=geocoded.resolved_address,
        latitude=geocoded.latitude,
        longitude=geocoded.longitude,
        county=county,
        fetch_key=fetch_key,
        path=path,
        preview=_preview_data_url(page.screenshot),
        source_url=page.source_url or page.fields.source_url,
        fields=page.fields,
    )


def playwright_browsers_configured() -> bool:
    path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    return bool(path)
