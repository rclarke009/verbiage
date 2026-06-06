"""Background worker: process Postgres-backed ingest jobs (Google Drive)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import INGEST_WORKER_ENABLED
from app.db import (
    INGEST_JOB_KIND_GOOGLE_DRIVE,
    claim_next_ingest_job,
    doc_exist,
    finish_ingest_job,
    get_document_index_by_doc_ids,
    get_valid_conn,
    refresh_batch_counts,
)
from app.drive_client import (
    DriveClientError,
    compute_index_status,
    drive_source_url_for_mime,
    fetch_drive_file_async,
)
from app.ingest_core import ingest_new_document, reingest_existing_document
from app.models import ChunkingOptions, IngestResponse

logger = logging.getLogger(__name__)

DEFAULT_CHUNKING = ChunkingOptions()


def _ingest_response_to_result(response: IngestResponse) -> dict[str, Any]:
    return response.model_dump()


async def process_google_drive_job(pool, job: dict[str, Any]) -> tuple[str, dict | None, str | None]:
    """
    Process one google_drive job. Returns (terminal_status, result_dict, error_message).
    terminal_status: succeeded | failed | skipped
    """
    doc_id = job["doc_id"]
    payload = job["payload"] or {}
    drive_file_id = payload.get("drive_file_id") or doc_id

    try:
        doc = await fetch_drive_file_async(drive_file_id)
    except DriveClientError as e:
        return "failed", None, str(e)

    source_url = drive_source_url_for_mime(doc.doc_id, doc.mime_type)
    drive_modified = doc.source_modified_at

    conn = get_valid_conn(pool)
    try:
        if doc_exist(conn, doc_id):
            index_meta = get_document_index_by_doc_ids(conn, [doc_id])
            source_modified_at = index_meta.get(doc_id, (None, 0))[0]
            status = compute_index_status(True, drive_modified, source_modified_at)
            if status == "indexed":
                return "skipped", {"doc_id": doc_id, "reason": "already_indexed"}, None
            result = await reingest_existing_document(
                conn,
                doc.doc_id,
                doc.title,
                doc.source,
                doc.text,
                DEFAULT_CHUNKING,
                source_modified_at=doc.source_modified_at,
                source_url=source_url,
                source_filename=doc.title,
            )
        else:
            result = await ingest_new_document(
                conn,
                doc.doc_id,
                doc.title,
                doc.source,
                doc.text,
                DEFAULT_CHUNKING,
                source_modified_at=doc.source_modified_at,
                source_url=source_url,
                source_filename=doc.title,
            )
        conn.commit()
        return "succeeded", _ingest_response_to_result(result), None
    except Exception as e:
        conn.rollback()
        logger.exception("Ingest job %s failed for %s", job["id"], doc_id)
        return "failed", None, str(e)
    finally:
        pool.putconn(conn)


async def process_ingest_job(pool, job: dict[str, Any]) -> None:
    batch_id = job["batch_id"]
    job_id = job["id"]
    kind = job["kind"]

    if kind == INGEST_JOB_KIND_GOOGLE_DRIVE:
        terminal, result, error = await process_google_drive_job(pool, job)
    else:
        terminal, result, error = "failed", None, f"Unknown job kind: {kind}"

    conn = get_valid_conn(pool)
    try:
        finish_ingest_job(conn, job_id, terminal, result=result, error=error)
        refresh_batch_counts(conn, batch_id)
        conn.commit()
    finally:
        pool.putconn(conn)


async def ingest_worker_loop(pool) -> None:
    """Poll Postgres for pending ingest jobs and process one at a time."""
    if not INGEST_WORKER_ENABLED:
        logger.info("Ingest worker disabled (INGEST_WORKER_ENABLED=0)")
        return

    logger.info("Ingest worker started")
    while True:
        try:
            conn = get_valid_conn(pool)
            try:
                job = claim_next_ingest_job(conn)
                if job:
                    conn.commit()
                else:
                    conn.rollback()
            finally:
                pool.putconn(conn)

            if not job:
                await asyncio.sleep(0.5)
                continue

            try:
                await process_ingest_job(pool, job)
            except Exception as e:
                logger.error("Unexpected error processing ingest job %s: %s", job.get("id"), e)
                conn2 = get_valid_conn(pool)
                try:
                    finish_ingest_job(conn2, job["id"], "failed", error=str(e))
                    refresh_batch_counts(conn2, job["batch_id"])
                    conn2.commit()
                finally:
                    pool.putconn(conn2)
        except Exception as e:
            logger.error("Ingest worker loop error: %s", e)
            await asyncio.sleep(1.0)
