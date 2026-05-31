"""
Health probes: liveness (/health), readiness (DB), deep (DB + embed + optional LLM).
"""

from __future__ import annotations

import httpx
import psycopg2
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.config import (
    EMBED_BASE_URL,
    EMBED_LOCAL_ONLY,
    EMBED_MODEL,
    HEALTH_DEEP_CHECK_LLM,
    HEALTH_DEEP_TIMEOUT,
    LLM_BASE_URL,
    OPENAI_API_KEY,
)
from app.db import get_valid_conn
from app.embeddings_openai import (
    OPENAI_EMBED_DIMENSIONS,
    OPENAI_EMBED_MODEL,
    OPENAI_EMBED_URL,
)

OPENAI_MODELS_URL = "https://api.openai.com/v1/models"


def check_database(request: Request) -> tuple[bool, str]:
    """Validate Postgres via pool + SELECT 1 (get_valid_conn)."""
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        return False, "database pool not initialized"
    conn = None
    try:
        conn = get_valid_conn(pool)
        return True, "ok"
    except psycopg2.Error as e:
        return False, str(e).split("\n")[0][:200]
    finally:
        if conn is not None:
            pool.putconn(conn)


async def check_embed_backend() -> tuple[bool, str]:
    """One-shot embed probe; no retries. Uses OpenAI or Ollama per app config."""
    use_openai = bool(OPENAI_API_KEY) and not EMBED_LOCAL_ONLY
    timeout = HEALTH_DEEP_TIMEOUT
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if use_openai:
                response = await client.post(
                    OPENAI_EMBED_URL,
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": OPENAI_EMBED_MODEL,
                        "input": ["x"],
                        "dimensions": OPENAI_EMBED_DIMENSIONS,
                    },
                )
            else:
                response = await client.post(
                    f"{EMBED_BASE_URL.rstrip('/')}/api/embed",
                    headers={"Content-Type": "application/json"},
                    json={"model": EMBED_MODEL, "input": ["x"]},
                )
    except httpx.TimeoutException:
        return False, "timeout"
    except httpx.RequestError as e:
        return False, str(e).split("\n")[0][:200]

    if response.status_code == 429:
        return False, "rate limited"
    if response.status_code >= 400:
        return False, f"HTTP {response.status_code}"
    try:
        data = response.json()
    except ValueError:
        return False, "invalid JSON response"
    if use_openai:
        if not data.get("data"):
            return False, "unexpected OpenAI response"
    elif not (data.get("embeddings") or data.get("embedding") is not None):
        return False, "unexpected embed response"
    return True, "ok"


async def check_llm_backend() -> tuple[bool, str]:
    """Optional LLM reachability; no retries."""
    timeout = HEALTH_DEEP_TIMEOUT
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if OPENAI_API_KEY:
                response = await client.get(
                    OPENAI_MODELS_URL,
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                )
            else:
                response = await client.get(f"{LLM_BASE_URL.rstrip('/')}/api/tags")
    except httpx.TimeoutException:
        return False, "timeout"
    except httpx.RequestError as e:
        return False, str(e).split("\n")[0][:200]

    if response.status_code == 429:
        return False, "rate limited"
    if response.status_code >= 400:
        return False, f"HTTP {response.status_code}"
    return True, "ok"


def check_reranker(request: Request) -> tuple[bool, str]:
    """Not-ready while the cross-encoder is still warming up at startup.

    Keeps the platform from routing traffic to a process that would otherwise have
    to load the (memory-heavy) reranker model on the request path. Treated as ready
    unless ``app.state.reranker_ready`` is explicitly False (disabled/loaded => ready).
    """
    ready = getattr(request.app.state, "reranker_ready", True)
    if ready is False:
        return False, "warming up"
    return True, "ok"


def build_ready_response(request: Request) -> JSONResponse:
    db_ok, db_msg = check_database(request)
    rr_ok, rr_msg = check_reranker(request)
    ok = db_ok and rr_ok
    body = {"ready": ok, "checks": {"database": db_msg, "reranker": rr_msg}}
    return JSONResponse(status_code=200 if ok else 503, content=body)


async def build_deep_response(request: Request) -> JSONResponse:
    checks: dict[str, str] = {}

    db_ok, db_msg = check_database(request)
    checks["database"] = db_msg

    embed_ok, embed_msg = await check_embed_backend()
    checks["embed"] = embed_msg

    if HEALTH_DEEP_CHECK_LLM:
        llm_ok, llm_msg = await check_llm_backend()
        checks["llm"] = llm_msg
    else:
        llm_ok = True
        checks["llm"] = "skipped"

    all_ok = db_ok and embed_ok and llm_ok
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"healthy": all_ok, "checks": checks},
    )
