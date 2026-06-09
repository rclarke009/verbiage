"""Drive ingest MIME allowlist and query helpers."""

from unittest.mock import MagicMock, patch

from app.drive_client import (
    DOCX_MIME,
    DRIVE_INGEST_MIMES,
    FOLDER_MIME,
    GOOGLE_DOCS_MIME,
    PDF_MIME,
    drive_mime_query_clause,
    is_drive_ingestable_mime,
    list_docs_metadata,
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


def test_list_docs_metadata_recurses_one_level_into_subfolders():
    """zfinished/<report folder>/<report> layout: files in subfolders are found."""
    queries: list[str] = []

    def fake_list(q, pageSize, fields, pageToken, **_kwargs):
        queries.append(q)
        # Subfolder discovery query for the top folder.
        if FOLDER_MIME in q and "'zfinished' in parents" in q:
            files = [{"id": "subA"}, {"id": "subB"}]
        # File queries are batched by parent ids OR'd together.
        elif "'zfinished' in parents" in q or "'subA' in parents" in q or "'subB' in parents" in q:
            files = []
            if "'zfinished' in parents" in q:
                files.append({"id": "top_pdf", "name": "Top.pdf", "mimeType": PDF_MIME})
            if "'subA' in parents" in q:
                files.append({"id": "a_doc", "name": "A.gdoc", "mimeType": GOOGLE_DOCS_MIME})
            if "'subB' in parents" in q:
                files.append({"id": "b_docx", "name": "B.docx", "mimeType": DOCX_MIME})
        else:
            files = []
        return MagicMock(execute=lambda: {"files": files, "nextPageToken": None})

    service = MagicMock()
    service.files.return_value.list = fake_list

    with patch("app.drive_client._get_credentials", return_value=MagicMock()), patch(
        "app.drive_client.build", return_value=service
    ):
        result = list_docs_metadata(folder_id="zfinished")

    ids = {f["id"] for f in result}
    assert ids == {"top_pdf", "a_doc", "b_docx"}
    # The subfolders must have been discovered and then queried for files.
    assert any(FOLDER_MIME in q for q in queries)


def test_list_docs_metadata_dedupes_files_seen_in_multiple_parents():
    def fake_list(q, pageSize, fields, pageToken, **_kwargs):
        if FOLDER_MIME in q:
            files = [{"id": "sub1"}]
        else:
            # Same file appears for both the top folder and the subfolder batch.
            files = [{"id": "dupe", "name": "D.pdf", "mimeType": PDF_MIME}]
        return MagicMock(execute=lambda: {"files": files, "nextPageToken": None})

    service = MagicMock()
    service.files.return_value.list = fake_list

    with patch("app.drive_client._get_credentials", return_value=MagicMock()), patch(
        "app.drive_client.build", return_value=service
    ), patch("app.drive_client.DRIVE_PARENTS_PER_QUERY", 1):
        result = list_docs_metadata(folder_id="top")

    assert [f["id"] for f in result] == ["dupe"]
