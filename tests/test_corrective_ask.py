"""Corrective rewrite-once path on /ask (mocked retrieve + LLM)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.corrective import SOFT_REFUSE_CANARY
from app.main import _run_ask_rag_with_corrective
from app.models import AskRequest, RetrievedChunk


def _chunk(doc_id: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"{doc_id}-0",
        doc_id=doc_id,
        score=0.9,
        content_snippet=text,
        document_title=doc_id,
        source="demo",
    )


def test_soft_refuse_triggers_rewrite_and_second_retrieve():
    q = "Which tile-roof properties had intact roof tiles and no storm-created opening?"
    first = [_chunk("wrong", "Wind created a storm-created opening in the shingles.")]
    second = [
        _chunk(
            "412_example_drive_samplecity",
            "The roof tiles were intact. No storm-created opening was identified.",
        )
    ]
    rate_limiter = MagicMock()
    rate_limiter.acquire = AsyncMock()
    embedder = MagicMock()
    embedder.model = "test-embed"
    embedder.embed_many = AsyncMock(side_effect=[[[0.1, 0.2]], [[0.3, 0.4]]])

    llm_answers = [SOFT_REFUSE_CANARY, "412 Example Drive had intact roof tiles."]

    async def fake_retrieve(conn, ask_request, query_vec, embedding_model, rag_endpoint, reranker):
        if ask_request.question == q:
            return first
        return second

    async def _run():
        with (
            patch("app.main._retrieve_for_ask", new=AsyncMock(side_effect=fake_retrieve)),
            patch("app.main.llm_client.answer_with_context", new=AsyncMock(side_effect=llm_answers)),
            patch(
                "app.main.rag_phase_span",
                return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()),
            ),
            patch("app.main.record_rag_phase_seconds"),
            patch("app.main.record_no_context_response"),
            patch("app.main.set_refused_attribute"),
            patch("app.main.trace.get_current_span", return_value=MagicMock()),
        ):
            return await _run_ask_rag_with_corrective(
                MagicMock(),
                AskRequest(question=q, top_k=5),
                embedder=embedder,
                rag_endpoint="sync",
                reranker=None,
                rate_limiter=rate_limiter,
            )

    result = asyncio.run(_run())

    assert result.retrieval_debug is not None
    assert result.retrieval_debug.retried is True
    assert "intact roof tiles" in result.retrieval_debug.rewritten_query.lower()
    assert result.top_chunks[0].doc_id == "412_example_drive_samplecity"
    assert "intact roof tiles" in result.answer.lower()
    assert rate_limiter.acquire.await_count == 2
    assert embedder.embed_many.await_count == 2


def test_non_refuse_skips_rewrite():
    q = "What causes shingle damage?"
    chunks = [_chunk("doc", "Hail damaged the shingles.")]
    rate_limiter = MagicMock()
    rate_limiter.acquire = AsyncMock()
    embedder = MagicMock()
    embedder.model = "test-embed"
    embedder.embed_many = AsyncMock(return_value=[[0.1]])

    async def _run():
        with (
            patch("app.main._retrieve_for_ask", new=AsyncMock(return_value=chunks)),
            patch(
                "app.main.llm_client.answer_with_context",
                new=AsyncMock(return_value="Hail damaged the shingles."),
            ),
            patch(
                "app.main.rag_phase_span",
                return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()),
            ),
            patch("app.main.record_rag_phase_seconds"),
            patch("app.main.trace.get_current_span", return_value=MagicMock()),
        ):
            return await _run_ask_rag_with_corrective(
                MagicMock(),
                AskRequest(question=q, top_k=5),
                embedder=embedder,
                rag_endpoint="sync",
                reranker=None,
                rate_limiter=rate_limiter,
            )

    result = asyncio.run(_run())

    assert result.retrieval_debug is None
    assert rate_limiter.acquire.await_count == 1
    assert embedder.embed_many.await_count == 1
