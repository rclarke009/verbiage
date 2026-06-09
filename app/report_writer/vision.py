"""OpenAI vision analysis for claim inspection photos."""

from __future__ import annotations

import base64
import json

from app.config import LLM_OPENAI_MODEL, OPENAI_API_KEY
from app.http_client import get_async_client
from app.report_writer.image_utils import normalize_image_bytes

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

VISION_PROMPT = (
    "Analyze this property inspection photo for storm-related damage. "
    "Respond with JSON only using this schema:\n"
    '{"has_damage": boolean, "observations": string}\n'
    "Set has_damage to true only when you see clear, observable evidence of "
    "storm-related damage. Set has_damage to false when there is no damage, "
    "damage is not visible, or the image is too unclear to tell. "
    "observations should be a brief caption-style description of what is visible."
)


def _parse_vision_response(text: str) -> dict:
    """Parse structured vision JSON; fall back to raw text on failure."""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            observations = (parsed.get("observations") or "").strip()
            result: dict = {
                "observations": observations,
                "caption": observations,
                "model": LLM_OPENAI_MODEL,
            }
            if "has_damage" in parsed:
                result["has_damage"] = bool(parsed["has_damage"])
            return result
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    text = text.strip()
    return {"caption": text, "observations": text, "model": LLM_OPENAI_MODEL}


async def analyze_image_bytes(image_bytes: bytes, content_type: str) -> dict:
    """Return caption/observations dict from OpenAI vision. Raises if no API key."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    image_bytes, mime = normalize_image_bytes(image_bytes, content_type)
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
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
            "response_format": {"type": "json_object"},
            "max_tokens": 400,
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    choice = (data.get("choices") or [None])[0]
    msg = (choice.get("message") if choice else None) or {}
    text = (msg.get("content") or "").strip()
    return _parse_vision_response(text)
