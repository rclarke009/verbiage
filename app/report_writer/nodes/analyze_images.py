"""Graph node: load cached vision analyses for claim photos."""

from __future__ import annotations

import asyncio

from app.config import OPENAI_API_KEY
from app.db import get_valid_conn
from app.report_writer.deps import get_report_writer_deps
from app.report_writer.queries import list_claim_images, update_image_vision_analysis
from app.report_writer.state import ReportWriterState
from app.report_writer.storage import read_claim_image_bytes
from app.report_writer.vision import analyze_image_bytes


async def analyze_images(state: ReportWriterState) -> dict:
    """
    Populate image_analyses from DB cache. Only analyze uncached manual uploads inline;
    Drive-backed photos are analyzed by the background worker before generate.
    """
    deps = get_report_writer_deps()
    claim_id = state["claim_id"]
    user_id = state["user_id"]

    def _load_meta(conn):
        return list_claim_images(conn, claim_id, user_id)

    conn = get_valid_conn(deps.db_pool)
    try:
        images = await asyncio.to_thread(_load_meta, conn)
    finally:
        deps.db_pool.putconn(conn)

    if not images:
        return {"image_analyses": state.get("image_analyses") or []}

    analyses: list[dict] = []
    pending_count = 0

    for img in images:
        existing = img.get("vision_analysis")
        if existing:
            analyses.append(
                {
                    "image_id": img["image_id"],
                    "filename": img.get("filename", ""),
                    "caption": existing.get("caption", ""),
                    "observations": existing.get("observations", ""),
                }
            )
            continue

        status = img.get("analysis_status") or "pending"
        if img.get("drive_file_id"):
            pending_count += 1
            continue

        if not OPENAI_API_KEY or not img.get("storage_path"):
            pending_count += 1
            continue

        try:
            data = read_claim_image_bytes(img["storage_path"])
            result = await analyze_image_bytes(data, img.get("content_type") or "image/jpeg")
            result["image_id"] = img["image_id"]

            def _save(conn):
                update_image_vision_analysis(conn, img["image_id"], result)

            conn2 = get_valid_conn(deps.db_pool)
            try:
                await asyncio.to_thread(_save, conn2)
            finally:
                deps.db_pool.putconn(conn2)
            analyses.append(
                {
                    "image_id": img["image_id"],
                    "filename": img.get("filename", ""),
                    "caption": result.get("caption", ""),
                    "observations": result.get("observations", ""),
                }
            )
        except Exception:
            pending_count += 1

    out: dict = {"image_analyses": analyses}
    if pending_count:
        out["photo_analysis_pending"] = pending_count
    return out
