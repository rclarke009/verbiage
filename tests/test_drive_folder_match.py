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


def test_match_folders_owner_client_naming(monkeypatch):
    folders = [
        {"id": "job1", "name": "412 Gulfview Dr - John Smith - Acme Insurance"},
        {"id": "other", "name": "999 Other St - Owner - Client"},
    ]
    monkeypatch.setattr(
        "app.drive_client.list_job_folder_candidates",
        lambda _root: folders,
    )
    result = match_folders_by_address("412 Gulfview Drive, Tampa, FL", "root-id")
    assert result["suggested_id"] == "job1"
    assert result["matches"][0]["score"] >= 0.85


def test_match_folders_st_vs_street_with_owner(monkeypatch):
    folders = [{"id": "s1", "name": "412 Gulfview Street - Owner Name"}]
    monkeypatch.setattr(
        "app.drive_client.list_job_folder_candidates",
        lambda _root: folders,
    )
    result = match_folders_by_address("412 Gulfview St", "root-id")
    assert result["suggested_id"] == "s1"
    assert result["matches"][0]["score"] >= 0.85


def test_match_folders_directional_expansion(monkeypatch):
    folders = [{"id": "d1", "name": "123 North Main Street - Client"}]
    monkeypatch.setattr(
        "app.drive_client.list_job_folder_candidates",
        lambda _root: folders,
    )
    result = match_folders_by_address("123 N Main St", "root-id")
    assert result["suggested_id"] == "d1"
    assert result["matches"][0]["score"] >= 0.85


def test_match_folders_house_number_mismatch(monkeypatch):
    folders = [{"id": "bad", "name": "413 Gulfview Dr - Owner"}]
    monkeypatch.setattr(
        "app.drive_client.list_job_folder_candidates",
        lambda _root: folders,
    )
    result = match_folders_by_address("412 Gulfview Dr", "root-id")
    assert result["suggested_id"] is None
    assert result["matches"] == []


def test_match_folders_filters_low_scores(monkeypatch):
    folders = [{"id": "weak", "name": "Somewhat Similar Address"}]
    monkeypatch.setattr(
        "app.drive_client.list_job_folder_candidates",
        lambda _root: folders,
    )
    result = match_folders_by_address("412 Gulfview Drive", "root-id")
    assert result["matches"] == []
