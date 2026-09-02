"""Parse WindowTest Full Job Package ZIPs into Verbiage claims."""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from app.report_writer.document_layout import get_layout, ordered_included_photos, section_keys_visible
from app.report_writer.job_package_import import JobPackageError, parse_full_job_package


def _package_zip(job: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "full-job-package.json",
            json.dumps({"version": "1.0", "job": job}),
        )
        zf.writestr("photos/1-Leak Close-ups-0.jpg", b"\xff\xd8\xff\xd9")
    return buf.getvalue()


def test_parse_full_job_package_windows_and_captions() -> None:
    job = {
        "jobId": "W2026-1",
        "clientName": "Acme LLC",
        "addressLine1": "100 Test St",
        "city": "Tampa",
        "state": "FL",
        "zip": "33610",
        "includePageNumbersInReport": True,
        "includeAddressInReport": True,
        "reportStartingPageNumber": 12,
        "customPurposeText": "Inspect windows.",
        "windows": [
            {
                "windowId": "w1",
                "windowNumber": "Specimen 1",
                "testResult": "Fail",
                "isInaccessible": False,
                "photos": [
                    {
                        "imageFile": "photos/1-Leak Close-ups-0.jpg",
                        "notes": "Water at frame.",
                        "includeInReport": True,
                        "photoType": "Leak Close-ups",
                    }
                ],
            }
        ],
    }
    parsed = parse_full_job_package(_package_zip(job))
    assert parsed.job["clientName"] == "Acme LLC"
    assert len(parsed.specimens) == 1
    assert parsed.specimens[0].label == "Specimen 1"
    assert parsed.specimens[0].result == "Fail"
    assert parsed.specimens[0].photos[0].notes == "Water at frame."
    assert parsed.specimens[0].photos[0].data.startswith(b"\xff\xd8")


def test_parse_rejects_non_zip() -> None:
    with pytest.raises(JobPackageError):
        parse_full_job_package(b"not a zip")


def test_layout_hides_and_orders_sections() -> None:
    layout = {
        "section_order": ["test_summary", "overview"],
        "hidden_sections": ["weather_history"],
        "photos": [],
        "specimens": [],
    }
    keys = section_keys_visible(layout, "window_test")
    assert keys[0] == "test_summary"
    assert "weather_history" not in keys
    assert "recommendations_conclusion" in keys


def test_ordered_included_photos_skips_hidden() -> None:
    layout = {
        "photos": [
            {"image_id": "a", "include": False, "caption": "no", "sort_order": 0},
            {"image_id": "b", "include": True, "caption": "yes", "sort_order": 1},
        ]
    }
    images = [
        {"image_id": "a", "vision_analysis": {}},
        {"image_id": "b", "vision_analysis": {}},
    ]
    out = ordered_included_photos(layout, images)
    assert [i["image_id"] for i in out] == ["b"]
    assert out[0]["_layout_caption"] == "yes"


def test_get_layout_honors_engineering_letter_flag() -> None:
    layout = get_layout({"report_type": "engineering", "include_engineering_letter": "false"})
    assert layout["include_engineering_letter"] is False
