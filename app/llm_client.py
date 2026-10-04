"""
LLM client: async answer_with_context uses xAI Grok when XAI_API_KEY is set,
otherwise OpenAI when OPENAI_API_KEY is set, with optional fallback to Ollama.

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
    LLM_TEMPERATURE,
    LLM_TIMEOUT_SECONDS,
    LLM_XAI_MODEL,
    OPENAI_API_KEY,
    XAI_API_KEY,
    XAI_CHAT_URL,
)
from app.errors import LLMRateLimitedError, LLMServiceError, LLMUpstreamTimeoutError
from app.http_client import get_async_client
from app.monitoring.metrics import record_upstream_fallback, record_upstream_timeout

logger = logging.getLogger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


def remote_chat() -> tuple[str, str, str, str] | None:
    """(provider, api_key, model, chat_url). Grok wins when its key is set."""
    if XAI_API_KEY:
        return ("xai", XAI_API_KEY, LLM_XAI_MODEL, XAI_CHAT_URL)
    if OPENAI_API_KEY:
        return ("openai", OPENAI_API_KEY, LLM_OPENAI_MODEL, OPENAI_CHAT_URL)
    return None


async def _answer_remote(
    prompt: str,
    *,
    provider: str,
    api_key: str,
    model: str,
    chat_url: str,
    temperature: float | None = None,
) -> str:
    """Call an OpenAI-compatible chat completions API. Retries on rate limit/timeout."""
    label = "xAI" if provider == "xai" else "OpenAI"
    last_exc: BaseException | None = None
    for attempt in range(LLM_MAX_ATTEMPTS):
        try:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            }
            if temperature is not None:
                payload["temperature"] = temperature
            client = get_async_client()
            resp = await client.post(
                chat_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json=payload,
                timeout=LLM_TIMEOUT_SECONDS,
            )
            if resp.status_code == 429:
                retry_after = resp.headers.get("retry-after")
                logger.warning(
                    "%s chat API returned 429 (rate limited); body=%s; retry_after=%s",
                    label,
                    resp.text[:500] if resp.text else "(empty)",
                    retry_after,
                )
                raise LLMRateLimitedError(f"{label} rate limited")
            if resp.status_code >= 400:
                raise LLMServiceError(
                    f"{label} API error {resp.status_code}: {resp.text[:200]}"
                )
            data = resp.json()
            choice = (data.get("choices") or [None])[0]
            if not choice:
                raise LLMServiceError(f"{label} response had no choices")
            msg = choice.get("message") or {}
            text = (msg.get("content") or "").strip()
            return text
        except httpx.TimeoutException:
            last_exc = LLMUpstreamTimeoutError(f"{label} request timed out")
            if attempt < LLM_MAX_ATTEMPTS - 1:
                delay = 1.0 * (2**attempt)
                jitter = random.uniform(0, delay * 0.5)
                await asyncio.sleep(delay + jitter)
            else:
                record_upstream_timeout("llm_xai" if provider == "xai" else "llm_openai")
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
    raise RuntimeError(f"{label} LLM retries exhausted")


async def _answer_ollama(prompt: str, temperature: float | None = None) -> str:
    """Call Ollama /api/chat; return assistant content. Retries on rate limit/timeout."""
    last_exc: BaseException | None = None
    for attempt in range(LLM_MAX_ATTEMPTS):
        try:
            payload = {
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            }
            if temperature is not None:
                payload["options"] = {"temperature": temperature}
            client = get_async_client()
            resp = await client.post(
                url=f"{LLM_BASE_URL.rstrip('/')}/api/chat",
                json=payload,
                timeout=LLM_TIMEOUT_SECONDS,
            )
            if resp.status_code == 429:
                raise LLMRateLimitedError("LLM rate limited")
            if resp.status_code >= 400:
                raise LLMServiceError(
                    f"LLM API error {resp.status_code}: {resp.text[:200]}"
                )
            data = resp.json()
            msg = data.get("message") or {}
            text = (msg.get("content") or "").strip()
            return text
        except httpx.TimeoutException:
            last_exc = LLMUpstreamTimeoutError("LLM request timed out")
            if attempt < LLM_MAX_ATTEMPTS - 1:
                delay = 1.0 * (2**attempt)
                jitter = random.uniform(0, delay * 0.5)
                await asyncio.sleep(delay + jitter)
            else:
                record_upstream_timeout("llm_ollama")
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


async def answer_with_context(prompt: str, temperature: float | None = None) -> str:
    """Use Grok when XAI_API_KEY is set, else OpenAI, else Ollama. Remote failures fall back to Ollama when LLM_FALLBACK_TO_LOCAL is set.

    When temperature is None we fall back to LLM_TEMPERATURE (a low default) rather than
    the provider default of 1.0, so production generations stay stable instead of
    flip-flopping on borderline retrievals. The eval harness passes temperature=0.0
    explicitly so the faithfulness gate scores a reproducible generation.
    """
    temp = LLM_TEMPERATURE if temperature is None else temperature
    remote = remote_chat()
    if remote:
        provider, api_key, model, chat_url = remote
        label = "xAI" if provider == "xai" else "OpenAI"
        try:
            return await _answer_remote(
                prompt,
                provider=provider,
                api_key=api_key,
                model=model,
                chat_url=chat_url,
                temperature=temp,
            )
        except Exception as e:
            if LLM_FALLBACK_TO_LOCAL:
                logger.warning("%s LLM failed, falling back to local: %s", label, e)
                record_upstream_fallback("llm")
                return await _answer_ollama(prompt, temperature=temp)
            raise
    return await _answer_ollama(prompt, temperature=temp)


async def _answer_remote_stream(
    prompt: str,
    *,
    provider: str,
    api_key: str,
    model: str,
    chat_url: str,
    temperature: float | None = None,
):
    """Stream OpenAI-compatible chat completion content deltas."""
    label = "xAI" if provider == "xai" else "OpenAI"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    client = get_async_client()
    async with client.stream(
        "POST",
        chat_url,
        headers=headers,
        json=payload,
        timeout=LLM_TIMEOUT_SECONDS,
    ) as resp:
        if resp.status_code == 429:
            raise LLMRateLimitedError(f"{label} rate limited")
        if resp.status_code >= 400:
            err_txt = await resp.aread()
            snippet = err_txt[:200].decode(errors="replace") if err_txt else "(empty)"
            raise LLMServiceError(
                f"{label} API error {resp.status_code}: {snippet}"
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


async def answer_with_context_stream(prompt: str, temperature: float | None = None):
    """Async iterator of answer text deltas. Remote chat is streamed; otherwise one chunk from Ollama.

    When temperature is None we fall back to LLM_TEMPERATURE (a low default) so the
    streamed generation users actually see is as stable as the non-stream/eval paths.
    """
    temp = LLM_TEMPERATURE if temperature is None else temperature
    remote = remote_chat()
    if remote:
        provider, api_key, model, chat_url = remote
        label = "xAI" if provider == "xai" else "OpenAI"
        try:
            async for part in _answer_remote_stream(
                prompt,
                provider=provider,
                api_key=api_key,
                model=model,
                chat_url=chat_url,
                temperature=temp,
            ):
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
                logger.warning("%s streaming failed, falling back to local once: %s", label, e)
                record_upstream_fallback("llm")
                text = await _answer_ollama(prompt, temperature=temp)
                if text:
                    yield text
                return
            raise
    text = await _answer_ollama(prompt, temperature=temp)
    if text:
        yield text
