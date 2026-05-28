"""Shared ingest helpers used by sync endpoints and the background worker."""

from __future__ import annotations

import logging
import time

from app.db import delete_by_doc_id, doc_exist, insert_document, update_document_for_drive_reingest
from app.embeddings import HttpEmbedder
from app.indexing import index_document, reindex_document
from app.models import ChunkingOptions, IngestResponse

logger = logging.getLogger(__name__)


async def ingest_new_document(
    conn,
    doc_id: str,
    title: str | None,
    source: str | None,
    text: str,
    chunking_options: ChunkingOptions,
    source_modified_at: int | None = None,
    source_url: str | None = None,
    source_filename: str | None = None,
) -> IngestResponse:
    """
    Insert document row, chunk, embed, persist. Raises ValueError if doc_id exists.
    Rolls back document row on embedding failure.
    """
    if doc_exist(conn, doc_id):
        raise ValueError("doc_id already exists")
    opts = chunking_options
    config_dict = opts.model_dump()
    insert_document(
        conn,
        doc_id,
        int(time.time()),
        title,
        source,
        source_modified_at=source_modified_at,
        source_url=source_url,
        full_text=text,
        source_filename=source_filename,
        chunking_config=config_dict,
    )
    embedder = HttpEmbedder()
    try:
        result = await index_document(conn, doc_id, text, opts, embedder=embedder)
    except Exception as e:
        delete_by_doc_id(conn, doc_id)
        logger.exception("embedding failed", exc_info=e)
        raise
    return result


async def reingest_existing_document(
    conn,
    doc_id: str,
    title: str | None,
    source: str | None,
    text: str,
    chunking_options: ChunkingOptions,
    source_modified_at: int | None = None,
    source_url: str | None = None,
    source_filename: str | None = None,
) -> IngestResponse:
    """Update stored full text/metadata and re-chunk/re-embed."""
    if not doc_exist(conn, doc_id):
        raise ValueError("doc_id not found")
    opts = chunking_options
    update_document_for_drive_reingest(
        conn,
        doc_id,
        title,
        source,
        text,
        source_modified_at,
        source_url,
        source_filename,
    )
    return await reindex_document(conn, doc_id, text, chunking_options=opts)
