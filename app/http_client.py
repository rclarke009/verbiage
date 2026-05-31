"""
Process-wide shared async HTTP client.

httpx.AsyncClient owns a connection pool with keep-alive sockets, so reusing one client
across requests avoids a fresh TCP + TLS handshake on every embedding / LLM call. The
client is created lazily and bound to the running event loop; it is recreated if that loop
changed (pytest tears the loop down between async cases) or if it was closed. Per-request
timeouts are passed at each call site, so the shared client is created without a global one.
"""

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

# Bound the pool so a burst of concurrent /ask + ingest calls can't open unbounded sockets,
# while keeping enough keep-alive connections to amortize handshakes to OpenAI/Ollama.
_DEFAULT_LIMITS = httpx.Limits(max_connections=100, max_keepalive_connections=20)

_client: httpx.AsyncClient | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


def get_async_client() -> httpx.AsyncClient:
    """Return the shared AsyncClient bound to the running event loop.

    Reuses keep-alive connections across calls. Recreates the client when it was closed
    or the running event loop changed. Pass ``timeout=`` on each request.
    """
    global _client, _client_loop
    loop = asyncio.get_running_loop()
    if _client is None or _client.is_closed or _client_loop is not loop:
        _client = httpx.AsyncClient(limits=_DEFAULT_LIMITS)
        _client_loop = loop
        logger.info("Created shared httpx.AsyncClient")
    return _client


async def aclose_async_client() -> None:
    """Close the shared client if open. Call on app shutdown."""
    global _client, _client_loop
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        logger.info("Closed shared httpx.AsyncClient")
    _client = None
    _client_loop = None
