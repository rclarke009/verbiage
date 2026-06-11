"""API smoke tests: route wiring and response shapes without a real database.

TestClient is used WITHOUT a context manager (no app lifespan). DB access is
patched via with_db_conn_retry / with_db_conn_retry_sync; external I/O (embed,
LLM, Drive) is mocked at the route boundary.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import app.main as main
from app.models import IngestResponse, RetrievedChunk
from tests.conftest_api import (
    api_client,
    clear_api_overrides,
    prime_app_state,
    run_async_db_fn,
    run_sync_db_fn,
)

SAMPLE_INGEST = IngestResponse(
    doc_id="doc-1",
    num_chunks=2,
    embedding_model="test-embed",
    dim=768,
    embedding_chars_total=100,
    embedding_tokens_estimate=25,
)

SAMPLE_CHUNK = RetrievedChunk(
    chunk_id="doc-1:0",
    doc_id="doc-1",
    score=0.9,
    content_snippet="Wind damage to shingles.",
    document_title="Storm Report",
    source="upload",
)


def test_health_liveness():
    resp = TestClient(main.app).get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"healthy": True}


def test_config_returns_public_keys():
    resp = TestClient(main.app).get("/config")
    assert resp.status_code == 200
    data = resp.json()
    for key in (
        "supabase_url",
        "supabase_anon_key",
        "signup_invite_enabled",
        "public_app_url",
        "google_drive_default_folder_id",
        "google_drive_default_folder_label",
    ):
        assert key in data


def test_get_documents_returns_list_shape():
    rows = [
        (
            "doc-1",
            "Title",
            "upload",
            1_700_000_000,
            3,
            "snippet",
            None,
            None,
            "file.pdf",
            "emb",
            {"chunk_size": 1200},
        ),
    ]
    client = api_client()
    try:
        with patch.object(main, "with_db_conn_retry_sync", side_effect=run_sync_db_fn):
            with patch.object(main, "list_documents", return_value=rows):
                resp = client.get("/documents")
    finally:
        clear_api_overrides()

    assert resp.status_code == 200
    doc = resp.json()["documents"][0]
    assert doc["doc_id"] == "doc-1"
    assert doc["num_chunks"] == 3
    assert doc["title"] == "Title"


def test_delete_document_not_found():
    client = api_client()
    try:
        with patch.object(main, "with_db_conn_retry_sync", side_effect=run_sync_db_fn):
            with patch.object(main, "remove_document_from_db", return_value=False):
                resp = client.delete("/documents/missing-id")
    finally:
        clear_api_overrides()

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Document not found"


def test_delete_document_ok():
    client = api_client()
    try:
        with patch.object(main, "with_db_conn_retry_sync", side_effect=run_sync_db_fn):
            with patch.object(main, "remove_document_from_db", return_value=True):
                resp = client.delete("/documents/doc-1")
    finally:
        clear_api_overrides()

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_similar_titles_empty_proposed():
    client = api_client()
    try:
        resp = client.get("/documents/similar-titles", params={"proposed": "   "})
    finally:
        clear_api_overrides()

    assert resp.status_code == 200
    assert resp.json() == {"matches": []}


def test_similar_titles_invalid_limit():
    client = api_client()
    try:
        resp = client.get("/documents/similar-titles", params={"proposed": "foo", "limit": 0})
    finally:
        clear_api_overrides()

    assert resp.status_code == 400


def test_similar_titles_returns_matches():
    client = api_client()
    try:
        with patch.object(main, "with_db_conn_retry_sync", side_effect=run_sync_db_fn):
            with patch.object(main, "list_doc_title_pairs", return_value=[("d1", "Maple Ct")]):
                with patch.object(
                    main,
                    "find_similar_titles",
                    return_value=[("d1", "Maple Ct", 0.95)],
                ):
                    resp = client.get(
                        "/documents/similar-titles",
                        params={"proposed": "Maple Court"},
                    )
    finally:
        clear_api_overrides()

    assert resp.status_code == 200
    matches = resp.json()["matches"]
    assert len(matches) == 1
    assert matches[0]["doc_id"] == "d1"
    assert matches[0]["score"] == 0.95


def test_ask_refusal_when_no_context():
    client = api_client()
    mock_embedder = MagicMock()
    mock_embedder.embed_many = AsyncMock(return_value=[[0.1] * 768])
    mock_embedder.model = "test-embed"

    async def ask_retry(request, async_fn):
        prime_app_state(request.app)
        with patch.object(main, "HttpEmbedder", return_value=mock_embedder):
            with patch.object(main, "_retrieve_for_ask", new=AsyncMock(return_value=[])):
                return await async_fn(MagicMock())

    try:
        with patch.object(main, "with_db_conn_retry", new=AsyncMock(side_effect=ask_retry)):
            resp = client.post("/ask", json={"question": "wind damage", "top_k": 5})
    finally:
        clear_api_overrides()

    assert resp.status_code == 200
    data = resp.json()
    assert "don't have relevant context" in data["answer"]
    assert data["top_chunks"] == []


def test_ask_returns_llm_answer_with_chunks():
    client = api_client()
    mock_embedder = MagicMock()
    mock_embedder.embed_many = AsyncMock(return_value=[[0.1] * 768])
    mock_embedder.model = "test-embed"

    async def ask_retry(request, async_fn):
        prime_app_state(request.app)
        with patch.object(main, "HttpEmbedder", return_value=mock_embedder):
            with patch.object(
                main, "_retrieve_for_ask", new=AsyncMock(return_value=[SAMPLE_CHUNK])
            ):
                with patch.object(
                    main.llm_client,
                    "answer_with_context",
                    new=AsyncMock(return_value="Shingle damage noted."),
                ):
                    return await async_fn(MagicMock())

    try:
        with patch.object(main, "with_db_conn_retry", new=AsyncMock(side_effect=ask_retry)):
            resp = client.post("/ask", json={"question": "roof damage", "top_k": 5})
    finally:
        clear_api_overrides()

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "Shingle damage noted."
    assert len(data["top_chunks"]) == 1
    assert data["top_chunks"][0]["doc_id"] == "doc-1"


def test_ingest_text_success():
    client = api_client()
    try:
        with patch.object(main, "with_db_conn_retry", new=AsyncMock(side_effect=run_async_db_fn)):
            with patch.object(main, "ingest_text", new=AsyncMock(return_value=SAMPLE_INGEST)):
                resp = client.post(
                    "/ingest",
                    json={
                        "text": "Storm report body.",
                        "doc_id": "doc-1",
                        "title": "Report",
                        "source": "test",
                    },
                )
    finally:
        clear_api_overrides()

    assert resp.status_code == 200
    data = resp.json()
    assert data["doc_id"] == "doc-1"
    assert data["num_chunks"] == 2


def test_ingest_duplicate_returns_409():
    client = api_client()
    try:
        with patch.object(main, "with_db_conn_retry", new=AsyncMock(side_effect=run_async_db_fn)):
            with patch.object(
                main,
                "ingest_text",
                new=AsyncMock(side_effect=ValueError("doc_id already exists")),
            ):
                resp = client.post(
                    "/ingest",
                    json={"text": "duplicate", "doc_id": "doc-1"},
                )
    finally:
        clear_api_overrides()

    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]


def test_ingest_file_rejects_non_pdf():
    client = api_client()
    try:
        resp = client.post(
            "/ingest/file",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
    finally:
        clear_api_overrides()

    assert resp.status_code == 400
    assert "PDF" in resp.json()["detail"]


def test_ingest_file_accepts_pdf():
    client = api_client()
    try:
        with patch.object(main, "extract_text_from_pdf", return_value="PDF body text."):
            with patch.object(main, "with_db_conn_retry", new=AsyncMock(side_effect=run_async_db_fn)):
                with patch.object(
                    main, "ingest_text", new=AsyncMock(return_value=SAMPLE_INGEST)
                ):
                    resp = client.post(
                        "/ingest/file",
                        files={"file": ("report.pdf", b"%PDF-1.4", "application/pdf")},
                    )
    finally:
        clear_api_overrides()

    assert resp.status_code == 200
    assert resp.json()["doc_id"] == "doc-1"


def test_reindex_not_found():
    client = api_client()
    try:
        with patch.object(main, "with_db_conn_retry", new=AsyncMock(side_effect=run_async_db_fn)):
            with patch.object(main, "get_document_full_text", return_value=None):
                resp = client.post("/documents/missing/reindex", json={})
    finally:
        clear_api_overrides()

    assert resp.status_code == 404


def test_reindex_success():
    client = api_client()
    try:
        with patch.object(main, "with_db_conn_retry", new=AsyncMock(side_effect=run_async_db_fn)):
            with patch.object(main, "get_document_full_text", return_value="Stored full text."):
                with patch.object(
                    main, "reindex_document", new=AsyncMock(return_value=SAMPLE_INGEST)
                ):
                    resp = client.post("/documents/doc-1/reindex", json={})
    finally:
        clear_api_overrides()

    assert resp.status_code == 200
    assert resp.json()["doc_id"] == "doc-1"


def test_ingest_google_drive_enqueues_batch():
    client = api_client()
    drive_files = [
        {
            "id": "file-abc",
            "name": "Report.pdf",
            "mimeType": "application/pdf",
            "modifiedTime": "2024-06-01T12:00:00.000Z",
        },
    ]
    async def enqueue_retry(request, async_fn):
        conn = MagicMock()
        with patch.object(main, "create_ingest_batch", return_value="batch-1"):
            with patch.object(main, "insert_ingest_jobs", return_value=["job-1"]):
                return await async_fn(conn)

    try:
        with patch.object(
            main, "list_docs_metadata_async", new=AsyncMock(return_value=drive_files)
        ):
            with patch.object(main, "with_db_conn_retry", new=AsyncMock(side_effect=enqueue_retry)):
                resp = client.post(
                    "/ingest/google-drive",
                    json={"file_ids": ["file-abc"]},
                )
    finally:
        clear_api_overrides()

    assert resp.status_code == 202
    data = resp.json()
    assert data["batch_id"] == "batch-1"
    assert data["total"] == 1
    assert data["job_ids"] == ["job-1"]


def test_ingest_batch_status_not_found():
    client = api_client()
    try:
        with patch.object(main, "with_db_conn_retry", new=AsyncMock(side_effect=run_async_db_fn)):
            with patch.object(main, "get_ingest_batch", return_value=None):
                resp = client.get("/ingest/batches/missing-batch")
    finally:
        clear_api_overrides()

    assert resp.status_code == 404


def test_ingest_batch_status_returns_counts():
    client = api_client()
    now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    batch = {
        "id": "batch-1",
        "kind": "google_drive",
        "status": "running",
        "total": 2,
        "pending": 1,
        "running": 0,
        "succeeded": 1,
        "failed": 0,
        "skipped": 0,
        "cancelled": 0,
        "created_at": now,
        "updated_at": now,
    }
    client = api_client()
    try:
        with patch.object(main, "with_db_conn_retry", new=AsyncMock(side_effect=run_async_db_fn)):
            with patch.object(main, "get_ingest_batch", return_value=batch):
                with patch.object(main, "get_ingest_batch_errors", return_value=[]):
                    resp = client.get("/ingest/batches/batch-1")
    finally:
        clear_api_overrides()

    assert resp.status_code == 200
    data = resp.json()
    assert data["batch_id"] == "batch-1"
    assert data["status"] == "running"
    assert data["succeeded"] == 1
    assert data["pending"] == 1


def test_ingest_batch_cancel_route():
    client = api_client()

    def do_cancel(conn, batch_id):
        assert batch_id == "batch-1"
        return 3

    try:
        with patch.object(main, "with_db_conn_retry", new=AsyncMock(side_effect=run_async_db_fn)):
            with patch.object(main, "get_ingest_batch", return_value={
                "id": "batch-1",
                "kind": "google_drive",
                "status": "running",
                "total": 5,
                "pending": 3,
                "running": 0,
                "succeeded": 2,
                "failed": 0,
                "skipped": 0,
                "cancelled": 0,
                "created_at": None,
                "updated_at": None,
            }):
                with patch.object(main, "cancel_ingest_batch", side_effect=do_cancel):
                    resp = client.post("/ingest/batches/batch-1/cancel")
    finally:
        clear_api_overrides()

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "cancelled"
    assert data["cancelled_jobs"] == 3


def test_drive_files_lists_with_index_status():
    client = api_client()
    raw = [
        {
            "id": "drive-1",
            "name": "Report.pdf",
            "mimeType": "application/pdf",
            "modifiedTime": "2024-06-01T12:00:00.000Z",
        },
    ]

    async def drive_retry(request, async_fn):
        with patch.object(
            main,
            "get_document_index_by_doc_ids",
            return_value={"drive-1": (1_700_000_000, 4)},
        ):
            return await async_fn(MagicMock())

    try:
        with patch.object(
            main, "list_docs_metadata_async", new=AsyncMock(return_value=raw)
        ):
            with patch.object(main, "with_db_conn_retry", new=AsyncMock(side_effect=drive_retry)):
                with patch.object(
                    main,
                    "resolve_drive_folder_id",
                    return_value=None,
                ):
                    resp = client.get("/drive/files", params={"file_ids": "drive-1"})
    finally:
        clear_api_overrides()

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["files"]) == 1
    assert data["files"][0]["id"] == "drive-1"
    assert data["files"][0]["index_status"] in ("indexed", "stale", "not_indexed")
    assert data["summary"]["total"] == 1
