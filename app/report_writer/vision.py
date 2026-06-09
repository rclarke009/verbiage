"""OpenAI vision analysis for claim inspection photos."""

from __future__ import annotations

import base64

from app.config import LLM_OPENAI_MODEL, OPENAI_API_KEY
from app.http_client import get_async_client

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

VISION_PROMPT = (
    "Describe storm-related damage visible in this inspection photo. "
    "List observable conditions only; note if unclear."
)


async def analyze_image_bytes(image_bytes: bytes, content_type: str) -> dict:
    """Return caption/observations dict from OpenAI vision. Raises if no API key."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    mime = content_type or "image/jpeg"
    client = get_async_client()
    resp = await client.post(
        OPENAI_CHAT_URL,
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
                        {"type": "text", "text": VISION_PROMPT},
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
    choice = (data.get("choices") or [None])[0]
    msg = (choice.get("message") if choice else None) or {}
    text = (msg.get("content") or "").strip()
    return {"caption": text, "observations": text, "model": LLM_OPENAI_MODEL}
