"""Tests for async ingest batch/job helpers and stale re-index logic."""

from app.drive_client import compute_index_status
from app.ingest_jobs import IngestBatchEnqueueResponse, IngestBatchStatusResponse


def test_compute_index_status_stale_triggers_reindex():
    assert compute_index_status(True, 200, 100) == "stale"


def test_compute_index_status_up_to_date_skips():
    assert compute_index_status(True, 100, 100) == "indexed"
    assert compute_index_status(True, 99, 100) == "indexed"


def test_compute_index_status_not_in_db_is_new():
    assert compute_index_status(False, 200, None) == "not_indexed"


def test_batch_enqueue_response_model():
    r = IngestBatchEnqueueResponse(batch_id="abc", total=3, job_ids=["j1", "j2", "j3"])
    assert r.total == 3
    assert len(r.job_ids) == 3


def test_batch_status_response_model():
    r = IngestBatchStatusResponse(
        batch_id="abc",
        kind="google_drive",
        status="running",
        total=5,
        pending=2,
        running=1,
        succeeded=1,
        failed=1,
        skipped=0,
        errors=["doc1: export failed"],
    )
    assert r.status == "running"
    assert r.failed == 1
