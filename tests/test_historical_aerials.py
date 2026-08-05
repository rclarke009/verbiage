"""Tests for NAIP historical aerial imagery."""

from __future__ import annotations

import asyncio
import io
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.report_writer.export import draft_to_docx_bytes, draft_to_pdf_bytes
from app.report_writer.historical_aerials import (
    HistoricalAerialItem,
    HistoricalAerialsResult,
    fetch_historical_aerials,
    historical_aerial_storage_path,
    historical_aerials_fetch_key,
    merge_historical_aerials_metadata,
    parse_historical_aerials_list,
    select_years,
)


@pytest.fixture
def sample_claim() -> dict:
    return {
        "claim_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "title": "Sample Client",
        "property_metadata": {
            "report_type": "engineering",
            "address": "100 Example Lane, Testville, FL 30001",
            "property_type": "single-family",
            "client_name": "Sample Client",
            "inspection_date": "Sep 15, 2023",
            "prepared_by": "Licensed Professional Engineer",
            "storm_name": "Ian",
            "storm_date": "September 28, 2022",
            "storm_date_iso": "2022-09-28",
            "storm_type": "hurricane",
            "storm_category": "Cat 4",
            "landfall_region": "Near Example Coast, FL",
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
    Image.new("RGB", (64, 64), color=(40, 120, 60)).save(buf, format="JPEG", quality=90)
    # Ensure size exceeds blank-image threshold used by fetch path.
    data = buf.getvalue()
    if len(data) < 12_000:
        buf = io.BytesIO()
        Image.new("RGB", (640, 480), color=(40, 120, 60)).save(buf, format="JPEG", quality=85)
        data = buf.getvalue()
    return data


def test_select_years_under_cap() -> None:
    assert select_years([2021, 2023], 5) == [2021, 2023]


def test_select_years_caps_with_ends() -> None:
    years = [2015, 2017, 2019, 2021, 2022, 2023]
    selected = select_years(years, 5)
    assert len(selected) == 5
    assert selected[0] == 2015
    assert selected[-1] == 2023


def test_select_years_empty() -> None:
    assert select_years([], 5) == []


def test_historical_aerials_fetch_key() -> None:
    assert historical_aerials_fetch_key("  100 Example Lane ", 2022) == "100 example lane|2022"


def test_historical_aerial_storage_path() -> None:
    path = historical_aerial_storage_path("user-1", "claim-1", 2021)
    assert path == "user-1/claim-1/historical_aerial_2021.jpg"


def test_parse_historical_aerials_list_preserves_include() -> None:
    items = parse_historical_aerials_list(
        [
            {"year": 2021, "path": "a.jpg", "include": True},
            {"year": "2023", "path": "b.jpg", "include": "false"},
        ]
    )
    assert items[0]["include"] is True
    assert items[1]["include"] is False
    assert items[1]["year"] == 2023


def test_merge_preserves_include_and_comment() -> None:
    result = HistoricalAerialsResult(
        resolved_address="100 Example Lane",
        latitude=26.33,
        longitude=-81.81,
        fetch_key="100 example lane|2022",
        dol_year=2022,
        aerials=[
            HistoricalAerialItem(year=2021, path="u/c/historical_aerial_2021.jpg"),
            HistoricalAerialItem(year=2023, path="u/c/historical_aerial_2023.jpg"),
        ],
    )
    prev = {
        "historical_aerials_comment": "Tree canopy unchanged.",
        "historical_aerials": [
            {"year": 2021, "path": "old.jpg", "include": True},
            {"year": 2019, "path": "gone.jpg", "include": True},
        ],
    }
    meta = merge_historical_aerials_metadata(result, previous_meta=prev)
    assert meta["historical_aerials_comment"] == "Tree canopy unchanged."
    by_year = {item["year"]: item for item in meta["historical_aerials"]}
    assert by_year[2021]["include"] is True
    assert by_year[2023]["include"] is False


def test_fetch_historical_aerials_persists_images(
    monkeypatch: pytest.MonkeyPatch,
    fake_jpeg: bytes,
    tmp_path,
) -> None:
    monkeypatch.setattr("app.report_writer.storage.CLAIM_IMAGES_DIR", tmp_path)
    monkeypatch.setattr(
        "app.report_writer.historical_aerials.list_naip_catalog_years",
        AsyncMock(return_value=[2019, 2021, 2022, 2023]),
    )
    monkeypatch.setattr(
        "app.report_writer.historical_aerials.export_naip_year_image",
        AsyncMock(return_value=fake_jpeg),
    )
    monkeypatch.setattr(
        "app.report_writer.historical_aerials.geocode_address",
        AsyncMock(
            return_value=MagicMock(
                latitude=26.33,
                longitude=-81.81,
                resolved_address="100 Example Lane, Testville, FL",
            )
        ),
    )

    result = asyncio.run(
        fetch_historical_aerials(
            "100 Example Lane, Testville, FL",
            "2022-09-28",
            user_id="user-1",
            claim_id="claim-1",
        )
    )

    assert result.dol_year == 2022
    assert result.fetch_key.endswith("|2022")
    assert "100 example lane" in result.fetch_key
    assert len(result.aerials) == 2  # 2022, 2023 (>= DOL)
    assert all(a.path and (tmp_path / a.path).is_file() for a in result.aerials)
    assert all(a.preview.startswith("data:image/jpeg;base64,") for a in result.aerials)
    assert all(a.include is False for a in result.aerials)


def test_fetch_skips_blank_years_and_backfills(
    monkeypatch: pytest.MonkeyPatch,
    fake_jpeg: bytes,
    tmp_path,
) -> None:
    monkeypatch.setattr("app.report_writer.storage.CLAIM_IMAGES_DIR", tmp_path)
    monkeypatch.setattr(
        "app.report_writer.historical_aerials.list_naip_catalog_years",
        AsyncMock(return_value=[2019, 2020, 2021, 2022, 2023]),
    )

    async def fake_export(_lat, _lon, year: int):
        if year == 2022:
            return None
        return fake_jpeg

    monkeypatch.setattr(
        "app.report_writer.historical_aerials.export_naip_year_image",
        fake_export,
    )
    monkeypatch.setattr(
        "app.report_writer.historical_aerials.geocode_address",
        AsyncMock(
            return_value=MagicMock(
                latitude=26.33,
                longitude=-81.81,
                resolved_address="100 Example Lane",
            )
        ),
    )

    result = asyncio.run(
        fetch_historical_aerials(
            "100 Example Lane",
            "September 28, 2019",
            user_id="user-1",
            claim_id="claim-1",
        )
    )
    years = [a.year for a in result.aerials]
    assert 2022 not in years
    assert len(years) <= 5
    assert years


def test_docx_export_omits_aerials_when_none_included(
    sample_claim: dict,
    sample_sections: dict[str, dict],
    fake_jpeg: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = {
        **sample_claim,
        "property_metadata": {
            **sample_claim["property_metadata"],
            "historical_aerials_comment": "Should not appear.",
            "historical_aerials": [
                {"year": 2021, "path": "maps/a2021.jpg", "include": False},
                {"year": 2023, "path": "maps/a2023.jpg", "include": False},
            ],
        },
    }
    monkeypatch.setattr(
        "app.report_writer.report_document.read_claim_image_bytes",
        lambda _p: fake_jpeg,
    )
    data = draft_to_docx_bytes(sample_sections, claim=claim, images=[])
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        doc_xml = zf.read("word/document.xml").decode("utf-8")
    assert "HISTORICAL AERIAL IMAGERY" not in doc_xml
    assert "Should not appear." not in doc_xml


def test_docx_export_includes_selected_aerials_and_comment(
    sample_claim: dict,
    sample_sections: dict[str, dict],
    fake_jpeg: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = {
        **sample_claim,
        "property_metadata": {
            **sample_claim["property_metadata"],
            "historical_aerials_comment": "Roof appears unchanged since 2021.",
            "historical_aerials": [
                {"year": 2021, "path": "maps/a2021.jpg", "include": True},
                {"year": 2023, "path": "maps/a2023.jpg", "include": False},
            ],
        },
    }
    monkeypatch.setattr(
        "app.report_writer.report_document.read_claim_image_bytes",
        lambda _p: fake_jpeg,
    )
    data = draft_to_docx_bytes(sample_sections, claim=claim, images=[])
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        doc_xml = zf.read("word/document.xml").decode("utf-8")
    assert "HISTORICAL AERIAL IMAGERY" in doc_xml
    assert "Roof appears unchanged since 2021." in doc_xml
    assert "2021" in doc_xml
    assert "NAIP" in doc_xml


def test_pdf_export_includes_selected_aerials(
    sample_claim: dict,
    sample_sections: dict[str, dict],
    fake_jpeg: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = {
        **sample_claim,
        "property_metadata": {
            **sample_claim["property_metadata"],
            "historical_aerials_comment": "Canopy stable.",
            "historical_aerials": [
                {"year": 2023, "path": "maps/a2023.jpg", "include": True},
            ],
        },
    }
    monkeypatch.setattr(
        "app.report_writer.report_document.read_claim_image_bytes",
        lambda _p: fake_jpeg,
    )
    data = draft_to_pdf_bytes(sample_sections, claim=claim, images=[])
    assert data.startswith(b"%PDF")
    assert len(data) > 1000


def test_historical_aerial_image_clears_stale_path(
    sample_claim: dict,
) -> None:
    from fastapi.testclient import TestClient

    import app.main as main
    from app.auth import get_current_user

    claim = {
        **sample_claim,
        "property_metadata": {
            **sample_claim["property_metadata"],
            "historical_aerials": [
                {"year": 2021, "path": "maps/missing.jpg", "include": False},
            ],
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
                f"/report-writer/claims/{sample_claim['claim_id']}/historical-aerials/image"
                "?year=2021"
            )
        assert resp.status_code == 404
        assert updates
        aerials = updates[0].get("historical_aerials") or []
        assert aerials[0]["path"] is None
    finally:
        main.app.dependency_overrides.pop(get_current_user, None)
