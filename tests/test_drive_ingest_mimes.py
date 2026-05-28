"""Drive ingest MIME allowlist and query helpers."""

from app.drive_client import (
    DOCX_MIME,
    DRIVE_INGEST_MIMES,
    GOOGLE_DOCS_MIME,
    PDF_MIME,
    drive_mime_query_clause,
    is_drive_ingestable_mime,
)


def test_drive_ingest_mimes_includes_expected_types():
    assert GOOGLE_DOCS_MIME in DRIVE_INGEST_MIMES
    assert PDF_MIME in DRIVE_INGEST_MIMES
    assert DOCX_MIME in DRIVE_INGEST_MIMES
    assert len(DRIVE_INGEST_MIMES) == 3


def test_is_drive_ingestable_mime():
    assert is_drive_ingestable_mime(GOOGLE_DOCS_MIME)
    assert is_drive_ingestable_mime(PDF_MIME)
    assert is_drive_ingestable_mime(DOCX_MIME)
    assert not is_drive_ingestable_mime("application/msword")
    assert not is_drive_ingestable_mime(None)
    assert not is_drive_ingestable_mime("")


def test_drive_mime_query_clause():
    clause = drive_mime_query_clause()
    assert clause.startswith("(")
    assert clause.endswith(")")
    assert f"mimeType = '{PDF_MIME}'" in clause
    assert f"mimeType = '{GOOGLE_DOCS_MIME}'" in clause
    assert f"mimeType = '{DOCX_MIME}'" in clause
    assert " or " in clause
