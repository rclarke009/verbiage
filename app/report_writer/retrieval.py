"""Hybrid retrieval for Report Writer (gate applied separately in graph)."""

from __future__ import annotations

import asyncio

from app.models import AskRequest, RetrievedChunk
from app.retrieval import (
    FusedHit,
    lexical_query_text,
    resolve_auto_mode,
    retrieve_top_k,
    retrieve_top_k_hybrid,
    retrieve_top_k_lexical,
)


async def _rerank_chunks(
    question: str,
    chunks: list[RetrievedChunk],
    top_k: int,
    reranker,
) -> list[RetrievedChunk]:
    if not chunks:
        return []
    if reranker is None or len(chunks) <= 1:
        return chunks[:top_k]
    payload = [{"content": c.content_snippet, "_chunk": c} for c in chunks]
    ranked = await asyncio.to_thread(reranker.rerank, question, payload, top_k)
    return [d["_chunk"] for d in ranked]


async def retrieve_similar_chunks(
    conn,
    query: str,
    *,
    query_vec: list[float],
    embedding_model: str | None,
    reranker,
    top_k: int = 8,
) -> tuple[list[RetrievedChunk], float | None]:
    """Retrieve candidates; return (chunks, best_cosine) for the gate node."""
    pool_k = max(top_k * 4, 20) if reranker is not None else top_k
    best_cosine: float | None = None

    def _hybrid() -> tuple[list[RetrievedChunk], float | None]:
        nonlocal best_cosine
        fused: list[FusedHit] = retrieve_top_k_hybrid(
            conn, query_vec, query, pool_k, None, embedding_model=embedding_model,
        )
        cosines = [h.cosine_score for h in fused if h.cosine_score is not None]
        best_cosine = max(cosines) if cosines else None
        return [h.chunk for h in fused], best_cosine

    def _run_retrieval() -> tuple[list[RetrievedChunk], float | None]:
        mode = resolve_auto_mode(query)
        if mode == "hybrid":
            return _hybrid()
        if mode == "lexical":
            candidates = retrieve_top_k_lexical(conn, lexical_query_text(query), pool_k, None)
            if not candidates:
                return _hybrid()
            return candidates, None
        candidates = retrieve_top_k(conn, query_vec, pool_k, None, embedding_model=embedding_model)
        scores = [c.score for c in candidates]
        return candidates, (max(scores) if scores else None)

    candidates, best_cosine = await asyncio.to_thread(_run_retrieval)
    ranked = await _rerank_chunks(query, candidates, top_k, reranker)
    return ranked, best_cosine
