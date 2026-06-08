"""Postgres queries for Report Writer domain tables."""

from __future__ import annotations

import uuid
from typing import Any

from psycopg2.extras import Json, RealDictCursor

from app.db import get_valid_conn
from app.report_writer.constants import get_report_type, section_keys_for_type


def _row_to_claim(row: dict) -> dict[str, Any]:
    return {
        "claim_id": str(row["claim_id"]),
        "user_id": row["user_id"],
        "title": row["title"],
        "property_metadata": row["property_metadata"] or {},
        "field_notes": row["field_notes"] or "",
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


def create_claim(
    conn,
    *,
    user_id: str,
    title: str,
    property_metadata: dict | None = None,
    field_notes: str = "",
) -> dict[str, Any]:
    claim_id = str(uuid.uuid4())
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            INSERT INTO report_claims (claim_id, user_id, title, property_metadata, field_notes)
            VALUES (%s::uuid, %s, %s, %s, %s)
            RETURNING *
            """,
            (claim_id, user_id, title, Json(property_metadata or {}), field_notes),
        )
        row = cur.fetchone()
        conn.commit()
        return _row_to_claim(row)
    finally:
        cur.close()


def get_claim(conn, claim_id: str, user_id: str) -> dict[str, Any] | None:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            "SELECT * FROM report_claims WHERE claim_id = %s::uuid AND user_id = %s",
            (claim_id, user_id),
        )
        row = cur.fetchone()
        return _row_to_claim(row) if row else None
    finally:
        cur.close()


def list_claims(conn, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            SELECT * FROM report_claims
            WHERE user_id = %s
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        )
        return [_row_to_claim(r) for r in cur.fetchall()]
    finally:
        cur.close()


def update_claim(
    conn,
    claim_id: str,
    user_id: str,
    *,
    title: str | None = None,
    property_metadata: dict | None = None,
    field_notes: str | None = None,
    status: str | None = None,
) -> dict[str, Any] | None:
    sets: list[str] = ["updated_at = now()"]
    params: list[Any] = []
    if title is not None:
        sets.append("title = %s")
        params.append(title)
    if property_metadata is not None:
        sets.append("property_metadata = %s")
        params.append(Json(property_metadata))
    if field_notes is not None:
        sets.append("field_notes = %s")
        params.append(field_notes)
    if status is not None:
        sets.append("status = %s")
        params.append(status)
    params.extend([claim_id, user_id])
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            f"""
            UPDATE report_claims SET {", ".join(sets)}
            WHERE claim_id = %s::uuid AND user_id = %s
            RETURNING *
            """,
            params,
        )
        row = cur.fetchone()
        conn.commit()
        return _row_to_claim(row) if row else None
    finally:
        cur.close()


def delete_claim(conn, claim_id: str, user_id: str) -> bool:
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM report_claims WHERE claim_id = %s::uuid AND user_id = %s",
            (claim_id, user_id),
        )
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    finally:
        cur.close()


def get_claim_sections(conn, claim_id: str) -> dict[str, dict[str, Any]]:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            SELECT s.section_key, r.content, r.revision_id, r.origin, r.created_at
            FROM report_claim_sections s
            JOIN report_claim_section_revisions r ON r.revision_id = s.current_revision_id
            WHERE s.claim_id = %s::uuid
            ORDER BY s.section_key
            """,
            (claim_id,),
        )
        out: dict[str, dict[str, Any]] = {}
        for row in cur.fetchall():
            cur2 = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur2.execute(
                    """
                    SELECT chunk_id, doc_id, score, snippet
                    FROM report_claim_sources WHERE revision_id = %s::uuid
                    """,
                    (str(row["revision_id"]),),
                )
                sources = [
                    {
                        "chunk_id": s["chunk_id"],
                        "doc_id": s["doc_id"],
                        "score": s["score"],
                        "snippet": s["snippet"],
                    }
                    for s in cur2.fetchall()
                ]
            finally:
                cur2.close()
            out[row["section_key"]] = {
                "section_key": row["section_key"],
                "content": row["content"],
                "revision_id": str(row["revision_id"]),
                "origin": row["origin"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "sources": sources,
            }
        return out
    finally:
        cur.close()


def create_section_revision(
    conn,
    *,
    claim_id: str,
    section_key: str,
    content: str,
    origin: str,
    generation_run_id: str | None,
    sources: list[dict] | None = None,
) -> str:
    revision_id = str(uuid.uuid4())
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO report_claim_section_revisions
                (revision_id, claim_id, section_key, content, origin, generation_run_id)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s)
            """,
            (
                revision_id,
                claim_id,
                section_key,
                content,
                origin,
                generation_run_id,
            ),
        )
        for src in sources or []:
            cur.execute(
                """
                INSERT INTO report_claim_sources (revision_id, chunk_id, doc_id, score, snippet)
                VALUES (%s::uuid, %s, %s, %s, %s)
                ON CONFLICT (revision_id, chunk_id) DO NOTHING
                """,
                (
                    revision_id,
                    src.get("chunk_id"),
                    src.get("doc_id"),
                    src.get("score"),
                    src.get("snippet"),
                ),
            )
        cur.execute(
            """
            INSERT INTO report_claim_sections (claim_id, section_key, current_revision_id)
            VALUES (%s::uuid, %s, %s::uuid)
            ON CONFLICT (claim_id, section_key) DO UPDATE
            SET current_revision_id = EXCLUDED.current_revision_id
            """,
            (claim_id, section_key, revision_id),
        )
        conn.commit()
        return revision_id
    finally:
        cur.close()


def create_generation_run(conn, *, claim_id: str, user_id: str, thread_id: str) -> str:
    run_id = str(uuid.uuid4())
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO report_generation_runs (run_id, claim_id, user_id, thread_id, status)
            VALUES (%s::uuid, %s::uuid, %s, %s, 'running')
            """,
            (run_id, claim_id, user_id, thread_id),
        )
        cur.execute(
            "UPDATE report_claims SET status = 'generating', updated_at = now() WHERE claim_id = %s::uuid",
            (claim_id,),
        )
        conn.commit()
        return run_id
    finally:
        cur.close()


def finish_generation_run(
    conn,
    run_id: str,
    *,
    status: str,
    error: str | None = None,
    checkpoint_id: str | None = None,
) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE report_generation_runs
            SET status = %s, completed_at = now(), error = %s, langgraph_checkpoint_id = %s
            WHERE run_id = %s::uuid
            """,
            (status, error, checkpoint_id, run_id),
        )
        conn.commit()
    finally:
        cur.close()


def set_claim_status_after_run(conn, claim_id: str, status: str) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE report_claims SET status = %s, updated_at = now() WHERE claim_id = %s::uuid",
            (status, claim_id),
        )
        conn.commit()
    finally:
        cur.close()


def list_generation_runs(conn, claim_id: str, user_id: str) -> list[dict[str, Any]]:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            SELECT r.* FROM report_generation_runs r
            JOIN report_claims c ON c.claim_id = r.claim_id
            WHERE r.claim_id = %s::uuid AND c.user_id = %s
            ORDER BY r.started_at DESC
            """,
            (claim_id, user_id),
        )
        return [
            {
                "run_id": str(row["run_id"]),
                "claim_id": str(row["claim_id"]),
                "status": row["status"],
                "thread_id": row["thread_id"],
                "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
                "error": row["error"],
            }
            for row in cur.fetchall()
        ]
    finally:
        cur.close()


def get_generation_run(conn, claim_id: str, run_id: str, user_id: str) -> dict[str, Any] | None:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            SELECT r.* FROM report_generation_runs r
            JOIN report_claims c ON c.claim_id = r.claim_id
            WHERE r.run_id = %s::uuid AND r.claim_id = %s::uuid AND c.user_id = %s
            """,
            (run_id, claim_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        sections = get_claim_sections(conn, claim_id)
        return {
            "run_id": str(row["run_id"]),
            "claim_id": str(row["claim_id"]),
            "status": row["status"],
            "thread_id": row["thread_id"],
            "started_at": row["started_at"].isoformat() if row["started_at"] else None,
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
            "error": row["error"],
            "sections": sections,
        }
    finally:
        cur.close()


def list_claim_images(conn, claim_id: str, user_id: str) -> list[dict[str, Any]]:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            SELECT i.* FROM report_claim_images i
            JOIN report_claims c ON c.claim_id = i.claim_id
            WHERE i.claim_id = %s::uuid AND c.user_id = %s
            ORDER BY i.sort_order, i.created_at
            """,
            (claim_id, user_id),
        )
        return [
            {
                "image_id": str(row["image_id"]),
                "claim_id": str(row["claim_id"]),
                "filename": row["filename"],
                "content_type": row["content_type"],
                "size_bytes": row["size_bytes"],
                "storage_path": row["storage_path"],
                "vision_analysis": row["vision_analysis"],
                "sort_order": row["sort_order"],
            }
            for row in cur.fetchall()
        ]
    finally:
        cur.close()


def insert_claim_image(
    conn,
    *,
    claim_id: str,
    user_id: str,
    storage_path: str,
    filename: str,
    content_type: str,
    size_bytes: int,
    sort_order: int = 0,
) -> dict[str, Any]:
    image_id = str(uuid.uuid4())
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            INSERT INTO report_claim_images
                (image_id, claim_id, user_id, storage_path, filename, content_type, size_bytes, sort_order)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (image_id, claim_id, user_id, storage_path, filename, content_type, size_bytes, sort_order),
        )
        row = cur.fetchone()
        conn.commit()
        return {
            "image_id": str(row["image_id"]),
            "claim_id": str(row["claim_id"]),
            "filename": row["filename"],
            "content_type": row["content_type"],
            "size_bytes": row["size_bytes"],
            "storage_path": row["storage_path"],
            "vision_analysis": row["vision_analysis"],
            "sort_order": row["sort_order"],
        }
    finally:
        cur.close()


def update_image_vision_analysis(conn, image_id: str, analysis: dict) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE report_claim_images SET vision_analysis = %s WHERE image_id = %s::uuid",
            (Json(analysis), image_id),
        )
        conn.commit()
    finally:
        cur.close()


def chunks_to_dicts(chunks) -> list[dict]:
    """Serialize RetrievedChunk list for graph state."""
    return [
        {
            "chunk_id": c.chunk_id,
            "doc_id": c.doc_id,
            "score": c.score,
            "content_snippet": c.content_snippet,
            "document_title": c.document_title,
            "source": c.source,
            "source_url": c.source_url,
            "section_label": c.section_label,
        }
        for c in chunks
    ]


def empty_sections_template(report_type: str | None = None, property_metadata: dict | None = None) -> dict[str, dict]:
    type_id = report_type or get_report_type(property_metadata)
    keys = section_keys_for_type(type_id)
    return {key: {"content": "", "status": "pending", "sources": []} for key in keys}


def claim_has_generated_sections(conn, claim_id: str) -> bool:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT 1
            FROM report_claim_section_revisions r
            JOIN report_claim_sections s ON s.current_revision_id = r.revision_id
            WHERE s.claim_id = %s AND r.content <> ''
            LIMIT 1
            """,
            (claim_id,),
        )
        return cur.fetchone() is not None
