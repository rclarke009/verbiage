"""Tests for county property-appraiser screenshots."""

from __future__ import annotations

import asyncio
import io
import zipfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.report_writer.export import draft_to_docx_bytes, draft_to_pdf_bytes
from app.report_writer.prompts import build_section_prompt
from app.report_writer.property_appraiser import (
    ParcelFields,
    ParcelPage,
    fetch_property_appraiser,
    parse_appraiser_text,
    parse_street_search,
    property_appraiser_fetch_key,
    property_appraiser_storage_path,
)
from app.report_writer.property_maps import geocode_address


@pytest.fixture
def sample_claim() -> dict:
    return {
        "claim_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "title": "Gamiotea",
        "property_metadata": {
            "report_type": "engineering",
            "address": "707 E Hickory Street, Arcadia, FL 34266",
            "property_type": "single-family",
            "client_name": "Kathey Gamiotea",
            "inspection_date": "Jul 21, 2026",
            "prepared_by": "Licensed Professional Engineer",
            "storm_name": "Ian",
            "storm_date": "September 28, 2022",
            "include_engineering_letter": "true",
        },
        "field_notes": "Roof and interior damage observed.",
    }


@pytest.fixture
def sample_sections() -> dict[str, dict]:
    return {
        "property_overview": {
            "content": "The subject property is a single-family residence.",
        },
        "recommendations_conclusion": {
            "content": "It is my professional opinion that the property sustained damage during Hurricane Ian.",
        },
    }


@pytest.fixture
def fake_jpeg() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(40, 80, 120)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def geocode_desoto() -> dict:
    return {
        "status": "OK",
        "results": [
            {
                "formatted_address": "707 E Hickory St, Arcadia, FL 34266, USA",
                "geometry": {"location": {"lat": 27.21, "lng": -81.85}},
                "address_components": [
                    {"long_name": "DeSoto County", "short_name": "DeSoto County", "types": ["administrative_area_level_2"]},
                    {"long_name": "Florida", "short_name": "FL", "types": ["administrative_area_level_1"]},
                ],
            }
        ],
    }


@pytest.fixture
def geocode_hillsborough() -> dict:
    return {
        "status": "OK",
        "results": [
            {
                "formatted_address": "100 Example Lane, Tampa, FL 33602, USA",
                "geometry": {"location": {"lat": 27.95, "lng": -82.45}},
                "address_components": [
                    {
                        "long_name": "Hillsborough County",
                        "short_name": "Hillsborough County",
                        "types": ["administrative_area_level_2"],
                    }
                ],
            }
        ],
    }


def _patch_geocode(monkeypatch: pytest.MonkeyPatch, payload: dict) -> None:
    monkeypatch.setattr("app.report_writer.property_maps.GOOGLE_MAPS_API_KEY", "test-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload
    mock_client = MagicMock()

    async def fake_get(*_args, **_kwargs):
        return mock_resp

    mock_client.get = fake_get
    monkeypatch.setattr("app.report_writer.property_maps.get_async_client", lambda: mock_client)


def test_property_appraiser_fetch_key_normalizes() -> None:
    assert property_appraiser_fetch_key("  707 E Hickory St ") == "707 e hickory st"


def test_property_appraiser_storage_path() -> None:
    assert property_appraiser_storage_path("u1", "c1") == "u1/c1/property_appraiser.jpg"


def test_parse_street_search() -> None:
    number, street = parse_street_search("707 E Hickory Street, Arcadia, FL 34266")
    assert number == "707"
    assert street.startswith("E Hickory")


def test_parse_appraiser_text() -> None:
    text = (
        "Parcel ID: 31-37-25-0224-00A0-0180 (17423)\n"
        "Owner: GAMIOTEA KATHEY L\n"
        "Site Address: 707 E HICKORY ST, ARCADIA\n"
        "Use Code: SINGLE FAMILY (0100)\n"
        "Area: 0.382 AC\n"
        "Legal Description: MILLS ADD TO ARCADIA LOTS 18 & 19\n"
    )
    fields = parse_appraiser_text(text, source_url="https://www.desotopa.com/gis/")
    assert "31-37-25" in fields.parcel_id
    assert "GAMIOTEA" in fields.owner
    assert "HICKORY" in fields.site_address
    assert "SINGLE FAMILY" in fields.use_code
    assert "0.382" in fields.acreage


def test_geocode_extracts_county(monkeypatch: pytest.MonkeyPatch, geocode_desoto: dict) -> None:
    _patch_geocode(monkeypatch, geocode_desoto)
    result = asyncio.run(geocode_address("707 E Hickory Street, Arcadia, FL"))
    assert result.county == "DeSoto"


def test_unsupported_county_returns_422(
    monkeypatch: pytest.MonkeyPatch,
    geocode_hillsborough: dict,
) -> None:
    _patch_geocode(monkeypatch, geocode_hillsborough)

    async def boom(_county: str, _address: str) -> ParcelPage:
        raise AssertionError("scrape should not run for unsupported county")

    monkeypatch.setattr("app.report_writer.property_appraiser.scrape_parcel_page", boom)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(fetch_property_appraiser("100 Example Lane, Tampa, FL"))
    assert exc.value.status_code == 422
    assert "Hillsborough" in str(exc.value.detail)


def test_fetch_property_appraiser_persists_screenshot(
    monkeypatch: pytest.MonkeyPatch,
    geocode_desoto: dict,
    fake_jpeg: bytes,
    tmp_path,
) -> None:
    _patch_geocode(monkeypatch, geocode_desoto)
    monkeypatch.setattr("app.report_writer.storage.CLAIM_IMAGES_DIR", tmp_path)

    async def fake_scrape(_county: str, _address: str) -> ParcelPage:
        return ParcelPage(
            screenshot=fake_jpeg,
            fields=ParcelFields(
                parcel_id="31-37-25-0224-00A0-0180",
                owner="GAMIOTEA KATHEY L",
                site_address="707 E HICKORY ST, ARCADIA",
                use_code="SINGLE FAMILY (0100)",
                acreage="0.382 AC",
                source_url="https://www.desotopa.com/gis/",
            ),
            source_url="https://www.desotopa.com/gis/",
        )

    monkeypatch.setattr("app.report_writer.property_appraiser.scrape_parcel_page", fake_scrape)

    result = asyncio.run(
        fetch_property_appraiser(
            "707 E Hickory Street, Arcadia, FL 34266",
            user_id="user-1",
            claim_id="claim-1",
        )
    )
    assert result.path is not None
    assert (tmp_path / result.path).is_file()
    assert result.fields.parcel_id.startswith("31-37-25")
    assert result.preview.startswith("data:image/jpeg;base64,")
    assert result.county == "DeSoto"


def test_fetch_property_appraiser_uses_cache(
    monkeypatch: pytest.MonkeyPatch,
    geocode_desoto: dict,
    fake_jpeg: bytes,
    tmp_path,
) -> None:
    _patch_geocode(monkeypatch, geocode_desoto)
    monkeypatch.setattr("app.report_writer.storage.CLAIM_IMAGES_DIR", tmp_path)
    cached_path = "user-1/claim-1/property_appraiser.jpg"
    (tmp_path / "user-1" / "claim-1").mkdir(parents=True)
    (tmp_path / cached_path).write_bytes(fake_jpeg)

    calls = {"n": 0}

    async def fake_scrape(_county: str, _address: str) -> ParcelPage:
        calls["n"] += 1
        raise AssertionError("should use cache")

    monkeypatch.setattr("app.report_writer.property_appraiser.scrape_parcel_page", fake_scrape)

    result = asyncio.run(
        fetch_property_appraiser(
            "707 E Hickory Street, Arcadia, FL 34266",
            user_id="user-1",
            claim_id="claim-1",
            previous_meta={
                "property_appraiser_fetch_key": property_appraiser_fetch_key(
                    "707 E Hickory Street, Arcadia, FL 34266"
                ),
                "property_appraiser_path": cached_path,
                "property_appraiser_parcel_id": "cached-id",
            },
        )
    )
    assert calls["n"] == 0
    assert result.fields.parcel_id == "cached-id"
    assert result.path == cached_path


def test_docx_export_includes_property_appraiser(
    sample_claim: dict,
    sample_sections: dict[str, dict],
    fake_jpeg: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = {
        **sample_claim,
        "property_metadata": {
            **sample_claim["property_metadata"],
            "property_appraiser_path": "pa/shot.jpg",
            "property_appraiser_county": "DeSoto",
            "property_appraiser_source_url": "https://www.desotopa.com/gis/",
        },
    }
    monkeypatch.setattr("app.report_writer.storage.read_claim_image_bytes", lambda _path: fake_jpeg)

    data = draft_to_docx_bytes(sample_sections, claim=claim, images=[])
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        doc_xml = zf.read("word/document.xml").decode("utf-8")
    assert "PROPERTY APPRAISER" in doc_xml
    assert "DeSoto County Property Appraiser" in doc_xml
    pa_at = doc_xml.index("PROPERTY APPRAISER")
    loc_at = doc_xml.find("PROPERTY LOCATION")
    assert loc_at == -1 or pa_at < loc_at


def test_pdf_export_includes_property_appraiser(
    sample_claim: dict,
    sample_sections: dict[str, dict],
    fake_jpeg: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = {
        **sample_claim,
        "property_metadata": {
            **sample_claim["property_metadata"],
            "property_appraiser_path": "pa/shot.jpg",
            "property_appraiser_county": "DeSoto",
        },
    }
    monkeypatch.setattr("app.report_writer.storage.read_claim_image_bytes", lambda _path: fake_jpeg)
    data = draft_to_pdf_bytes(sample_sections, claim=claim, images=[])
    assert data.startswith(b"%PDF")
    assert len(data) > 1000


def test_section_prompt_includes_appraiser_fields() -> None:
    prompt = build_section_prompt(
        "property_overview",
        "Property Overview",
        "Metal roof damage.",
        {
            "report_type": "engineering",
            "address": "707 E Hickory Street",
            "property_appraiser_owner": "GAMIOTEA KATHEY L",
            "property_appraiser_parcel_id": "31-37-25-0224-00A0-0180",
            "property_appraiser_path": "secret/path.jpg",
        },
        [],
        {},
    )
    assert "GAMIOTEA KATHEY L" in prompt
    assert "31-37-25-0224-00A0-0180" in prompt
    assert "secret/path.jpg" not in prompt


def test_property_appraiser_image_clears_stale_path(
    sample_claim: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi.testclient import TestClient

    import app.main as main
    from app.auth import get_current_user

    claim = {
        **sample_claim,
        "property_metadata": {
            **sample_claim["property_metadata"],
            "property_appraiser_path": "pa/missing.jpg",
        },
    }
    updates: list[dict] = []

    async def fake_with_conn(_request, fn):
        conn = MagicMock()
        return fn(conn)

    def fake_get_claim(_conn, _claim_id, _user_id):
        return claim

    def fake_update_claim(_conn, _claim_id, _user_id, **kwargs):
        updates.append(kwargs.get("property_metadata") or {})
        claim["property_metadata"] = kwargs["property_metadata"]
        return claim

    def boom(_path: str) -> bytes:
        raise FileNotFoundError("missing")

    main.app.dependency_overrides[get_current_user] = lambda: "test-user"
    client = TestClient(main.app)
    try:
        with (
            patch("app.report_writer.router._with_conn", new=fake_with_conn),
            patch("app.report_writer.router.get_claim", side_effect=fake_get_claim),
            patch("app.report_writer.router.update_claim", side_effect=fake_update_claim),
            patch("app.report_writer.router.read_claim_image_bytes", side_effect=boom),
        ):
            resp = client.get(
                f"/report-writer/claims/{sample_claim['claim_id']}/property-appraiser/image"
            )
        assert resp.status_code == 404
        assert updates
        assert "property_appraiser_path" not in updates[0]
    finally:
        main.app.dependency_overrides.pop(get_current_user, None)
