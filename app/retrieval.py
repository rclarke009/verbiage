"""
Retrieval: top-k chunks by similarity to the query vector.
Uses Postgres pgvector when available; retrieve_top_k_in_memory for tests/fallback.
"""

from app.models import RetrievedChunk
from app.db import get_document_source_fields, get_embeddings_for_retrieval, retrieve_top_k_pg
from app.similarity import cosine_similarity
from app.source_url import resolved_source_url


def retrieve_top_k(
    conn, query_vec, top_k, doc_id=None, user_id=None
) -> list[RetrievedChunk]:
    """Postgres similarity search; returns top_k chunks as RetrievedChunk. If user_id is set, only that user's documents are searched."""
    rows = retrieve_top_k_pg(conn, query_vec, top_k, doc_id, user_id)
    return [
        RetrievedChunk(
            chunk_id=chunk_id,
            doc_id=doc_id_val,
            score=score,
            content_snippet=content,
            document_title=title,
            source=src,
            source_url=resolved_source_url(src, doc_id_val, src_url),
        )
        for chunk_id, doc_id_val, score, content, title, src, src_url in rows
    ]


def retrieve_top_k_in_memory(conn, query_vec, top_k, doc_id=None) -> list[RetrievedChunk]:
    """In-memory similarity (get_embeddings + cosine_similarity). For tests/fallback."""
    all_candidates = get_embeddings_for_retrieval(conn, doc_id)
    candidates = all_candidates[:5000]
    scored: list[tuple[float, str, str, str]] = []
    for chunk_id, doc_id_val, vector, content in candidates:
        score = cosine_similarity(query_vec, vector)
        scored.append((score, chunk_id, doc_id_val, content))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]
    if not top:
        return []
    unique_ids = list({t[2] for t in top})
    meta = get_document_source_fields(conn, unique_ids)
    out: list[RetrievedChunk] = []
    for score, chunk_id, doc_id_val, content in top:
        title, src, src_url = meta.get(doc_id_val, (None, None, None))
        out.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                doc_id=doc_id_val,
                score=score,
                content_snippet=content,
                document_title=title,
                source=src,
                source_url=resolved_source_url(src, doc_id_val, src_url),
            )
        )
    return out
