"""Graph node: hybrid RAG retrieval."""

from __future__ import annotations

from app.db import get_valid_conn
from app.embeddings import HttpEmbedder
from app.report_writer.deps import get_report_writer_deps
from app.report_writer.queries import chunks_to_dicts
from app.report_writer.retrieval import retrieve_similar_chunks
from app.report_writer.state import ReportWriterState


async def retrieve_similar(state: ReportWriterState) -> dict:
    deps = get_report_writer_deps()
    query = state.get("retrieval_query") or ""
    embedder = HttpEmbedder()
    query_vectors = await embedder.embed_many([query])
    query_vec = query_vectors[0]

    conn = get_valid_conn(deps.db_pool)
    try:
        chunks, best_cosine = await retrieve_similar_chunks(
            conn,
            query,
            query_vec=query_vec,
            embedding_model=embedder.model,
            reranker=deps.reranker,
        )
    finally:
        deps.db_pool.putconn(conn)

    return {
        "retrieved_chunks": chunks_to_dicts(chunks),
        "best_cosine": best_cosine,
    }
