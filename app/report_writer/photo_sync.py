"""Sync claim photos from Google Drive and enqueue vision analysis jobs."""

from __future__ import annotations

from typing import Any

from app.db import (
    INGEST_BATCH_KIND_CLAIM_PHOTO_SYNC,
    INGEST_JOB_KIND_CLAIM_PHOTO_VISION,
    create_ingest_batch,
    has_active_vision_job,
    insert_ingest_jobs,
)
from app.drive_client import (
    DriveClientError,
    drive_file_view_url,
    list_image_files_metadata_async,
)
from app.report_writer.drive_photo_folders import resolve_drive_photo_folder_ids
from app.report_writer.queries import upsert_drive_claim_image


def enqueue_vision_jobs_for_claim(
    conn,
    *,
    claim_id: str,
    user_id: str,
    images: list[dict],
    skip_active: bool = False,
) -> dict[str, Any]:
    """Enqueue claim_photo_vision jobs for images missing vision_analysis."""
    jobs_to_enqueue: list[tuple[str, str, dict]] = []
    for img in images:
        if img.get("vision_analysis"):
            continue
        drive_file_id = img.get("drive_file_id")
        storage_path = img.get("storage_path")
        if not drive_file_id and not storage_path:
            continue
        if skip_active and has_active_vision_job(conn, img["image_id"]):
            continue
        job_doc_id = drive_file_id or img["image_id"]
        payload: dict[str, Any] = {
            "claim_id": claim_id,
            "user_id": user_id,
            "image_id": img["image_id"],
        }
        if drive_file_id:
            payload["drive_file_id"] = drive_file_id
        jobs_to_enqueue.append(
            (job_doc_id, INGEST_JOB_KIND_CLAIM_PHOTO_VISION, payload),
        )

    if not jobs_to_enqueue:
        conn.commit()
        return {
            "batch_id": None,
            "total": 0,
            "enqueued": 0,
            "image_count": len(images),
            "job_ids": [],
        }

    batch_id = create_ingest_batch(conn, INGEST_BATCH_KIND_CLAIM_PHOTO_SYNC, len(jobs_to_enqueue))
    job_ids = insert_ingest_jobs(conn, batch_id, jobs_to_enqueue)
    conn.commit()
    return {
        "batch_id": batch_id,
        "total": len(jobs_to_enqueue),
        "enqueued": len(jobs_to_enqueue),
        "image_count": len(images),
        "job_ids": job_ids,
    }


async def upsert_images_from_drive_folder(
    conn,
    *,
    claim_id: str,
    user_id: str,
    folder_id: str,
    sort_order_start: int = 0,
) -> list[dict]:
    """List images in a Drive folder and upsert claim image rows. Does not enqueue vision."""
    try:
        metas = await list_image_files_metadata_async(folder_id)
    except DriveClientError as e:
        raise ValueError(str(e)) from e

    images: list[dict] = []
    for idx, meta in enumerate(metas):
        fid = meta["id"]
        name = meta.get("name") or fid
        mime = meta.get("mimeType") or "image/jpeg"
        size = int(meta.get("size") or 0)
        row = upsert_drive_claim_image(
            conn,
            claim_id=claim_id,
            user_id=user_id,
            drive_file_id=fid,
            source_url=drive_file_view_url(fid),
            filename=name,
            content_type=mime,
            size_bytes=size,
            sort_order=sort_order_start + idx,
        )
        images.append(row)
    return images


async def sync_claim_photos_from_drive(
    conn,
    *,
    claim_id: str,
    user_id: str,
    folder_id: str | None = None,
    folder_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Upsert Drive image rows for one or more folders and enqueue vision for uncached images.
    Prefer folder_ids; folder_id remains a single-folder override.
    Returns { batch_id, total, image_count, job_ids, enqueued, folder_ids }.
    """
    ids = [fid for fid in (folder_ids or ([folder_id] if folder_id else [])) if fid]
    if not ids:
        raise ValueError("No Drive photo folder IDs to sync")

    images: list[dict] = []
    sort_base = 0
    for fid in ids:
        folder_images = await upsert_images_from_drive_folder(
            conn,
            claim_id=claim_id,
            user_id=user_id,
            folder_id=fid,
            sort_order_start=sort_base,
        )
        sort_base += len(folder_images)
        images.extend(folder_images)

    # Deduplicate by image_id if the same Drive file appeared in multiple folders
    by_id: dict[str, dict] = {}
    for img in images:
        by_id[img["image_id"]] = img
    unique_images = list(by_id.values())

    result = enqueue_vision_jobs_for_claim(
        conn,
        claim_id=claim_id,
        user_id=user_id,
        images=unique_images,
        skip_active=False,
    )
    result["folder_ids"] = ids
    return result


def folder_ids_for_claim_sync(meta: dict | None, *, override_folder_id: str | None = None) -> list[str]:
    """Resolve folder IDs for sync: optional single override, else all linked folders."""
    if override_folder_id:
        return [override_folder_id]
    return resolve_drive_photo_folder_ids(meta)


def claim_photo_analysis_counts(conn, claim_id: str, user_id: str) -> dict[str, int]:
    """Analysis status counts for a claim's images."""
    from app.report_writer.queries import count_claim_image_analysis, get_claim

    if not get_claim(conn, claim_id, user_id):
        return {"total": 0, "pending": 0, "running": 0, "succeeded": 0, "failed": 0, "with_damage": 0}
    return count_claim_image_analysis(conn, claim_id)
