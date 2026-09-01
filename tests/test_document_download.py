"""Download original cited Drive files (single + zip)."""

from io import BytesIO
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

from app.document_download import (
    is_drive_backed_source,
    pack_sources_zip,
    safe_download_filename,
    unique_zip_member,
)
from app.drive_client import DriveClientError, GOOGLE_DOCS_MIME, download_drive_source_file
from tests.conftest_api import api_client, clear_api_overrides, run_sync_db_fn

import app.main as main


def test_is_drive_backed_source():
    assert is_drive_backed_source("google_drive")
    assert is_drive_backed_source("Google Drive")
    assert not is_drive_backed_source("uploaded_pdf")
    assert not is_drive_backed_source(None)


def test_safe_and_unique_zip_names():
    assert "/" not in safe_download_filename("a/b.pdf")
    used: set[str] = set()
    assert unique_zip_member("Roof.pdf", used) == "Roof.pdf"
    assert unique_zip_member("Roof.pdf", used) == "Roof_2.pdf"


def test_pack_sources_zip_includes_failures():
    data = pack_sources_zip([("a.pdf", b"%PDF")], ["missing: not found"])
    with ZipFile(BytesIO(data)) as zf:
        names = zf.namelist()
        assert "a.pdf" in names
        assert "failed.txt" in names
        assert b"missing" in zf.read("failed.txt")


def test_download_drive_source_file_exports_google_doc():
    service = MagicMock()
    service.files.return_value.get.return_value.execute.return_value = {
        "id": "g1",
        "name": "Notes",
        "mimeType": GOOGLE_DOCS_MIME,
    }
    service.files.return_value.export_media.return_value.execute.return_value = b"%PDF-doc"
    with patch("app.drive_client._get_credentials"), patch(
        "app.drive_client._build_service", return_value=service
    ):
        data, mime, name = download_drive_source_file("g1")
    assert data == b"%PDF-doc"
    assert mime == "application/pdf"
    assert name == "Notes.pdf"


def test_download_document_file_drive_pdf():
    client = api_client()
    try:
        with patch.object(main, "with_db_conn_retry_sync", side_effect=run_sync_db_fn):
            with patch.object(
                main,
                "get_document_file_fields",
                return_value={
                    "file-abc": ("Roof.pdf", "google_drive", "https://drive.example/file-abc", "Roof.pdf"),
                },
            ):
                with patch.object(
                    main,
                    "fetch_drive_source",
                    return_value=(b"%PDF-1.4 bytes", "application/pdf", "Roof.pdf"),
                ):
                    resp = client.get("/documents/file-abc/file")
    finally:
        clear_api_overrides()

    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4 bytes"
    assert "Roof.pdf" in resp.headers.get("content-disposition", "")


def test_download_document_file_google_doc_export():
    client = api_client()
    try:
        with patch.object(main, "with_db_conn_retry_sync", side_effect=run_sync_db_fn):
            with patch.object(
                main,
                "get_document_file_fields",
                return_value={
                    "gdoc-1": ("Field notes", "google_drive", None, "Field notes"),
                },
            ):
                with patch.object(
                    main,
                    "fetch_drive_source",
                    return_value=(b"%PDF-export", "application/pdf", "Field notes.pdf"),
                ):
                    resp = client.get("/documents/gdoc-1/file")
    finally:
        clear_api_overrides()

    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")
    assert "Field notes.pdf" in resp.headers.get("content-disposition", "")


def test_download_document_file_uploaded_pdf_404():
    client = api_client()
    try:
        with patch.object(main, "with_db_conn_retry_sync", side_effect=run_sync_db_fn):
            with patch.object(
                main,
                "get_document_file_fields",
                return_value={
                    "up-1": ("manual.pdf", "uploaded_pdf", None, "manual.pdf"),
                },
            ):
                resp = client.get("/documents/up-1/file")
    finally:
        clear_api_overrides()

    assert resp.status_code == 404
    assert "not available" in resp.json()["detail"]


def test_download_document_file_drive_error_503():
    client = api_client()
    try:
        with patch.object(main, "with_db_conn_retry_sync", side_effect=run_sync_db_fn):
            with patch.object(
                main,
                "get_document_file_fields",
                return_value={"file-abc": ("Roof.pdf", "google_drive", None, "Roof.pdf")},
            ):
                with patch.object(
                    main,
                    "fetch_drive_source",
                    side_effect=DriveClientError("quota"),
                ):
                    resp = client.get("/documents/file-abc/file")
    finally:
        clear_api_overrides()

    assert resp.status_code == 503


def test_download_zip_mixed_success():
    client = api_client()

    def fake_fetch(doc_id: str, _name: str | None):
        if doc_id == "ok-1":
            return b"pdf-ok", "application/pdf", "Ok.pdf"
        raise DriveClientError("gone")

    try:
        with patch.object(main, "with_db_conn_retry_sync", side_effect=run_sync_db_fn):
            with patch.object(
                main,
                "get_document_file_fields",
                return_value={
                    "ok-1": ("Ok.pdf", "google_drive", None, "Ok.pdf"),
                    "bad-1": ("Bad.pdf", "google_drive", None, "Bad.pdf"),
                    "up-1": ("manual.pdf", "uploaded_pdf", None, "manual.pdf"),
                },
            ):
                with patch.object(main, "fetch_drive_source", side_effect=fake_fetch):
                    resp = client.post(
                        "/documents/download-zip",
                        json={"doc_ids": ["ok-1", "bad-1", "up-1"]},
                    )
    finally:
        clear_api_overrides()

    assert resp.status_code == 200
    with ZipFile(BytesIO(resp.content)) as zf:
        assert "Ok.pdf" in zf.namelist()
        failed = zf.read("failed.txt").decode()
        assert "Bad.pdf" in failed
        assert "manual.pdf" in failed
