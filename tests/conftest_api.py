"""Shared helpers for API smoke tests (no real DB, no app lifespan)."""

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

import app.main as main
from app.auth import get_current_user


def api_client() -> TestClient:
    """Authenticated TestClient; lifespan is not started (no pool)."""
    main.app.dependency_overrides[get_current_user] = lambda: "test-user"
    return TestClient(main.app)


def clear_api_overrides() -> None:
    main.app.dependency_overrides.pop(get_current_user, None)


def prime_app_state(app) -> MagicMock:
    """Attach rate_limiter/reranker stubs routes expect on request.app.state."""
    rate_limiter = MagicMock()
    rate_limiter.acquire = AsyncMock()
    app.state.rate_limiter = rate_limiter
    app.state.reranker = MagicMock()
    return rate_limiter


async def run_async_db_fn(_request, async_fn):
    """Patch target for with_db_conn_retry: invoke handler with a mock conn."""
    return await async_fn(MagicMock())


def run_sync_db_fn(_request, sync_fn):
    """Patch target for with_db_conn_retry_sync: invoke handler with a mock conn."""
    return sync_fn(MagicMock())
