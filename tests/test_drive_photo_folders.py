"""Tests for Drive photo folder metadata normalization and sync resolution."""

from __future__ import annotations

from app.report_writer.drive_photo_folders import (
    mirror_drive_photo_folder_fields,
    normalize_drive_photo_folders,
    resolve_drive_photo_folder_ids,
)
from app.report_writer.photo_sync import folder_ids_for_claim_sync


def test_normalize_legacy_single_folder():
    assert normalize_drive_photo_folders(
        {
            "drive_photo_folder_id": "folder_a",
            "drive_photo_folder_label": "Job A",
        }
    ) == [{"id": "folder_a", "label": "Job A"}]


def test_normalize_prefers_list_and_dedupes():
    assert normalize_drive_photo_folders(
        {
            "drive_photo_folder_id": "legacy",
            "drive_photo_folders": [
                {"id": "f1", "label": "One"},
                {"id": "f2", "label": "Two"},
                {"id": "f1", "label": "Dup"},
                "skip-me",
            ],
        }
    ) == [
        {"id": "f1", "label": "One"},
        {"id": "f2", "label": "Two"},
    ]


def test_normalize_empty_list_is_authoritative():
    assert (
        normalize_drive_photo_folders(
            {
                "drive_photo_folders": [],
                "drive_photo_folder_id": "legacy",
            }
        )
        == []
    )


def test_resolve_ids_order():
    assert resolve_drive_photo_folder_ids(
        {
            "drive_photo_folders": [
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
            ]
        }
    ) == ["a", "b"]


def test_mirror_fields():
    assert mirror_drive_photo_folder_fields(
        [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]
    ) == {
        "drive_photo_folders": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "drive_photo_folder_id": "a",
        "drive_photo_folder_label": "A",
    }
    assert mirror_drive_photo_folder_fields([]) == {
        "drive_photo_folders": [],
        "drive_photo_folder_id": "",
        "drive_photo_folder_label": "",
    }


def test_folder_ids_for_claim_sync_uses_all_linked():
    meta = {
        "drive_photo_folders": [
            {"id": "a", "label": "A"},
            {"id": "b", "label": "B"},
        ]
    }
    assert folder_ids_for_claim_sync(meta) == ["a", "b"]


def test_folder_ids_for_claim_sync_override():
    meta = {
        "drive_photo_folders": [
            {"id": "a", "label": "A"},
            {"id": "b", "label": "B"},
        ]
    }
    assert folder_ids_for_claim_sync(meta, override_folder_id="only") == ["only"]


def test_sync_claim_photos_from_drive_multiple_folders(monkeypatch):
    import asyncio

    from app.report_writer import photo_sync

    calls: list[str] = []

    async def fake_upsert(conn, *, claim_id, user_id, folder_id, sort_order_start=0):
        calls.append(folder_id)
        return [
            {
                "image_id": f"img-{folder_id}",
                "drive_file_id": f"file-{folder_id}",
                "vision_analysis": None,
            }
        ]

    enqueued: dict = {}

    def fake_enqueue(conn, *, claim_id, user_id, images, skip_active=False):
        enqueued["images"] = images
        return {
            "batch_id": "batch-1",
            "total": len(images),
            "enqueued": len(images),
            "image_count": len(images),
            "job_ids": ["j1", "j2"],
        }

    monkeypatch.setattr(photo_sync, "upsert_images_from_drive_folder", fake_upsert)
    monkeypatch.setattr(photo_sync, "enqueue_vision_jobs_for_claim", fake_enqueue)

    result = asyncio.run(
        photo_sync.sync_claim_photos_from_drive(
            None,
            claim_id="c1",
            user_id="u1",
            folder_ids=["folder_a", "folder_b"],
        )
    )

    assert calls == ["folder_a", "folder_b"]
    assert result["folder_ids"] == ["folder_a", "folder_b"]
    assert result["batch_id"] == "batch-1"
    assert len(enqueued["images"]) == 2
