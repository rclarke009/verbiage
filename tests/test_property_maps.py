"""Tests for Google Maps property location images."""

from __future__ import annotations

import asyncio
import io
import zipfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.report_writer.export import draft_to_docx_bytes, draft_to_pdf_bytes
from app.report_writer.property_maps import (
    fetch_property_maps,
    geocode_address,
    property_map_fetch_key,
    property_map_metadata_from_result,
    property_map_storage_path,
)
from app.report_writer.property_maps import PropertyMapResult


@pytest.fixture
def sample_claim() -> dict:
    return {
        "claim_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "title": "Huseman",
        "property_metadata": {
            "report_type": "engineering",
            "address": "3795 Riviera Cir, Bonita Springs, FL 34134",
            "property_type": "single-family",
            "client_name": "Huseman",
            "inspection_date": "Sep 15, 2023",
            "prepared_by": "Stuart Jay Clarke, CGC and CCC",
            "storm_name": "Ian",
            "storm_date": "September 28, 2022",
            "storm_type": "hurricane",
            "storm_category": "Cat 4",
            "landfall_region": "Near Fort Myers, FL",
            "include_engineering_letter": "true",
        },
        "field_notes": "Roof and interior damage observed.",
    }


@pytest.fixture
def sample_sections() -> dict[str, dict]:
    return {
        "property_overview": {
            "content": "The subject property is a single-family residence with storm-related damage.",
        },
        "recommendations_conclusion": {
            "content": "It is my professional opinion that the property sustained damage during Hurricane Ian.",
        },
    }


@pytest.fixture
def fake_jpeg() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(120, 80, 40)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def geocode_payload() -> dict:
    return {
        "status": "OK",
        "results": [
            {
                "formatted_address": "3795 Riviera Cir, Bonita Springs, FL 34134, USA",
                "geometry": {"location": {"lat": 26.33, "lng": -81.81}},
            }
        ],
    }


def test_property_map_fetch_key_normalizes_whitespace() -> None:
    assert property_map_fetch_key("  3795 Riviera Cir ") == "3795 riviera cir"


def test_property_map_storage_path() -> None:
    path = property_map_storage_path("user-1", "claim-1", "satellite")
    assert path == "user-1/claim-1/property_map_satellite.jpg"


def test_property_map_metadata_from_result() -> None:
    result = PropertyMapResult(
        resolved_address="3795 Riviera Cir, Bonita Springs, FL",
        latitude=26.33,
        longitude=-81.81,
        fetch_key="3795 riviera cir",
        satellite_path="user/claim/property_map_satellite.jpg",
        roadmap_path="user/claim/property_map_roadmap.jpg",
    )
    meta = property_map_metadata_from_result(result)
    assert meta["property_map_fetch_key"] == "3795 riviera cir"
    assert meta["property_latitude"] == "26.33"
    assert meta["property_map_satellite_path"].endswith("satellite.jpg")


def test_geocode_address_success(monkeypatch: pytest.MonkeyPatch, geocode_payload: dict) -> None:
    monkeypatch.setattr("app.report_writer.property_maps.GOOGLE_MAPS_API_KEY", "test-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = geocode_payload

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    monkeypatch.setattr(
        "app.report_writer.property_maps.get_async_client",
        lambda: mock_client,
    )

    result = asyncio.run(geocode_address("3795 Riviera Cir, Bonita Springs, FL"))
    assert result.latitude == 26.33
    assert result.longitude == -81.81
    assert "Bonita Springs" in result.resolved_address


def test_fetch_property_maps_persists_images(
    monkeypatch: pytest.MonkeyPatch,
    geocode_payload: dict,
    fake_jpeg: bytes,
    tmp_path,
) -> None:
    monkeypatch.setattr("app.report_writer.property_maps.GOOGLE_MAPS_API_KEY", "test-key")
    monkeypatch.setattr("app.report_writer.storage.CLAIM_IMAGES_DIR", tmp_path)

    geocode_resp = MagicMock()
    geocode_resp.status_code = 200
    geocode_resp.json.return_value = geocode_payload

    map_resp = MagicMock()
    map_resp.status_code = 200
    map_resp.headers = {"content-type": "image/png"}
    map_resp.content = fake_jpeg

    mock_client = MagicMock()
    map_params: list[dict] = []

    async def fake_get(url, **kwargs):
        if "geocode" in url:
            return geocode_resp
        map_params.append(kwargs.get("params") or {})
        return map_resp

    mock_client.get = fake_get
    monkeypatch.setattr(
        "app.report_writer.property_maps.get_async_client",
        lambda: mock_client,
    )

    result = asyncio.run(
        fetch_property_maps(
            "3795 Riviera Cir, Bonita Springs, FL",
            user_id="user-1",
            claim_id="claim-1",
        )
    )

    assert len(map_params) == 2
    assert all(p.get("zoom") == "19" for p in map_params)

    assert result.satellite_path is not None
    assert result.roadmap_path is not None
    assert (tmp_path / result.satellite_path).is_file()
    assert (tmp_path / result.roadmap_path).is_file()
    assert result.satellite_preview.startswith("data:image/jpeg;base64,")


def test_docx_export_includes_property_location(
    sample_claim: dict,
    sample_sections: dict[str, dict],
    fake_jpeg: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = {
        **sample_claim,
        "property_metadata": {
            **sample_claim["property_metadata"],
            "property_map_satellite_path": "maps/satellite.jpg",
            "property_map_roadmap_path": "maps/roadmap.jpg",
        },
    }

    def fake_read(path: str) -> bytes:
        return fake_jpeg

    monkeypatch.setattr("app.report_writer.storage.read_claim_image_bytes", fake_read)

    data = draft_to_docx_bytes(sample_sections, claim=claim, images=[])
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        doc_xml = zf.read("word/document.xml").decode("utf-8")
    assert "PROPERTY LOCATION" in doc_xml
    assert "Map data" in doc_xml


def test_pdf_export_includes_property_location(
    sample_claim: dict,
    sample_sections: dict[str, dict],
    fake_jpeg: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = {
        **sample_claim,
        "property_metadata": {
            **sample_claim["property_metadata"],
            "property_map_satellite_path": "maps/satellite.jpg",
            "property_map_roadmap_path": "maps/roadmap.jpg",
        },
    }

    monkeypatch.setattr("app.report_writer.storage.read_claim_image_bytes", lambda _path: fake_jpeg)

    data = draft_to_pdf_bytes(sample_sections, claim=claim, images=[])
    assert data.startswith(b"%PDF")
    assert len(data) > 1000
