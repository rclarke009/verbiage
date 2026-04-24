"""
Postgres + pgvector DB layer. create_db runs DDL; helpers use psycopg2 connections.
For in-memory similarity (tests/fallback), use get_embeddings_for_retrieval + similarity.cosine_similarity.

Supabase transaction-mode pooler (port 6543) does not support prepared statements; use
connection_factory=NoPrepareConnection when creating the pool for such URLs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import psycopg2
from psycopg2 import extensions
from pgvector.psycopg2 import register_vector

if TYPE_CHECKING:
    from psycopg2.extensions import connection as PgConnection


class _NoPrepareCursor(extensions.cursor):
    """Cursor that never uses prepared statements (required for Supabase transaction-mode pooler, port 6543)."""
    prepare_threshold = None


class NoPrepareConnection(extensions.connection):
    """Connection whose cursors do not use prepared statements. Use for Supabase pooler port 6543."""
    cursor_factory = _NoPrepareCursor


def is_connection_error(exc: BaseException) -> bool:
    """True if the exception indicates a closed or broken DB connection (retry-safe)."""
    if not isinstance(exc, psycopg2.DatabaseError):
        return False
    msg = str(exc).lower()
    return "connection" in msg and ("closed" in msg or "terminated" in msg or "unexpectedly" in msg)


def get_valid_conn(pool: Any) -> "PgConnection":
    """
    Get a connection from the pool and validate it with SELECT 1.
    If validation fails (e.g. server closed the connection), discard that connection
    and try one more time. Caller must putconn(conn) when done.
    """
    conn = pool.getconn()
    for attempt in range(2):
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            return conn
        except psycopg2.DatabaseError:
            pool.putconn(conn, close=True)
            if attempt == 1:
                raise
            conn = pool.getconn()
    return conn  # unreachable


def _ensure_pgvector(conn: PgConnection) -> None:
    """Register pgvector type on this connection (idempotent for same conn)."""
    register_vector(conn)


def create_db(conn: PgConnection) -> None:
    """Run Postgres DDL: extension, documents/chunks/embeddings tables, indexes."""
    cur = conn.cursor()
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
    finally:
        cur.close()
    _ensure_pgvector(conn)
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                title TEXT,
                source TEXT,
                created_at BIGINT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                content TEXT,
                start_offset INTEGER,
                end_offset INTEGER
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                chunk_id TEXT PRIMARY KEY REFERENCES chunks(chunk_id) ON DELETE CASCADE,
                model TEXT,
                embedding vector(768),
                dim INTEGER
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_chunks_doc_id_chunk_index ON chunks(doc_id, chunk_index);"
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_model ON embeddings(model);")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_embeddings_embedding_hnsw
            ON embeddings USING hnsw (embedding vector_cosine_ops);
        """)
        # Add user_id for Supabase Auth (per-user documents); idempotent for existing DBs
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'documents' AND column_name = 'user_id'
                ) THEN
                    ALTER TABLE documents ADD COLUMN user_id TEXT;
                END IF;
            END $$;
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);")
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'documents'
                      AND column_name = 'source_modified_at'
                ) THEN
                    ALTER TABLE documents ADD COLUMN source_modified_at BIGINT;
                END IF;
            END $$;
        """)
        conn.commit()
    finally:
        cur.close()


def insert_document(
    conn: PgConnection,
    doc_id: str,
    created_at: int,
    title: str | None = None,
    source: str | None = None,
    user_id: str | None = None,
    source_modified_at: int | None = None,
) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO documents(doc_id, title, source, created_at, user_id, source_modified_at) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (doc_id, title, source, created_at, user_id, source_modified_at),
        )
    finally:
        cur.close()


def insert_chunk(
    conn: PgConnection,
    chunk_id: str,
    doc_id: str,
    chunk_index: int,
    content: str,
    start_offset: int,
    end_offset: int,
) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO chunks(chunk_id, doc_id, chunk_index, content, start_offset, end_offset) VALUES (%s,%s,%s,%s,%s,%s)",
            (chunk_id, doc_id, chunk_index, content, start_offset, end_offset),
        )
    finally:
        cur.close()


def insert_embedding(
    conn: PgConnection,
    chunk_id: str,
    model: str,
    embedding: list[float],
    dim: int,
) -> None:
    _ensure_pgvector(conn)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO embeddings(chunk_id, model, embedding, dim) VALUES (%s,%s,%s,%s)",
            (chunk_id, model, embedding, dim),
        )
    finally:
        cur.close()


def doc_exist(conn: PgConnection, doc_id: str) -> bool:
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM documents WHERE doc_id = %s", (doc_id,))
        return cur.fetchone() is not None
    finally:
        cur.close()


def get_embeddings_for_retrieval(
    conn: PgConnection, doc_id: str | None = None
) -> list[tuple[str, str, list[float], str]]:
    """Fetch (chunk_id, doc_id, vector, content) for in-memory similarity (tests/fallback)."""
    _ensure_pgvector(conn)
    sql = """
        SELECT e.chunk_id, c.doc_id, e.embedding, c.content
        FROM embeddings e
        JOIN chunks c ON e.chunk_id = c.chunk_id
    """
    cur = conn.cursor()
    try:
        if doc_id is not None:
            cur.execute(sql + " WHERE c.doc_id = %s", (doc_id,))
        else:
            cur.execute(sql)
        rows = cur.fetchall()
        return [(r[0], r[1], list(r[2]), r[3]) for r in rows]
    finally:
        cur.close()


def retrieve_top_k_pg(
    conn: PgConnection,
    query_vec: list[float],
    top_k: int,
    doc_id: str | None = None,
    user_id: str | None = None,
) -> list[tuple[str, str, float, str]]:
    """Postgres similarity search. Returns (chunk_id, doc_id, score, content). Uses <=> (cosine distance); 1 - distance = similarity. If user_id is set, only chunks from that user's documents are considered."""
    _ensure_pgvector(conn)
    sql = """
        SELECT c.chunk_id, c.doc_id, 1 - (e.embedding <=> %s::vector) AS score, c.content
        FROM embeddings e
        JOIN chunks c ON e.chunk_id = c.chunk_id
    """
    conditions: list[str] = []
    params: list[Any] = [query_vec]
    if user_id is not None:
        sql = """
        SELECT c.chunk_id, c.doc_id, 1 - (e.embedding <=> %s::vector) AS score, c.content
        FROM embeddings e
        JOIN chunks c ON e.chunk_id = c.chunk_id
        JOIN documents d ON d.doc_id = c.doc_id
        """
        conditions.append("d.user_id = %s")
        params.append(user_id)
    if doc_id is not None:
        conditions.append("c.doc_id = %s")
        params.append(doc_id)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY e.embedding <=> %s::vector LIMIT %s"
    params.extend([query_vec, top_k])
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()


def delete_by_doc_id(conn: PgConnection, doc_id: str) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM embeddings WHERE chunk_id IN (SELECT chunk_id FROM chunks WHERE doc_id = %s)",
            (doc_id,),
        )
        cur.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
        cur.execute("DELETE FROM documents WHERE doc_id = %s", (doc_id,))
        conn.commit()
    finally:
        cur.close()


def list_documents(
    conn: PgConnection,
    snippet_max_len: int = 250,
    user_id: str | None = None,
) -> list[tuple[str, str | None, str | None, int, int, str | None, int | None]]:
    """
    Returns list of (doc_id, title, source, created_at, num_chunks, snippet, source_modified_at).
    Ordered by created_at desc. If user_id is set, only that user's documents are returned.
    """
    sql = """
        SELECT
            d.doc_id,
            d.title,
            d.source,
            d.created_at,
            (SELECT COUNT(*) FROM chunks c WHERE c.doc_id = d.doc_id) AS num_chunks,
            (SELECT c.content FROM chunks c WHERE c.doc_id = d.doc_id ORDER BY c.chunk_index LIMIT 1) AS first_content,
            d.source_modified_at
        FROM documents d
    """
    params: list[Any] = []
    if user_id is not None:
        sql += " WHERE d.user_id = %s"
        params.append(user_id)
    sql += " ORDER BY d.created_at DESC"
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        rows = cur.fetchall()
        result = []
        for doc_id, title, source, created_at, num_chunks, first_content, source_modified_at in rows:
            snippet = None
            if first_content:
                snippet = (
                    first_content[:snippet_max_len]
                    + ("..." if len(first_content) > snippet_max_len else "")
                )
            result.append(
                (doc_id, title, source, created_at, num_chunks, snippet, source_modified_at)
            )
        return result
    finally:
        cur.close()


def list_doc_title_pairs(
    conn: PgConnection,
    user_id: str,
) -> list[tuple[str, str | None]]:
    """(doc_id, title) for the user; used for fuzzy title matching."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT doc_id, title FROM documents WHERE user_id = %s",
            (user_id,),
        )
        return [(r[0], r[1]) for r in cur.fetchall()]
    finally:
        cur.close()
