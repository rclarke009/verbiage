"""OpenAI vision analysis for claim inspection photos."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import random

import httpx

from app.config import LLM_MAX_ATTEMPTS, LLM_OPENAI_MODEL, LLM_TIMEOUT_SECONDS, OPENAI_API_KEY
from app.errors import LLMRateLimitedError, LLMServiceError, LLMUpstreamTimeoutError
from app.http_client import get_async_client
from app.report_writer.image_utils import normalize_image_bytes

logger = logging.getLogger(__name__)

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


def _retry_delay_seconds(attempt: int, retry_after: str | None = None) -> float:
    delay = 1.0 * (2**attempt)
    if retry_after:
        try:
            delay = max(delay, float(retry_after))
        except ValueError:
            pass
    jitter = random.uniform(0, delay * 0.5)
    return delay + jitter


async def analyze_image_bytes(image_bytes: bytes, content_type: str) -> dict:
    """Return caption/observations dict from OpenAI vision. Raises if no API key."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    image_bytes, mime = normalize_image_bytes(image_bytes, content_type)
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    payload = {
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
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    last_exc: BaseException | None = None
    retry_after: str | None = None
    for attempt in range(LLM_MAX_ATTEMPTS):
        try:
            client = get_async_client()
            resp = await client.post(
                OPENAI_CHAT_URL,
                headers=headers,
                json=payload,
                timeout=LLM_TIMEOUT_SECONDS,
            )
            if resp.status_code == 429:
                retry_after = resp.headers.get("retry-after")
                logger.warning(
                    "OpenAI vision API returned 429 (rate limited); body=%s; retry_after=%s",
                    resp.text[:500] if resp.text else "(empty)",
                    retry_after,
                )
                raise LLMRateLimitedError("OpenAI vision rate limited")
            if resp.status_code >= 400:
                raise LLMServiceError(
                    f"OpenAI vision API error {resp.status_code}: {resp.text[:200]}"
                )
            data = resp.json()
            choice = (data.get("choices") or [None])[0]
            msg = (choice.get("message") if choice else None) or {}
            text = (msg.get("content") or "").strip()
            return _parse_vision_response(text)
        except httpx.TimeoutException:
            last_exc = LLMUpstreamTimeoutError("OpenAI vision request timed out")
            retry_after = None
            if attempt < LLM_MAX_ATTEMPTS - 1:
                await asyncio.sleep(_retry_delay_seconds(attempt))
            else:
                raise last_exc
            continue
        except (LLMRateLimitedError, LLMUpstreamTimeoutError) as e:
            last_exc = e
            if attempt < LLM_MAX_ATTEMPTS - 1:
                await asyncio.sleep(_retry_delay_seconds(attempt, retry_after))
                retry_after = None
            else:
                raise
            continue
        except LLMServiceError:
            raise
        break
    if last_exc:
        raise last_exc
    raise RuntimeError("OpenAI vision retries exhausted")
