"""Opt-in integration check for lexical / vector / hybrid retrieval against the live DB.

Skipped by default. To run against your real ingested corpus:

    VERBIAGE_INTEGRATION=1 .venv/bin/python -m pytest tests/test_retrieval_integration.py -s

Requires DATABASE_URL (loaded via app.config) and the content_tsv migration applied.
Vector/hybrid assertions additionally need a working embedding backend; they skip
(rather than fail) if the embed API is unavailable.
"""

import asyncio
import os

import psycopg2
import pytest
from pgvector.psycopg2 import register_vector

from app.config import DATABASE_CONNECTION_KWARGS, DATABASE_URL
from app.embeddings import HttpEmbedder
from app.retrieval import (
    FusedHit,
    resolve_auto_mode,
    retrieve_top_k,
    retrieve_top_k_hybrid,
    retrieve_top_k_lexical,
)

pytestmark = pytest.mark.skipif(
    os.getenv("VERBIAGE_INTEGRATION") != "1" or not DATABASE_URL,
    reason="integration test: set VERBIAGE_INTEGRATION=1 (and DATABASE_URL) to run",
)

TOP_K = 5


@pytest.fixture(scope="module")
def conn():
    if DATABASE_CONNECTION_KWARGS:
        c = psycopg2.connect(**DATABASE_CONNECTION_KWARGS)
    else:
        c = psycopg2.connect(DATABASE_URL)
    register_vector(c)
    yield c
    c.close()


@pytest.fixture(scope="module")
def corpus_term(conn):
    """A real word from the corpus so lexical search is guaranteed at least one match."""
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM chunks")
    if cur.fetchone()[0] == 0:
        pytest.skip("no chunks ingested")
    cur.execute("SELECT content_tsv IS NOT NULL FROM chunks LIMIT 1")
    if not cur.fetchone()[0]:
        pytest.skip("content_tsv not populated (migration not applied?)")
    cur.execute("SELECT content FROM chunks WHERE length(content) > 100 LIMIT 1")
    content = cur.fetchone()[0]
    cur.close()
    for word in content.split():
        w = "".join(ch for ch in word if ch.isalpha())
        if len(w) >= 6:
            return w
    return "report"


@pytest.fixture(scope="module")
def query_vec():
    """Embed a query, or skip the whole vector/hybrid path if the embed backend is down."""
    embedder = HttpEmbedder()
    try:
        vec = asyncio.run(embedder.embed_many(["roof damage assessment"]))[0]
    except Exception as e:  # invalid key, network, etc.
        pytest.skip(f"embedding backend unavailable: {str(e)[:120]}")
    return embedder.model, vec


def test_lexical_returns_ranked_chunks(conn, corpus_term):
    results = retrieve_top_k_lexical(conn, corpus_term, TOP_K)
    print(f"\nMYDEBUG -> lexical term={corpus_term!r} -> {len(results)} hits")
    for r in results:
        print(f"   {r.score:.5f}  {(r.document_title or r.doc_id)[:50]}")

    assert len(results) >= 1
    assert all(r.content_snippet for r in results)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_hybrid_fuses_and_preserves_components(conn, query_vec):
    model, vec = query_vec
    query = "roof damage assessment"

    vector = retrieve_top_k(conn, vec, TOP_K, embedding_model=model)
    lexical = retrieve_top_k_lexical(conn, query, TOP_K)
    fused = retrieve_top_k_hybrid(conn, vec, query, TOP_K, embedding_model=model)

    print(f"\nMYDEBUG -> vector={len(vector)} lexical={len(lexical)} fused={len(fused)}")
    for h in fused:
        cos = f"{h.cosine_score:.4f}" if h.cosine_score is not None else "  -   "
        lex = f"{h.lexical_score:.4f}" if h.lexical_score is not None else "  -   "
        print(f"   rrf={h.rrf_score:.5f} cos={cos} lex={lex} "
              f"vr={h.vector_rank} lr={h.lexical_rank} | {(h.chunk.document_title or h.chunk.doc_id)[:40]}")

    if not vector and not lexical:
        pytest.skip("query matched nothing in this corpus")

    assert all(isinstance(h, FusedHit) for h in fused)
    rrf_scores = [h.rrf_score for h in fused]
    assert rrf_scores == sorted(rrf_scores, reverse=True)

    union_ids = {c.chunk_id for c in vector} | {c.chunk_id for c in lexical}
    for h in fused:
        assert h.chunk.chunk_id in union_ids
        assert h.chunk.score == h.rrf_score  # score field carries the RRF score
        # component presence must line up with which list produced the hit
        assert (h.cosine_score is None) == (h.vector_rank is None)
        assert (h.lexical_score is None) == (h.lexical_rank is None)
        assert h.cosine_score is not None or h.lexical_score is not None


# --- Retrieval-quality eval: real questions, auto routing, content check ---
#
# Each case is (question, expected_substrings). resolve_auto_mode picks the
# mode, the routed retriever runs against the live corpus, and we assert that
# at least one expected term shows up in the returned snippets. Tune the
# expected_substrings to whatever your ingested corpus actually contains --
# they're the "right answer" signal for the quality angle.
EVAL_QUESTIONS = [
    ("which report had the hail damage in wyoming", ["wyoming"]),
    ("give me 3 text chunks about torn shingles", ["shingle"]),
    ("Please provide text about water damage due to storm created opening", ["water"]),
]


@pytest.fixture(scope="module")
def embedder():
    """Shared embedder; skips the eval if the embed backend is unavailable."""
    emb = HttpEmbedder()
    try:
        asyncio.run(emb.embed_many(["probe"]))
    except Exception as e:  # invalid key, network, etc.
        pytest.skip(f"embedding backend unavailable: {str(e)[:120]}")
    return emb


@pytest.mark.parametrize("question, expected_substrings", EVAL_QUESTIONS)
def test_auto_routing_retrieval_quality(conn, embedder, question, expected_substrings):
    mode = resolve_auto_mode(question)

    if mode == "lexical":
        chunks = retrieve_top_k_lexical(conn, question, TOP_K)
    else:  # "hybrid" or "vector" -- both need the query embedding
        vec = asyncio.run(embedder.embed_many([question]))[0]
        if mode == "vector":
            chunks = retrieve_top_k(conn, vec, TOP_K, embedding_model=embedder.model)
        else:
            fused = retrieve_top_k_hybrid(conn, vec, question, TOP_K, embedding_model=embedder.model)
            chunks = [h.chunk for h in fused]

    print(f"\nMYDEBUG -> mode={mode} q={question!r} -> {len(chunks)} hits")
    for c in chunks:
        print(f"   {c.score:.5f}  {(c.document_title or c.doc_id)[:50]} | {c.content_snippet[:80]!r}")

    assert len(chunks) <= TOP_K
    if not chunks:
        pytest.skip(f"query matched nothing in this corpus: {question!r}")

    blob = " ".join(c.content_snippet.lower() for c in chunks)
    for sub in expected_substrings:
        assert sub.lower() in blob, f"expected {sub!r} in retrieved snippets for {question!r}"
