"""
LLM client: async answer_with_context uses OpenAI when OPENAI_API_KEY is set,
with optional fallback to Ollama; otherwise Ollama only.

Streaming helpers yield text deltas for POST /ask/stream (SSE).
"""

import asyncio
import json
import logging
import random

import httpx

from app.config import (
    LLM_BASE_URL,
    LLM_FALLBACK_TO_LOCAL,
    LLM_MAX_ATTEMPTS,
    LLM_MODEL,
    LLM_OPENAI_MODEL,
    LLM_TIMEOUT_SECONDS,
    OPENAI_API_KEY,
)
from app.errors import LLMRateLimitedError, LLMServiceError, LLMUpstreamTimeoutError

logger = logging.getLogger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


async def _answer_openai(prompt: str) -> str:
    """Call OpenAI chat completions; return assistant content. Retries on rate limit/timeout."""
    last_exc: BaseException | None = None
    for attempt in range(LLM_MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    OPENAI_CHAT_URL,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                    },
                    json={
                        "model": LLM_OPENAI_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                    },
                )
            if resp.status_code == 429:
                retry_after = resp.headers.get("retry-after")
                logger.warning(
                    "OpenAI chat API returned 429 (rate limited); body=%s; retry_after=%s",
                    resp.text[:500] if resp.text else "(empty)",
                    retry_after,
                )
                raise LLMRateLimitedError("OpenAI rate limited")
            if resp.status_code >= 400:
                raise LLMServiceError(
                    f"OpenAI API error {resp.status_code}: {resp.text[:200]}"
                )
            data = resp.json()
            choice = (data.get("choices") or [None])[0]
            if not choice:
                raise LLMServiceError("OpenAI response had no choices")
            msg = choice.get("message") or {}
            text = (msg.get("content") or "").strip()
            return text
        except httpx.TimeoutException:
            last_exc = LLMUpstreamTimeoutError("OpenAI request timed out")
            if attempt < LLM_MAX_ATTEMPTS - 1:
                delay = 1.0 * (2**attempt)
                jitter = random.uniform(0, delay * 0.5)
                await asyncio.sleep(delay + jitter)
            else:
                raise last_exc
            continue
        except (LLMRateLimitedError, LLMUpstreamTimeoutError) as e:
            last_exc = e
            if attempt < LLM_MAX_ATTEMPTS - 1:
                delay = 1.0 * (2**attempt)
                jitter = random.uniform(0, delay * 0.5)
                await asyncio.sleep(delay + jitter)
            else:
                raise
            continue
        except LLMServiceError:
            raise
        break
    if last_exc:
        raise last_exc
    raise RuntimeError("OpenAI LLM retries exhausted")


async def _answer_ollama(prompt: str) -> str:
    """Call Ollama /api/chat; return assistant content. Retries on rate limit/timeout."""
    last_exc: BaseException | None = None
    for attempt in range(LLM_MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    url=f"{LLM_BASE_URL.rstrip('/')}/api/chat",
                    json={
                        "model": LLM_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                    },
                )
            if resp.status_code == 429:
                raise LLMRateLimitedError("LLM rate limited")
            if resp.status_code >= 400:
                raise LLMServiceError(
                    f"LLM API error {resp.status_code}: {resp.text[:200]}"
                )
            data = resp.json()
            text = data.get("message", {}).get("content", "").strip()
            return text
        except httpx.TimeoutException:
            last_exc = LLMUpstreamTimeoutError("LLM request timed out")
            if attempt < LLM_MAX_ATTEMPTS - 1:
                delay = 1.0 * (2**attempt)
                jitter = random.uniform(0, delay * 0.5)
                await asyncio.sleep(delay + jitter)
            else:
                raise last_exc
            continue
        except (LLMRateLimitedError, LLMUpstreamTimeoutError) as e:
            last_exc = e
            if attempt < LLM_MAX_ATTEMPTS - 1:
                delay = 1.0 * (2**attempt)
                jitter = random.uniform(0, delay * 0.5)
                await asyncio.sleep(delay + jitter)
            else:
                raise
            continue
        except LLMServiceError:
            raise
        break
    if last_exc:
        raise last_exc
    raise RuntimeError("LLM retries exhausted")


async def answer_with_context(prompt: str) -> str:
    """Use OpenAI when OPENAI_API_KEY is set, else Ollama. If OpenAI fails and LLM_FALLBACK_TO_LOCAL is set, use Ollama."""
    if OPENAI_API_KEY:
        try:
            return await _answer_openai(prompt)
        except Exception as e:
            if LLM_FALLBACK_TO_LOCAL:
                logger.warning("OpenAI LLM failed, falling back to local: %s", e)
                return await _answer_ollama(prompt)
            raise
    return await _answer_ollama(prompt)


async def _answer_openai_stream(prompt: str):
    """Stream OpenAI chat completion content deltas."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }
    payload = {
        "model": LLM_OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
        async with client.stream(
            "POST",
            OPENAI_CHAT_URL,
            headers=headers,
            json=payload,
        ) as resp:
            if resp.status_code == 429:
                raise LLMRateLimitedError("OpenAI rate limited")
            if resp.status_code >= 400:
                err_txt = await resp.aread()
                snippet = err_txt[:200].decode(errors="replace") if err_txt else "(empty)"
                raise LLMServiceError(
                    f"OpenAI API error {resp.status_code}: {snippet}"
                )
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    break
                try:
                    j = json.loads(data)
                    choice = (j.get("choices") or [None])[0]
                    if not choice:
                        continue
                    delta = choice.get("delta") or {}
                    content = delta.get("content") or ""
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue


async def answer_with_context_stream(prompt: str):
    """Async iterator of answer text deltas. OpenAI streamed; otherwise one chunk from non-stream APIs."""
    if OPENAI_API_KEY:
        try:
            async for part in _answer_openai_stream(prompt):
                yield part
            return
        except LLMRateLimitedError:
            raise
        except LLMUpstreamTimeoutError:
            raise
        except LLMServiceError:
            raise
        except Exception as e:
            if LLM_FALLBACK_TO_LOCAL:
                logger.warning("OpenAI streaming failed, falling back to local once: %s", e)
                text = await _answer_ollama(prompt)
                if text:
                    yield text
                return
            raise
    text = await _answer_ollama(prompt)
    if text:
        yield text
