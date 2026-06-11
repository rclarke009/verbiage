"""
Document indexing: chunk stored text, embed, and persist vectors.
Used by ingest and reindex flows.
"""

from __future__ import annotations

import asyncio
import logging

from app.breadcrumb import apply_document_breadcrumb, build_document_breadcrumb_prefix
from app.chunking import chunk_text
from app.db import (
    delete_chunks_for_doc,
    get_document_breadcrumb_fields,
    insert_chunk,
    insert_embedding,
    update_document_indexing_metadata,
)
from app.embedding_usage_estimate import embedding_metering
from app.embeddings import HttpEmbedder
from app.models import ChunkingOptions, IngestResponse

logger = logging.getLogger(__name__)


def _chunk_and_insert(conn, doc_id: str, text: str, opts: ChunkingOptions):
    """CPU-bound chunking + sync chunk inserts; run via asyncio.to_thread."""
    delete_chunks_for_doc(conn, doc_id)
    chunks = chunk_text(text, opts)
    title, source, source_filename = get_document_breadcrumb_fields(conn, doc_id)
    prefix = build_document_breadcrumb_prefix(
        doc_id=doc_id,
        title=title,
        source=source,
        source_filename=source_filename,
    )
    chunks = apply_document_breadcrumb(chunks, prefix)
    for chunk in chunks:
        chunk_id = f"{doc_id}:{chunk.chunk_index}"
        insert_chunk(
            conn,
            chunk_id,
            doc_id,
            chunk.chunk_index,
            chunk.content,
            chunk.start_offset,
            chunk.end_offset,
            section_label=chunk.section_label,
        )
    return chunks


async def index_document(
    conn,
    doc_id: str,
    text: str,
    chunking_options: ChunkingOptions,
    embedder: HttpEmbedder | None = None,
) -> IngestResponse:
    """
    Chunk text, embed, and store chunks + embeddings for an existing document row.
    Replaces any prior chunks/embeddings for doc_id.
    """
    embedder = embedder or HttpEmbedder()
    opts = chunking_options
    chunks = await asyncio.to_thread(_chunk_and_insert, conn, doc_id, text, opts)

    try:
        vectors = await embedder.embed_many([c.content for c in chunks])
    except Exception:
        delete_chunks_for_doc(conn, doc_id)
        raise

    for chunk, vector in zip(chunks, vectors):
        chunk_id = f"{doc_id}:{chunk.chunk_index}"
        insert_embedding(conn, chunk_id, embedder.model, vector, embedder.dim)

    config_dict = opts.model_dump()
    update_document_indexing_metadata(conn, doc_id, config_dict, embedder.model)

    chars_total, toks_estimate = embedding_metering([c.content for c in chunks])
    return IngestResponse(
        doc_id=doc_id,
        num_chunks=len(chunks),
        embedding_model=embedder.model,
        dim=embedder.dim,
        embedding_chars_total=chars_total,
        embedding_tokens_estimate=toks_estimate,
    )


async def reindex_document(
    conn,
    doc_id: str,
    full_text: str,
    chunking_options: ChunkingOptions | None = None,
    embedder: HttpEmbedder | None = None,
) -> IngestResponse:
    """Re-chunk and re-embed from stored full_text without re-upload."""
    opts = chunking_options or ChunkingOptions()
    return await index_document(conn, doc_id, full_text, opts, embedder=embedder)
