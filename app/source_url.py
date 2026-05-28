"""Resolve stored or derived URL for a document (e.g. Google Drive open link from doc_id)."""

from app.drive_client import drive_file_view_url


def resolved_source_url(
    source: str | None,
    doc_id: str,
    stored: str | None,
) -> str | None:
    """
    Return the effective report URL. Stored value wins; for legacy Google Drive
    documents without a stored URL, derive the Drive file view link.
    """
    s = (stored or "").strip()
    if s:
        return s
    if (source or "").strip() == "google_drive" and doc_id:
        return drive_file_view_url(doc_id)
    return None
