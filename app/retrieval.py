"""
Retrieval: top-k chunks by similarity to the query vector.
Uses Postgres pgvector when available; retrieve_top_k_in_memory for tests/fallback.
"""

from dataclasses import dataclass
from typing import Literal

from app.models import RetrievedChunk
from app.db import get_document_source_fields, get_embeddings_for_retrieval, retrieve_top_k_pg, retrieve_top_k_lexical_pg
from app.similarity import cosine_similarity
from app.source_url import resolved_source_url


def retrieve_top_k(
    conn, query_vec, top_k, doc_id=None, embedding_model: str | None = None
) -> list[RetrievedChunk]:
    """Postgres similarity search over the shared library; returns top_k chunks as RetrievedChunk."""
    rows = retrieve_top_k_pg(conn, query_vec, top_k, doc_id, embedding_model=embedding_model)
    return [
        RetrievedChunk(
            chunk_id=chunk_id,
            doc_id=doc_id_val,
            score=score,
            content_snippet=content,
            document_title=title,
            source=src,
            source_url=resolved_source_url(src, doc_id_val, src_url),
            section_label=section_label,
        )
        for chunk_id, doc_id_val, score, content, title, src, src_url, section_label in rows
    ]


def retrieve_top_k_in_memory(
    conn, query_vec, top_k, doc_id=None, embedding_model: str | None = None
) -> list[RetrievedChunk]:
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

def resolve_auto_mode(question: str) -> Literal["vector", "lexical", "hybrid"]:
    """Pick a concrete retrieval mode for the ``auto`` request mode based on query shape.

    Conservative policy for the storm-report domain: short exact-term / identifier-style
    lookups (a quoted phrase, or <= 2 whitespace tokens, e.g. "torn shingles", WY-2024)
    route to ``lexical``; everything else routes to ``hybrid``. Pure ``vector`` is never
    returned because hybrid (RRF) subsumes it on recall, so auto stays safe by default.
    """
    text = (question or "").strip()
    if not text:
        return "hybrid"
    if '"' in text or "'" in text:
        return "lexical"
    if len(text.split()) <= 2:
        return "lexical"
    return "hybrid"


def retrieve_top_k_lexical(
    conn, query_text: str, top_k: int, doc_id: str | None = None
) -> list[RetrievedChunk]:
    """Postgres full-text (lexical) search; returns top_k chunks as RetrievedChunk.

    score is ts_rank (NOT comparable to the cosine scores from retrieve_top_k).
    """
    rows = retrieve_top_k_lexical_pg(conn, query_text, top_k, doc_id)
    return [
        RetrievedChunk(
            chunk_id=chunk_id,
            doc_id=doc_id_val,
            score=score,
            content_snippet=content,
            document_title=title,
            source=src,
            source_url=resolved_source_url(src, doc_id_val, src_url),
            section_label=section_label,
        )
        for chunk_id, doc_id_val, score, content, title, src, src_url, section_label in rows
    ]

@dataclass
class FusedHit:
    """One fused result plus the component scores that produced it.

    ``chunk.score`` holds the RRF score (same value as ``rrf_score``).
    ``cosine_score``/``lexical_score`` are ``None`` when that retriever did not
    surface the chunk (vector-only or lexical-only hit) — never coerced to 0.0,
    so downstream metrics can distinguish "absent" from "scored zero".
    """

    chunk: RetrievedChunk
    rrf_score: float
    cosine_score: float | None = None
    lexical_score: float | None = None
    vector_rank: int | None = None
    lexical_rank: int | None = None


def _rrf_fuse(
    vector_hits: list[RetrievedChunk],
    lexical_hits: list[RetrievedChunk],
    top_k: int,
    k: int = 60,
) -> list[FusedHit]:
    """Reciprocal Rank Fusion of the vector and lexical lists, keyed by chunk_id.

    Each list contributes 1 / (k + rank) (rank is 1-based) to a chunk's RRF score.
    Component scores are retained: cosine from the vector list, ts_rank from the
    lexical list. A chunk present in only one list keeps the other as None.
    The returned chunk's ``score`` is the RRF score, not cosine/ts_rank.
    """
    rrf_scores: dict[str, float] = {}
    cosine_scores: dict[str, float] = {}
    lexical_scores: dict[str, float] = {}
    vector_ranks: dict[str, int] = {}
    lexical_ranks: dict[str, int] = {}
    chunk_by_id: dict[str, RetrievedChunk] = {}

    for rank, hit in enumerate(vector_hits, start=1):
        rrf_scores[hit.chunk_id] = rrf_scores.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
        cosine_scores[hit.chunk_id] = hit.score
        vector_ranks[hit.chunk_id] = rank
        chunk_by_id.setdefault(hit.chunk_id, hit)

    for rank, hit in enumerate(lexical_hits, start=1):
        rrf_scores[hit.chunk_id] = rrf_scores.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
        lexical_scores[hit.chunk_id] = hit.score
        lexical_ranks[hit.chunk_id] = rank
        chunk_by_id.setdefault(hit.chunk_id, hit)

    ranked = sorted(rrf_scores.items(), key=lambda kv: kv[1], reverse=True)
    out: list[FusedHit] = []
    for chunk_id, rrf_score in ranked[:top_k]:
        out.append(
            FusedHit(
                chunk=chunk_by_id[chunk_id].model_copy(update={"score": rrf_score}),
                rrf_score=rrf_score,
                cosine_score=cosine_scores.get(chunk_id),
                lexical_score=lexical_scores.get(chunk_id),
                vector_rank=vector_ranks.get(chunk_id),
                lexical_rank=lexical_ranks.get(chunk_id),
            )
        )
    return out


def retrieve_top_k_hybrid(
    conn,
    query_vec,
    query_text: str,
    top_k: int,
    doc_id: str | None = None,
    embedding_model: str | None = None,
    candidate_k: int | None = None,
    rrf_k: int = 60,
) -> list[FusedHit]:
    """Hybrid retrieval: fuse vector + lexical results with RRF, return top_k FusedHits.

    Pulls a larger candidate pool from each retriever (``candidate_k``) so the
    fusion has room to rerank, then trims to ``top_k``. Each FusedHit carries the
    RRF score plus the cosine/ts_rank components for metrics and debugging.
    """
    pool = candidate_k or max(top_k * 4, 20)
    vector_hits = retrieve_top_k(conn, query_vec, pool, doc_id, embedding_model=embedding_model)
    lexical_hits = retrieve_top_k_lexical(conn, query_text, pool, doc_id)
    return _rrf_fuse(vector_hits, lexical_hits, top_k, k=rrf_k)