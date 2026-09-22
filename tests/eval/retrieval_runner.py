"""Run production retrieval for each gold question (no LLM generation).

Mirrors the /ask retrieve path:
    normalize_retrieval_query -> embed (cached) -> _retrieve_for_ask
with an explicit ``candidate_k`` so the first-pass pool is production-rerank width
even when the cross-encoder is not loaded.

nearby_storm questions use the structured geo path; there is no RRF pool to widen.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.ask_router import resolve_ask_route, retrieve_nearby_storm_chunks
from app.main import _retrieve_for_ask
from app.models import AskRequest, ClaimContext
from app.retrieval import normalize_retrieval_query

try:
    from .embedding_cache import CachedEmbedder
    from .retrieval_metrics import hit_at, mrr, recall_at, unique_doc_ids
    from .runner import load_gold_questions
except ImportError:  # pragma: no cover - pytest path-based import
    from embedding_cache import CachedEmbedder
    from retrieval_metrics import hit_at, mrr, recall_at, unique_doc_ids
    from runner import load_gold_questions

DEFAULT_TOP_K = 3
POOL_K = max(DEFAULT_TOP_K * 4, 20)
ABLATION_MODES = ("auto", "vector", "lexical", "hybrid")


@dataclass
class RetrievalResult:
    question_id: str
    category: str
    route: str
    requested_mode: str
    resolved_mode: str
    relevant_doc_ids: list[str]
    pool_doc_ids: list[str]
    prompt_doc_ids: list[str]
    recall_pool: float | None
    recall_k: float | None
    hit_k: float | None
    mrr: float | None
    gate_blocked: bool = False
    n_docs: int = 0
    n_chunks: int = 0
    pool_chunk_ids: list[str] = field(default_factory=list)


def corpus_stats(conn) -> tuple[int, int]:
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM documents")
        n_docs = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM chunks")
        n_chunks = int(cur.fetchone()[0])
        return n_docs, n_chunks
    finally:
        cur.close()


def _ask_request(q: dict, *, retrieval_mode: str, top_k: int = DEFAULT_TOP_K) -> AskRequest:
    claim_ctx_raw = q.get("claim_context")
    claim_context = ClaimContext(**claim_ctx_raw) if claim_ctx_raw else None
    return AskRequest(
        question=q["question"],
        query_mode=q.get("query_mode", "auto"),
        retrieval_mode=retrieval_mode,  # type: ignore[arg-type]
        claim_context=claim_context,
        top_k=top_k,
    )


def _score(
    *,
    q: dict,
    route: str,
    requested_mode: str,
    resolved_mode: str,
    pool_chunks,
    prompt_chunks,
    gate_blocked: bool,
    n_docs: int,
    n_chunks: int,
) -> RetrievalResult:
    relevant = list(q.get("relevant_doc_ids") or [])
    pool_ids = unique_doc_ids(pool_chunks)
    prompt_ids = unique_doc_ids(prompt_chunks)
    return RetrievalResult(
        question_id=q["id"],
        category=q["category"],
        route=route,
        requested_mode=requested_mode,
        resolved_mode=resolved_mode,
        relevant_doc_ids=relevant,
        pool_doc_ids=pool_ids,
        prompt_doc_ids=prompt_ids,
        recall_pool=recall_at(pool_ids, relevant),
        recall_k=recall_at(prompt_ids, relevant),
        hit_k=hit_at(prompt_ids, relevant),
        mrr=mrr(prompt_ids, relevant),
        gate_blocked=gate_blocked,
        n_docs=n_docs,
        n_chunks=n_chunks,
        pool_chunk_ids=[c.chunk_id for c in pool_chunks],
    )


async def run_retrieval(
    conn,
    q: dict,
    *,
    retrieval_mode: str = "auto",
    embedder: CachedEmbedder | None = None,
    reranker=None,
    candidate_k: int | None = POOL_K,
    top_k: int = DEFAULT_TOP_K,
) -> RetrievalResult:
    embedder = embedder or CachedEmbedder()
    n_docs, n_chunks = corpus_stats(conn)
    req = _ask_request(q, retrieval_mode=retrieval_mode, top_k=top_k)

    route = resolve_ask_route(req.question, req.query_mode, req.claim_context)
    if route == "nearby_storm":
        answer, top_chunks = await retrieve_nearby_storm_chunks(conn, req)
        chunks = top_chunks if answer is not None else []
        return _score(
            q=q,
            route="nearby_storm",
            requested_mode="nearby_storm",
            resolved_mode="nearby_storm",
            pool_chunks=chunks,
            prompt_chunks=chunks,
            gate_blocked=False,
            n_docs=n_docs,
            n_chunks=n_chunks,
        )

    retrieval_q = normalize_retrieval_query(req.question)
    retrieval_req = req.model_copy(update={"question": retrieval_q})
    vec = (await embedder.embed_many([retrieval_q]))[0]
    outcome = await _retrieve_for_ask(
        conn,
        retrieval_req,
        vec,
        embedder.model,
        "eval",
        reranker,
        candidate_k=candidate_k,
    )
    return _score(
        q=q,
        route="rag",
        requested_mode=retrieval_mode,
        resolved_mode=outcome.retrieval_mode,
        pool_chunks=outcome.pool_chunks,
        prompt_chunks=outcome.chunks,
        gate_blocked=outcome.gate_blocked,
        n_docs=n_docs,
        n_chunks=n_chunks,
    )


def run_retrieval_sync(conn, q: dict, **kwargs) -> RetrievalResult:
    return asyncio.run(run_retrieval(conn, q, **kwargs))


def answerable_questions() -> list[dict]:
    return [q for q in load_gold_questions() if q["category"] != "unanswerable"]


def rag_answerable_questions() -> list[dict]:
    return [
        q
        for q in answerable_questions()
        if q.get("query_mode", "auto") != "nearby_storm"
    ]
