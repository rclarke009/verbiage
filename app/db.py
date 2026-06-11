"""
Postgres + pgvector DB layer. create_db runs DDL; helpers use psycopg2 connections.
For in-memory similarity (tests/fallback), use get_embeddings_for_retrieval + similarity.cosine_similarity.

Supabase transaction-mode pooler (port 6543) does not support prepared statements; use
connection_factory=NoPrepareConnection when creating the pool for such URLs.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import psycopg2
from psycopg2.extras import Json
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
        # Legacy user_id column (shared library; queries ignore it); idempotent for existing DBs
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
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'documents'
                      AND column_name = 'source_url'
                ) THEN
                    ALTER TABLE documents ADD COLUMN source_url TEXT;
                END IF;
            END $$;
        """)
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'documents'
                      AND column_name = 'full_text'
                ) THEN
                    ALTER TABLE documents ADD COLUMN full_text TEXT NOT NULL DEFAULT '';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'documents'
                      AND column_name = 'source_filename'
                ) THEN
                    ALTER TABLE documents ADD COLUMN source_filename TEXT;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'documents'
                      AND column_name = 'chunking_config'
                ) THEN
                    ALTER TABLE documents ADD COLUMN chunking_config JSONB;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'documents'
                      AND column_name = 'embedding_model'
                ) THEN
                    ALTER TABLE documents ADD COLUMN embedding_model TEXT;
                END IF;
            END $$;
        """)
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'chunks'
                      AND column_name = 'content_tsv'
                ) THEN
                    ALTER TABLE chunks ADD COLUMN content_tsv tsvector
                        GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED;
                END IF;
            END $$;
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_chunks_content_tsv ON chunks USING GIN (content_tsv);"
        )
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'chunks'
                      AND column_name = 'section_label'
                ) THEN
                    ALTER TABLE chunks ADD COLUMN section_label TEXT;
                END IF;
            END $$;
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ingest_batches (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                kind TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                total INT NOT NULL DEFAULT 0,
                pending INT NOT NULL DEFAULT 0,
                running INT NOT NULL DEFAULT 0,
                succeeded INT NOT NULL DEFAULT 0,
                failed INT NOT NULL DEFAULT 0,
                skipped INT NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ingest_jobs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                batch_id UUID NOT NULL REFERENCES ingest_batches(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'pending',
                kind TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                payload JSONB NOT NULL,
                result JSONB,
                error TEXT,
                attempts INT NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_ingest_jobs_status_created ON ingest_jobs(status, created_at);"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_ingest_jobs_batch ON ingest_jobs(batch_id);"
        )
        cur.execute("""
            CREATE TABLE IF NOT EXISTS signup_allowlist (
                email TEXT PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                note TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS report_claims (
                claim_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                property_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                field_notes TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_report_claims_user_updated "
            "ON report_claims(user_id, updated_at DESC);"
        )
        cur.execute("""
            CREATE TABLE IF NOT EXISTS report_generation_runs (
                run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                claim_id UUID NOT NULL REFERENCES report_claims(claim_id) ON DELETE CASCADE,
                user_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                thread_id TEXT NOT NULL,
                langgraph_checkpoint_id TEXT,
                started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                completed_at TIMESTAMPTZ,
                error TEXT
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_report_generation_runs_claim "
            "ON report_generation_runs(claim_id, started_at DESC);"
        )
        cur.execute("""
            CREATE TABLE IF NOT EXISTS report_claim_section_revisions (
                revision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                claim_id UUID NOT NULL REFERENCES report_claims(claim_id) ON DELETE CASCADE,
                section_key TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                origin TEXT NOT NULL DEFAULT 'generation',
                generation_run_id UUID REFERENCES report_generation_runs(run_id) ON DELETE SET NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_report_section_revisions_claim "
            "ON report_claim_section_revisions(claim_id, section_key, created_at DESC);"
        )
        cur.execute("""
            CREATE TABLE IF NOT EXISTS report_claim_sections (
                claim_id UUID NOT NULL REFERENCES report_claims(claim_id) ON DELETE CASCADE,
                section_key TEXT NOT NULL,
                current_revision_id UUID NOT NULL REFERENCES report_claim_section_revisions(revision_id) ON DELETE CASCADE,
                PRIMARY KEY (claim_id, section_key)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS report_claim_sources (
                revision_id UUID NOT NULL REFERENCES report_claim_section_revisions(revision_id) ON DELETE CASCADE,
                chunk_id TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                score DOUBLE PRECISION,
                snippet TEXT,
                PRIMARY KEY (revision_id, chunk_id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS report_claim_images (
                image_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                claim_id UUID NOT NULL REFERENCES report_claims(claim_id) ON DELETE CASCADE,
                user_id TEXT NOT NULL,
                storage_path TEXT,
                drive_file_id TEXT,
                source_url TEXT,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
                size_bytes BIGINT NOT NULL DEFAULT 0,
                vision_analysis JSONB,
                analysis_status TEXT NOT NULL DEFAULT 'pending',
                sort_order INT NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_report_claim_images_claim "
            "ON report_claim_images(claim_id, sort_order);"
        )
        cur.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'report_claim_images'
                      AND column_name = 'storage_path' AND is_nullable = 'NO'
                ) THEN
                    ALTER TABLE report_claim_images ALTER COLUMN storage_path DROP NOT NULL;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'report_claim_images'
                      AND column_name = 'drive_file_id'
                ) THEN
                    ALTER TABLE report_claim_images ADD COLUMN drive_file_id TEXT;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'report_claim_images'
                      AND column_name = 'source_url'
                ) THEN
                    ALTER TABLE report_claim_images ADD COLUMN source_url TEXT;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'report_claim_images'
                      AND column_name = 'analysis_status'
                ) THEN
                    ALTER TABLE report_claim_images
                        ADD COLUMN analysis_status TEXT NOT NULL DEFAULT 'pending';
                END IF;
            END $$;
        """)
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_report_claim_images_drive_unique "
            "ON report_claim_images(claim_id, drive_file_id) WHERE drive_file_id IS NOT NULL;"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_report_claim_images_analysis "
            "ON report_claim_images(claim_id, analysis_status);"
        )
        cur.execute("ALTER TABLE report_claims ENABLE ROW LEVEL SECURITY;")
        cur.execute("ALTER TABLE report_generation_runs ENABLE ROW LEVEL SECURITY;")
        cur.execute("ALTER TABLE report_claim_section_revisions ENABLE ROW LEVEL SECURITY;")
        cur.execute("ALTER TABLE report_claim_sections ENABLE ROW LEVEL SECURITY;")
        cur.execute("ALTER TABLE report_claim_sources ENABLE ROW LEVEL SECURITY;")
        cur.execute("ALTER TABLE report_claim_images ENABLE ROW LEVEL SECURITY;")
        cur.execute("ALTER TABLE signup_allowlist ENABLE ROW LEVEL SECURITY;")
        conn.commit()
    finally:
        cur.close()


def email_in_signup_allowlist(conn: PgConnection, email: str) -> bool:
    """True if lowercase email exists in signup_allowlist (server DB role bypasses RLS)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM signup_allowlist WHERE email = %s LIMIT 1",
            (email.lower(),),
        )
        return cur.fetchone() is not None
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
    source_url: str | None = None,
    full_text: str = "",
    source_filename: str | None = None,
    chunking_config: dict | None = None,
    embedding_model: str | None = None,
) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO documents("
            "doc_id, title, source, created_at, user_id, source_modified_at, source_url, "
            "full_text, source_filename, chunking_config, embedding_model"
            ") VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                doc_id,
                title,
                source,
                created_at,
                user_id,
                source_modified_at,
                source_url,
                full_text,
                source_filename,
                Json(chunking_config) if chunking_config is not None else None,
                embedding_model,
            ),
        )
    finally:
        cur.close()


def update_document_indexing_metadata(
    conn: PgConnection,
    doc_id: str,
    chunking_config: dict,
    embedding_model: str,
) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE documents SET chunking_config = %s, embedding_model = %s WHERE doc_id = %s",
            (Json(chunking_config), embedding_model, doc_id),
        )
    finally:
        cur.close()


def get_document_full_text(conn: PgConnection, doc_id: str) -> str | None:
    cur = conn.cursor()
    try:
        cur.execute("SELECT full_text FROM documents WHERE doc_id = %s", (doc_id,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()


def get_document_breadcrumb_fields(
    conn: PgConnection, doc_id: str
) -> tuple[str | None, str | None, str | None]:
    """Return (title, source, source_filename) for document breadcrumb prefixes."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT title, source, source_filename FROM documents WHERE doc_id = %s",
            (doc_id,),
        )
        row = cur.fetchone()
        if not row:
            return None, None, None
        return row[0], row[1], row[2]
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
    section_label: str | None = None,
) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO chunks("
            "chunk_id, doc_id, chunk_index, content, start_offset, end_offset, section_label"
            ") VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (
                chunk_id,
                doc_id,
                chunk_index,
                content,
                start_offset,
                end_offset,
                section_label,
            ),
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


def get_document_index_by_doc_ids(
    conn: PgConnection, doc_ids: list[str]
) -> dict[str, tuple[int | None, int]]:
    """
    Returns doc_id -> (source_modified_at, num_chunks) for documents in doc_ids.
    """
    if not doc_ids:
        return {}
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                d.doc_id,
                d.source_modified_at,
                (SELECT COUNT(*) FROM chunks c WHERE c.doc_id = d.doc_id) AS num_chunks
            FROM documents d
            WHERE d.doc_id = ANY(%s)
            """,
            (doc_ids,),
        )
        return {row[0]: (row[1], row[2]) for row in cur.fetchall()}
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
    embedding_model: str | None = None,
) -> list[tuple[str, str, float, str, str | None, str | None, str | None, str | None]]:
    """Postgres similarity search over the shared document library. Returns (chunk_id, doc_id, score, content, title, source, source_url, section_label). Uses <=> (cosine distance)."""
    _ensure_pgvector(conn)
    sql = """
        SELECT c.chunk_id, c.doc_id, 1 - (e.embedding <=> %s::vector) AS score, c.content,
               d.title, d.source, d.source_url, c.section_label
        FROM embeddings e
        JOIN chunks c ON e.chunk_id = c.chunk_id
        JOIN documents d ON d.doc_id = c.doc_id
    """
    conditions: list[str] = []
    params: list[Any] = [query_vec]
    if embedding_model is not None:
        conditions.append("e.model = %s")
        params.append(embedding_model)
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

def retrieve_top_k_lexical_pg(
    conn: PgConnection,
    query_text: str,
    top_k: int,
    doc_id: str | None = None,
) -> list[tuple[str, str, float, str, str | None, str | None, str | None, str | None]]:
    """Postgres full-text (lexical) search over the shared document library. Returns (chunk_id, doc_id, score, content, title, source, source_url, section_label). Uses ts_rank over content_tsv."""
    sql = """
        SELECT c.chunk_id, c.doc_id,
               ts_rank(c.content_tsv, websearch_to_tsquery('english', %s)) AS score,
               c.content, d.title, d.source, d.source_url, c.section_label
        FROM chunks c
        JOIN documents d ON d.doc_id = c.doc_id
        WHERE c.content_tsv @@ websearch_to_tsquery('english', %s)
    """
    params: list[Any] = [query_text, query_text]
    if doc_id is not None:
        sql += " AND c.doc_id = %s"
        params.append(doc_id)
    sql += " ORDER BY score DESC LIMIT %s"
    params.append(top_k)
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()


def delete_chunks_for_doc(conn: PgConnection, doc_id: str) -> None:
    """Remove chunks and embeddings for a document; keep the documents row (for reindex)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM embeddings WHERE chunk_id IN (SELECT chunk_id FROM chunks WHERE doc_id = %s)",
            (doc_id,),
        )
        cur.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
    finally:
        cur.close()


def delete_by_doc_id(conn: PgConnection, doc_id: str) -> None:
    cur = conn.cursor()
    try:
        delete_chunks_for_doc(conn, doc_id)
        cur.execute("DELETE FROM documents WHERE doc_id = %s", (doc_id,))
        conn.commit()
    finally:
        cur.close()


def delete_document(conn: PgConnection, doc_id: str) -> bool:
    """Delete a document from the shared library by doc_id. Returns True if a row was removed."""
    if not doc_exist(conn, doc_id):
        return False
    delete_by_doc_id(conn, doc_id)
    return True


def list_documents(
    conn: PgConnection,
    snippet_max_len: int = 250,
) -> list[
    tuple[
        str,
        str | None,
        str | None,
        int,
        int,
        str | None,
        int | None,
        str | None,
        str | None,
        str | None,
        dict | None,
    ]
]:
    """
    Returns list of (doc_id, title, source, created_at, num_chunks, snippet,
    source_modified_at, source_url, source_filename, embedding_model, chunking_config).
    Ordered by created_at desc (shared library — all documents).
    """
    sql = """
        SELECT
            d.doc_id,
            d.title,
            d.source,
            d.created_at,
            (SELECT COUNT(*) FROM chunks c WHERE c.doc_id = d.doc_id) AS num_chunks,
            (SELECT c.content FROM chunks c WHERE c.doc_id = d.doc_id ORDER BY c.chunk_index LIMIT 1) AS first_content,
            d.source_modified_at,
            d.source_url,
            d.source_filename,
            d.embedding_model,
            d.chunking_config
        FROM documents d
        ORDER BY d.created_at DESC
    """
    cur = conn.cursor()
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        result = []
        for (
            doc_id,
            title,
            source,
            created_at,
            num_chunks,
            first_content,
            source_modified_at,
            source_url,
            source_filename,
            embedding_model,
            chunking_config,
        ) in rows:
            snippet = None
            if first_content:
                snippet = (
                    first_content[:snippet_max_len]
                    + ("..." if len(first_content) > snippet_max_len else "")
                )
            config_dict = chunking_config
            if isinstance(chunking_config, str):
                config_dict = json.loads(chunking_config)
            result.append(
                (
                    doc_id,
                    title,
                    source,
                    created_at,
                    num_chunks,
                    snippet,
                    source_modified_at,
                    source_url,
                    source_filename,
                    embedding_model,
                    config_dict,
                )
            )
        return result
    finally:
        cur.close()


def get_document_source_fields(
    conn: PgConnection, doc_ids: list[str]
) -> dict[str, tuple[str | None, str | None, str | None]]:
    """
    For each doc_id, return (title, source, source_url) from documents.
    Omits doc_ids that are not in the table.
    """
    if not doc_ids:
        return {}
    unique: list[str] = list(dict.fromkeys(doc_ids))
    placeholders = ",".join(["%s"] * len(unique))
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT doc_id, title, source, source_url FROM documents WHERE doc_id IN ({placeholders})",
            unique,
        )
        return {r[0]: (r[1], r[2], r[3]) for r in cur.fetchall()}
    finally:
        cur.close()


def list_doc_title_pairs(conn: PgConnection) -> list[tuple[str, str | None]]:
    """(doc_id, title) for all documents; used for fuzzy title matching."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT doc_id, title FROM documents")
        return [(r[0], r[1]) for r in cur.fetchall()]
    finally:
        cur.close()


# --- Ingest job queue ---

INGEST_JOB_KIND_GOOGLE_DRIVE = "google_drive"
INGEST_JOB_KIND_CLAIM_PHOTO_VISION = "claim_photo_vision"
INGEST_BATCH_KIND_CLAIM_PHOTO_SYNC = "claim_photo_sync"


def create_ingest_batch(conn: PgConnection, kind: str, total: int) -> str:
    """Create a batch row; initial counters assume all jobs pending."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO ingest_batches (
                kind, status, total, pending, running, succeeded, failed, skipped
            ) VALUES (%s, 'pending', %s, %s, 0, 0, 0, 0)
            RETURNING id::text
            """,
            (kind, total, total),
        )
        row = cur.fetchone()
        assert row is not None
        return row[0]
    finally:
        cur.close()


def insert_ingest_jobs(
    conn: PgConnection,
    batch_id: str,
    jobs: list[tuple[str, str, dict]],
) -> list[str]:
    """Insert jobs as (doc_id, kind, payload). Returns job ids."""
    if not jobs:
        return []
    cur = conn.cursor()
    try:
        ids: list[str] = []
        for doc_id, kind, payload in jobs:
            cur.execute(
                """
                INSERT INTO ingest_jobs (batch_id, kind, doc_id, payload, status)
                VALUES (%s::uuid, %s, %s, %s, 'pending')
                RETURNING id::text
                """,
                (batch_id, kind, doc_id, Json(payload)),
            )
            row = cur.fetchone()
            assert row is not None
            ids.append(row[0])
        return ids
    finally:
        cur.close()


def claim_next_ingest_job(conn: PgConnection) -> dict[str, Any] | None:
    """Claim one pending job (SKIP LOCKED). Caller must commit."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE ingest_jobs
            SET status = 'running', updated_at = now(), attempts = attempts + 1
            WHERE id = (
                SELECT id FROM ingest_jobs
                WHERE status = 'pending'
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id::text, batch_id::text, kind, doc_id, payload, attempts
            """
        )
        row = cur.fetchone()
        if not row:
            return None
        payload = row[4]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return {
            "id": row[0],
            "batch_id": row[1],
            "kind": row[2],
            "doc_id": row[3],
            "payload": payload,
            "attempts": row[5],
        }
    finally:
        cur.close()


def finish_ingest_job(
    conn: PgConnection,
    job_id: str,
    status: str,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE ingest_jobs
            SET status = %s, result = %s, error = %s, updated_at = now()
            WHERE id = %s::uuid
            """,
            (status, Json(result) if result is not None else None, error, job_id),
        )
    finally:
        cur.close()


def refresh_batch_counts(conn: PgConnection, batch_id: str) -> None:
    """Recompute batch counters and terminal status from child jobs."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE ingest_batches b SET
                pending = sub.pending,
                running = sub.running,
                succeeded = sub.succeeded,
                failed = sub.failed,
                skipped = sub.skipped,
                status = CASE
                    WHEN sub.running > 0 OR sub.pending > 0 THEN
                        CASE WHEN sub.running > 0 THEN 'running' ELSE 'pending' END
                    WHEN sub.failed > 0 AND sub.succeeded = 0 AND sub.skipped = 0 THEN 'failed'
                    ELSE 'completed'
                END,
                updated_at = now()
            FROM (
                SELECT
                    COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                    COUNT(*) FILTER (WHERE status = 'running') AS running,
                    COUNT(*) FILTER (WHERE status = 'succeeded') AS succeeded,
                    COUNT(*) FILTER (WHERE status = 'failed') AS failed,
                    COUNT(*) FILTER (WHERE status = 'skipped') AS skipped
                FROM ingest_jobs
                WHERE batch_id = %s::uuid
            ) sub
            WHERE b.id = %s::uuid
            """,
            (batch_id, batch_id),
        )
    finally:
        cur.close()


def get_ingest_batch(conn: PgConnection, batch_id: str) -> dict[str, Any] | None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id::text, kind, status, total, pending, running, succeeded, failed, skipped,
                   created_at, updated_at
            FROM ingest_batches WHERE id = %s::uuid
            """,
            (batch_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "kind": row[1],
            "status": row[2],
            "total": row[3],
            "pending": row[4],
            "running": row[5],
            "succeeded": row[6],
            "failed": row[7],
            "skipped": row[8],
            "created_at": row[9],
            "updated_at": row[10],
        }
    finally:
        cur.close()


def get_ingest_batch_errors(conn: PgConnection, batch_id: str, limit: int = 10) -> list[str]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT doc_id, error FROM ingest_jobs
            WHERE batch_id = %s::uuid AND status = 'failed' AND error IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (batch_id, limit),
        )
        return [f"{r[0]}: {r[1]}" for r in cur.fetchall()]
    finally:
        cur.close()


def get_ingest_batch_claim_context(conn: PgConnection, batch_id: str) -> dict[str, str] | None:
    """Return claim_id and user_id from first job payload (claim photo batches)."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT payload FROM ingest_jobs
            WHERE batch_id = %s::uuid
            ORDER BY created_at
            LIMIT 1
            """,
            (batch_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        payload = row[0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            return None
        claim_id = payload.get("claim_id")
        user_id = payload.get("user_id")
        if claim_id and user_id:
            return {"claim_id": str(claim_id), "user_id": str(user_id)}
        return None
    finally:
        cur.close()


def update_document_for_drive_reingest(
    conn: PgConnection,
    doc_id: str,
    title: str | None,
    source: str | None,
    full_text: str,
    source_modified_at: int | None,
    source_url: str | None,
    source_filename: str | None,
) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE documents SET
                title = %s, source = %s, full_text = %s, source_modified_at = %s,
                source_url = %s, source_filename = %s
            WHERE doc_id = %s
            """,
            (
                title,
                source,
                full_text,
                source_modified_at,
                source_url,
                source_filename,
                doc_id,
            ),
        )
    finally:
        cur.close()
