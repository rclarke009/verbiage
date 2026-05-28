"""Unit tests for Drive folder display and context building."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.drive_client import (
    _folder_display_from_service,
    build_drive_folder_context,
    get_folder_display,
)
from app.main import app


def test_folder_display_breadcrumb_from_service():
    service = MagicMock()
    calls = {
        "child": {"name": "Ready for AI Ingest", "parents": ["parent1"], "mimeType": "application/vnd.google-apps.folder"},
        "parent1": {"name": "Team", "parents": ["root"], "mimeType": "application/vnd.google-apps.folder"},
        "root": {"name": "Shared drives", "parents": [], "mimeType": "application/vnd.google-apps.folder"},
    }

    def fake_get(fileId, fields, supportsAllDrives):
        return MagicMock(execute=lambda: calls[fileId])

    service.files.return_value.get = fake_get
    result = _folder_display_from_service(service, "child")
    assert result["id"] == "child"
    assert result["name"] == "Ready for AI Ingest"
    assert result["path"] == "Shared drives / Team / Ready for AI Ingest"


def test_build_drive_folder_context_uses_env_label_for_default():
    with patch("app.drive_client.GOOGLE_DRIVE_DEFAULT_FOLDER_ID", "inbox99"), patch(
        "app.drive_client.GOOGLE_DRIVE_DEFAULT_FOLDER_LABEL",
        "Shared drives / Team / Ready for AI Ingest",
    ), patch(
        "app.drive_client.get_folder_display",
        return_value={"id": "inbox99", "name": "Ready for AI Ingest", "path": "My Drive / Ready for AI Ingest"},
    ):
        ctx = build_drive_folder_context("inbox99")
    assert ctx is not None
    assert ctx["is_default"] is True
    assert ctx["display_path"] == "Shared drives / Team / Ready for AI Ingest"


def test_build_drive_folder_context_uses_api_path_for_override():
    with patch("app.drive_client.GOOGLE_DRIVE_DEFAULT_FOLDER_ID", "inbox99"), patch(
        "app.drive_client.GOOGLE_DRIVE_DEFAULT_FOLDER_LABEL",
        "Team inbox label",
    ), patch(
        "app.drive_client.get_folder_display",
        return_value={"id": "other11", "name": "Other", "path": "My Drive / Other"},
    ):
        ctx = build_drive_folder_context("other11")
    assert ctx is not None
    assert ctx["is_default"] is False
    assert ctx["display_path"] == "My Drive / Other"


def test_build_drive_folder_context_falls_back_to_id():
    with patch("app.drive_client.GOOGLE_DRIVE_DEFAULT_FOLDER_ID", ""), patch(
        "app.drive_client.GOOGLE_DRIVE_DEFAULT_FOLDER_LABEL",
        "",
    ), patch(
        "app.drive_client.get_folder_display",
        return_value={"id": "abc123", "name": None, "path": None},
    ):
        ctx = build_drive_folder_context("abc123")
    assert ctx is not None
    assert ctx["display_path"] == "abc123"


def test_get_folder_display_returns_nulls_on_failure():
    with patch("app.drive_client._get_credentials", side_effect=RuntimeError("no creds")):
        result = get_folder_display("folder1")
    assert result == {"id": "folder1", "name": None, "path": None}


def test_config_includes_default_folder_label():
    with patch("app.main.GOOGLE_DRIVE_DEFAULT_FOLDER_LABEL", "Ready for AI Ingest"):
        client = TestClient(app)
        res = client.get("/config")
    assert res.status_code == 200
    assert res.json()["google_drive_default_folder_label"] == "Ready for AI Ingest"
