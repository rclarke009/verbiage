"""
Document-level breadcrumb prefixes for chunk embedding and retrieval.

Prepends stable metadata (title, source, filename) to each chunk at index time
so vectors and lexical search see document context, not just isolated passages.
"""

from __future__ import annotations

from dataclasses import replace

from app.chunking import Chunk


def document_display_title(
    title: str | None,
    source_filename: str | None,
    doc_id: str,
) -> str:
    """Pick the best human-readable document label for breadcrumb lines."""
    for candidate in (title, source_filename, doc_id):
        if candidate and candidate.strip():
            return candidate.strip()
    return doc_id


def build_document_breadcrumb_prefix(
    *,
    doc_id: str,
    title: str | None = None,
    source: str | None = None,
    source_filename: str | None = None,
    storm_name: str | None = None,
    address: str | None = None,
) -> str:
    """
    Build a multi-line prefix in the same [Key: value] style as section labels.

    Always includes a Document line; Source and File lines are omitted when empty
    or redundant with the display title.
    """
    display = document_display_title(title, source_filename, doc_id)
    lines = [f"[Document: {display}]"]
    if address and address.strip():
        lines.append(f"[Location: {address.strip()}]")
    if storm_name and storm_name.strip():
        lines.append(f"[Storm: {storm_name.strip()}]")
    if source and source.strip():
        lines.append(f"[Source: {source.strip()}]")
    if source_filename and source_filename.strip():
        filename = source_filename.strip()
        if filename.lower() != display.lower():
            lines.append(f"[File: {filename}]")
    return "\n".join(lines)


def apply_document_breadcrumb(chunks: list[Chunk], prefix: str) -> list[Chunk]:
    """Prepend document breadcrumb to each chunk's stored/embedded content."""
    if not prefix or not chunks:
        return chunks
    header = f"{prefix}\n\n"
    return [replace(chunk, content=f"{header}{chunk.content}") for chunk in chunks]
