"""Tests for Drive folder matching by property address."""

from app.drive_client import match_folders_by_address


def test_match_folders_single_strong_match(monkeypatch):
    folders = [
        {"id": "a1", "name": "412 Gulfview Drive"},
        {"id": "b2", "name": "999 Other St"},
    ]

    monkeypatch.setattr(
        "app.drive_client.list_job_folder_candidates",
        lambda _root: folders,
    )

    result = match_folders_by_address("412 Gulfview Drive, Tampa, FL", "root-id")
    assert result["suggested_id"] == "a1"
    assert result["matches"][0]["score"] >= 0.85


def test_match_folders_strips_version_suffix(monkeypatch):
    folders = [{"id": "v2", "name": "412 Gulfview Drive v2"}]
    monkeypatch.setattr(
        "app.drive_client.list_job_folder_candidates",
        lambda _root: folders,
    )
    result = match_folders_by_address("412 Gulfview Drive", "root-id")
    assert result["suggested_id"] == "v2"


def test_match_folders_no_match(monkeypatch):
    folders = [{"id": "x", "name": "Completely Different Name"}]
    monkeypatch.setattr(
        "app.drive_client.list_job_folder_candidates",
        lambda _root: folders,
    )
    result = match_folders_by_address("412 Gulfview Drive", "root-id")
    assert result["suggested_id"] is None
    assert not [m for m in result["matches"] if m["score"] >= 0.85]
