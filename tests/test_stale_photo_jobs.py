"""Tests for stale ingest job reclaim and stuck photo retry helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import app.main as main
from app.auth import get_current_user
from app.db import has_active_vision_job, reclaim_stale_ingest_jobs


def test_reclaim_stale_ingest_jobs_refreshes_batches():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchall.return_value = [("batch-1",), ("batch-1",), ("batch-2",)]
    cur.rowcount = 3

    with patch("app.db.refresh_batch_counts") as refresh:
        count = reclaim_stale_ingest_jobs(conn, max_age_minutes=15)

    assert count == 3
    sql = cur.execute.call_args[0][0]
    assert "status = 'running'" in sql
    assert "interval '1 minute'" in sql
    assert refresh.call_count == 2
    refresh.assert_any_call(conn, "batch-1")
    refresh.assert_any_call(conn, "batch-2")


def test_reclaim_stale_ingest_jobs_immediate_for_claim():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchall.return_value = [("batch-9",)]
    cur.rowcount = 1

    with patch("app.db.refresh_batch_counts"):
        count = reclaim_stale_ingest_jobs(conn, max_age_minutes=None, claim_id="claim-1")

    assert count == 1
    params = cur.execute.call_args[0][1]
    assert params == ["claim-1"]
    sql = cur.execute.call_args[0][0]
    assert "payload->>'claim_id'" in sql
    assert "interval" not in sql


def test_has_active_vision_job():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = (True,)

    assert has_active_vision_job(conn, "img-1") is True
    cur.execute.assert_called_once()


def test_reset_stuck_claim_photos_returns_none_when_missing():
    from app.report_writer.queries import reset_stuck_claim_photos

    conn = MagicMock()
    with patch("app.report_writer.queries.get_claim", return_value=None):
        assert reset_stuck_claim_photos(conn, "claim-1", "user-1") is None


def test_reset_stuck_claim_photos_resets_rows():
    from app.report_writer.queries import reset_stuck_claim_photos

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.rowcount = 2

    with patch("app.report_writer.queries.get_claim", return_value={"claim_id": "claim-1"}):
        with patch("app.db.reclaim_stale_ingest_jobs", return_value=1) as reclaim:
            result = reset_stuck_claim_photos(conn, "claim-1", "user-1", max_age_minutes=None)

    assert result == {"reset_images": 2, "reclaimed_jobs": 1}
    reclaim.assert_called_once_with(conn, max_age_minutes=None, claim_id="claim-1")
    conn.commit.assert_called_once()


def test_enqueue_vision_jobs_skips_active():
    from app.report_writer.photo_sync import enqueue_vision_jobs_for_claim

    conn = MagicMock()
    images = [
        {"image_id": "img-1", "drive_file_id": "d1", "vision_analysis": None},
        {"image_id": "img-2", "drive_file_id": "d2", "vision_analysis": None},
    ]

    with patch("app.report_writer.photo_sync.has_active_vision_job", side_effect=[True, False]):
        with patch("app.report_writer.photo_sync.create_ingest_batch", return_value="batch-1"):
            with patch("app.report_writer.photo_sync.insert_ingest_jobs", return_value=["job-1"]) as insert:
                result = enqueue_vision_jobs_for_claim(
                    conn,
                    claim_id="claim-1",
                    user_id="user-1",
                    images=images,
                    skip_active=True,
                )

    assert result["enqueued"] == 1
    assert insert.call_count == 1
    jobs = insert.call_args[0][2]
    assert len(jobs) == 1
    assert jobs[0][2]["image_id"] == "img-2"


def test_retry_stuck_photos_route():
    main.app.dependency_overrides[get_current_user] = lambda: "test-user"
    client = TestClient(main.app)
    try:
        payload = {
            "reset_images": 3,
            "reclaimed_jobs": 2,
            "batch_id": "batch-1",
            "enqueued": 3,
            "total": 3,
            "image_count": 10,
            "job_ids": ["j1"],
        }
        with patch(
            "app.report_writer.router._with_conn",
            new=AsyncMock(return_value=payload),
        ):
            resp = client.post(
                "/report-writer/claims/00000000-0000-0000-0000-000000000001/photos/retry-stuck",
            )
        assert resp.status_code == 202
        data = resp.json()
        assert data["reset_images"] == 3
        assert data["batch_id"] == "batch-1"
    finally:
        main.app.dependency_overrides.pop(get_current_user, None)
