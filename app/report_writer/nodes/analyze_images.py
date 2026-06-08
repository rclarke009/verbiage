"""Graph node: vision analysis for claim photos (Phase 2)."""

from __future__ import annotations

import asyncio
import base64

from app.config import OPENAI_API_KEY, LLM_OPENAI_MODEL
from app.db import get_valid_conn
from app.http_client import get_async_client
from app.report_writer.deps import get_report_writer_deps
from app.report_writer.queries import list_claim_images, update_image_vision_analysis
from app.report_writer.state import ReportWriterState


async def _analyze_with_openai(image_bytes: bytes, content_type: str) -> dict:
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    mime = content_type or "image/jpeg"
    client = get_async_client()
    resp = await client.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": LLM_OPENAI_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Describe storm-related damage visible in this inspection photo. "
                                "List observable conditions only; note if unclear."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        },
                    ],
                }
            ],
            "max_tokens": 400,
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
    return {"caption": text, "observations": text, "model": LLM_OPENAI_MODEL}


async def analyze_images(state: ReportWriterState) -> dict:
    """Load claim images from storage and populate image_analyses in state."""
    if not OPENAI_API_KEY:
        return {}
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

    from app.report_writer.storage import read_claim_image_bytes

    analyses: list[dict] = []
    for img in images:
        existing = img.get("vision_analysis")
        if existing:
            analyses.append(
                {
                    "image_id": img["image_id"],
                    "caption": existing.get("caption", ""),
                    "observations": existing.get("observations", ""),
                }
            )
            continue
        try:
            data = read_claim_image_bytes(img["storage_path"])
            result = await _analyze_with_openai(data, img.get("content_type") or "image/jpeg")
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
                    "caption": result.get("caption", ""),
                    "observations": result.get("observations", ""),
                }
            )
        except Exception:
            continue

    return {"image_analyses": analyses}
