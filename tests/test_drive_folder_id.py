"""Unit tests for Drive folder id parsing and resolution."""

from unittest.mock import patch

from app.drive_client import parse_drive_folder_id, resolve_drive_folder_id


def test_parse_raw_folder_id():
    assert parse_drive_folder_id("12FGnoHObEnFRQNEUHtHla2Ajx33xauhc") == "12FGnoHObEnFRQNEUHtHla2Ajx33xauhc"


def test_parse_full_folder_url():
    url = "https://drive.google.com/drive/folders/12FGnoHObEnFRQNEUHtHla2Ajx33xauhc"
    assert parse_drive_folder_id(url) == "12FGnoHObEnFRQNEUHtHla2Ajx33xauhc"


def test_parse_folder_url_with_query():
    url = "https://drive.google.com/drive/u/0/folders/abc123_xyz?resourcekey=0"
    assert parse_drive_folder_id(url) == "abc123_xyz"


def test_parse_empty_returns_none():
    assert parse_drive_folder_id(None) is None
    assert parse_drive_folder_id("") is None
    assert parse_drive_folder_id("   ") is None


def test_parse_doc_url_returns_none():
    assert (
        parse_drive_folder_id("https://docs.google.com/document/d/abc123/edit")
        is None
    )


def test_parse_garbage_returns_none():
    assert parse_drive_folder_id("not a folder!!!") is None


def test_resolve_uses_explicit_when_set():
    with patch("app.drive_client.GOOGLE_DRIVE_DEFAULT_FOLDER_ID", "default99"):
        assert resolve_drive_folder_id("explicit11") == "explicit11"


def test_resolve_falls_back_to_default():
    with patch("app.drive_client.GOOGLE_DRIVE_DEFAULT_FOLDER_ID", "default99"):
        assert resolve_drive_folder_id(None) == "default99"
        assert resolve_drive_folder_id("") == "default99"
        assert resolve_drive_folder_id("   ") == "default99"


def test_resolve_none_when_no_default_and_no_explicit():
    with patch("app.drive_client.GOOGLE_DRIVE_DEFAULT_FOLDER_ID", ""):
        assert resolve_drive_folder_id(None) is None


def test_resolve_parses_default_url_from_env():
    with patch(
        "app.drive_client.GOOGLE_DRIVE_DEFAULT_FOLDER_ID",
        "https://drive.google.com/drive/folders/from_env_id",
    ):
        assert resolve_drive_folder_id(None) == "from_env_id"
