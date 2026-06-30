"""
Demo deployment helpers: mode detection, per-user Ask quota, signup IP throttle, route gates.

DEMO_OPEN_SIGNUP and other demo-only behavior require DEMO_MODE=1 (prevents accidental prod misconfig).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import (
    DEMO_ASK_LIMIT,
    DEMO_ASK_WINDOW_SECONDS,
    DEMO_GATE_MESSAGE_TEMPLATE,
    DEMO_MODE,
    DEMO_OPEN_SIGNUP,
    DEMO_ANONYMOUS,
    DEMO_SIGNUP_LIMIT,
    DEMO_SIGNUP_WINDOW_SECONDS,
)
from app.errors import LLMRateLimitedError

logger = logging.getLogger(__name__)

_DEMO_ENABLED_TABS = ("chat", "preferences")
DEMO_GUEST_USER_ID = "demo-guest"

# Per-user Ask timestamps (demo only; in-memory, single worker).
_ask_timestamps: dict[str, deque[float]] = defaultdict(deque)
_ask_lock = asyncio.Lock()

# Signup attempts per client IP (demo only).
_signup_timestamps: dict[str, deque[float]] = defaultdict(deque)
_signup_lock = asyncio.Lock()


def is_demo_mode() -> bool:
    return DEMO_MODE


def demo_open_signup_enabled() -> bool:
    return DEMO_MODE and DEMO_OPEN_SIGNUP


def demo_anonymous_enabled() -> bool:
    """Skip sign-in on demo; Ask uses IP-based rate limits. Requires DEMO_MODE=1."""
    return DEMO_MODE and DEMO_ANONYMOUS


def demo_enabled_tabs() -> list[str]:
    return list(_DEMO_ENABLED_TABS)


def demo_gate_message_for(feature_name: str) -> str:
    return DEMO_GATE_MESSAGE_TEMPLATE.format(feature=feature_name)


def _client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def _prune_and_count(
    store: dict[str, deque[float]],
    key: str,
    window_seconds: int,
    lock: asyncio.Lock,
) -> int:
    now = time.monotonic()
    cutoff = now - window_seconds
    async with lock:
        q = store[key]
        while q and q[0] < cutoff:
            q.popleft()
        return len(q)


async def _record_event(
    store: dict[str, deque[float]],
    key: str,
    lock: asyncio.Lock,
) -> None:
    now = time.monotonic()
    async with lock:
        store[key].append(now)


async def check_demo_signup_allowed(request: Request) -> None:
    """Raise 429 when too many signups from the same IP in the demo window."""
    ip = _client_ip(request)
    count = await _prune_and_count(
        _signup_timestamps, ip, DEMO_SIGNUP_WINDOW_SECONDS, _signup_lock
    )
    if count >= DEMO_SIGNUP_LIMIT:
        logger.warning("demo signup rate limit exceeded for ip=%s", ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many sign-up attempts from this network. Try again later.",
        )
    await _record_event(_signup_timestamps, ip, _signup_lock)


async def acquire_demo_ask_quota(request: Request, user_id: str) -> None:
    """Consume one Ask slot; anonymous guests are keyed by client IP."""
    key = f"ip:{_client_ip(request)}" if user_id == DEMO_GUEST_USER_ID else user_id
    count = await _prune_and_count(
        _ask_timestamps, key, DEMO_ASK_WINDOW_SECONDS, _ask_lock
    )
    if count >= DEMO_ASK_LIMIT:
        logger.info("demo ask quota exceeded key=%s", key)
        raise LLMRateLimitedError(
            f"Demo limit reached ({DEMO_ASK_LIMIT} searches per hour). Try again later."
        )
    await _record_event(_ask_timestamps, key, _ask_lock)


def demo_forbidden() -> None:
    """Raise 403 for routes disabled in demo mode."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="This feature is not available in the demo.",
    )
