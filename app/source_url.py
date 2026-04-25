"""Resolve stored or derived URL for a document (e.g. Google Doc open link from doc_id)."""


def resolved_source_url(
    source: str | None,
    doc_id: str,
    stored: str | None,
) -> str | None:
    """
    Return the effective report URL. Stored value wins; for legacy Google Drive
    documents without a stored URL, derive the standard Google Docs open link.
    """
    s = (stored or "").strip()
    if s:
        return s
    if (source or "").strip() == "google_drive" and doc_id:
        return f"https://docs.google.com/document/d/{doc_id}/edit"
    return None
