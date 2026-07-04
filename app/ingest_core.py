"""Shared ingest helpers used by sync endpoints and the background worker."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

from app.db import delete_by_doc_id, doc_exist, get_valid_conn, insert_document, update_document_for_drive_reingest
from app.embeddings import HttpEmbedder
from app.indexing import index_document, index_document_pooled, reindex_document, reindex_document_pooled
from app.models import ChunkingOptions, IngestResponse

logger = logging.getLogger(__name__)


async def _run_db(pool, fn: Callable[..., Any], *args, commit: bool = True, **kwargs) -> Any:
    """Run sync psycopg2 work off the asyncio event loop."""

    def _work() -> Any:
        conn = get_valid_conn(pool)
        try:
            result = fn(conn, *args, **kwargs)
            if commit:
                conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            pool.putconn(conn)

    return await asyncio.to_thread(_work)


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


async def ingest_new_document_pooled(
    pool,
    doc_id: str,
    title: str | None,
    source: str | None,
    text: str,
    chunking_options: ChunkingOptions,
    source_modified_at: int | None = None,
    source_url: str | None = None,
    source_filename: str | None = None,
) -> IngestResponse:
    """Worker ingest: returns DB connections to the pool before embedding."""
    opts = chunking_options

    def _insert(conn) -> None:
        if doc_exist(conn, doc_id):
            raise ValueError("doc_id already exists")
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
            chunking_config=opts.model_dump(),
        )

    await _run_db(pool, _insert)

    embedder = HttpEmbedder()
    try:
        return await index_document_pooled(pool, doc_id, text, opts, embedder=embedder)
    except Exception as e:
        await _run_db(pool, lambda conn: delete_by_doc_id(conn, doc_id))
        logger.exception("embedding failed", exc_info=e)
        raise


async def reingest_existing_document_pooled(
    pool,
    doc_id: str,
    title: str | None,
    source: str | None,
    text: str,
    chunking_options: ChunkingOptions,
    source_modified_at: int | None = None,
    source_url: str | None = None,
    source_filename: str | None = None,
) -> IngestResponse:
    """Worker reingest: returns DB connections to the pool before embedding."""
    opts = chunking_options

    def _update(conn) -> None:
        if not doc_exist(conn, doc_id):
            raise ValueError("doc_id not found")
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

    await _run_db(pool, _update)
    return await reindex_document_pooled(pool, doc_id, text, chunking_options=opts)
