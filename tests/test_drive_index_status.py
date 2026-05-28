"""Unit tests for Drive file index status computation."""

from app.drive_client import compute_index_status, _drive_modified_to_unix


def test_not_in_db():
    assert compute_index_status(False, 100, 100) == "not_indexed"
    assert compute_index_status(False, None, None) == "not_indexed"


def test_indexed_when_drive_older_or_equal():
    assert compute_index_status(True, 100, 100) == "indexed"
    assert compute_index_status(True, 99, 100) == "indexed"


def test_stale_when_drive_newer():
    assert compute_index_status(True, 101, 100) == "stale"


def test_missing_timestamps_defaults_indexed():
    assert compute_index_status(True, None, 100) == "indexed"
    assert compute_index_status(True, 100, None) == "indexed"
    assert compute_index_status(True, None, None) == "indexed"


def test_drive_modified_to_unix_parses_z_suffix():
    assert _drive_modified_to_unix("2024-06-01T12:00:00Z") == 1717243200


def test_drive_modified_to_unix_none_for_invalid():
    assert _drive_modified_to_unix(None) is None
    assert _drive_modified_to_unix("not-a-date") is None
