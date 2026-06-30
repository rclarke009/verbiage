"""Demo mode: config, route gates, per-user Ask quota, open signup safety."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

import app.demo as demo_module
import app.main as main
from app.errors import LLMRateLimitedError
from tests.conftest_api import api_client, clear_api_overrides, prime_app_state, run_async_db_fn


@pytest.fixture(autouse=True)
def reset_demo_state():
    demo_module._ask_timestamps.clear()
    demo_module._signup_timestamps.clear()
    yield
    demo_module._ask_timestamps.clear()
    demo_module._signup_timestamps.clear()


def test_config_includes_demo_fields_when_demo_mode():
    with patch.object(main, "is_demo_mode", return_value=True):
        with patch.object(main, "demo_anonymous_enabled", return_value=True):
            resp = TestClient(main.app).get("/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["demo_mode"] is True
    assert data["demo_anonymous"] is True
    assert data["enabled_tabs"] == ["chat", "preferences"]
    assert "{feature}" in data["demo_gate_message"]
    assert "google_drive_default_folder_id" not in data


def test_config_prod_includes_demo_mode_false():
    with patch.object(main, "is_demo_mode", return_value=False):
        resp = TestClient(main.app).get("/config")
    data = resp.json()
    assert data["demo_mode"] is False
    assert "google_drive_default_folder_id" in data


def test_demo_open_signup_requires_demo_mode():
    with patch.object(demo_module, "DEMO_MODE", False):
        with patch.object(demo_module, "DEMO_OPEN_SIGNUP", True):
            assert demo_module.demo_open_signup_enabled() is False
    with patch.object(demo_module, "DEMO_MODE", True):
        with patch.object(demo_module, "DEMO_OPEN_SIGNUP", True):
            assert demo_module.demo_open_signup_enabled() is True


def test_ingest_forbidden_in_demo():
    client = api_client()
    try:
        with patch.object(main, "is_demo_mode", return_value=True):
            resp = client.post(
                "/ingest",
                json={
                    "doc_id": "x",
                    "title": "t",
                    "source": "upload",
                    "text": "hello",
                },
            )
    finally:
        clear_api_overrides()
    assert resp.status_code == 403


def test_documents_forbidden_in_demo():
    client = api_client()
    try:
        with patch.object(main, "is_demo_mode", return_value=True):
            resp = client.get("/documents")
    finally:
        clear_api_overrides()
    assert resp.status_code == 403


def test_ask_allowed_in_demo():
    client = api_client()
    prime_app_state(main.app)
    try:
        with patch.object(main, "is_demo_mode", return_value=True):
            with patch.object(main, "with_db_conn_retry", side_effect=run_async_db_fn):
                with patch.object(main, "resolve_ask_route", return_value="hybrid"):
                    with patch("app.main.HttpEmbedder") as embed_cls:
                        embed_cls.return_value.embed_many = AsyncMock(return_value=[[0.1] * 768])
                        embed_cls.return_value.model = "test-embed"
                        with patch.object(main, "_retrieve_for_ask", new_callable=AsyncMock) as retrieve:
                            retrieve.return_value = []
                            resp = client.post("/ask", json={"question": "roof damage?"})
    finally:
        clear_api_overrides()
    assert resp.status_code == 200


def test_demo_ask_quota_exceeded():
    req = MagicMock(spec=Request)
    req.client = MagicMock(host="203.0.113.1")
    req.headers = {}

    async def _run():
        with patch.object(demo_module, "DEMO_ASK_LIMIT", 2):
            with patch.object(demo_module, "DEMO_ASK_WINDOW_SECONDS", 3600):
                await demo_module.acquire_demo_ask_quota(req, "user-a")
                await demo_module.acquire_demo_ask_quota(req, "user-a")
                with pytest.raises(LLMRateLimitedError):
                    await demo_module.acquire_demo_ask_quota(req, "user-a")

    asyncio.run(_run())


def test_demo_ask_quota_guest_uses_ip():
    req_a = MagicMock(spec=Request)
    req_a.client = MagicMock(host="203.0.113.1")
    req_a.headers = {}
    req_b = MagicMock(spec=Request)
    req_b.client = MagicMock(host="203.0.113.2")
    req_b.headers = {}

    async def _run():
        with patch.object(demo_module, "DEMO_ASK_LIMIT", 1):
            with patch.object(demo_module, "DEMO_ASK_WINDOW_SECONDS", 3600):
                await demo_module.acquire_demo_ask_quota(req_a, demo_module.DEMO_GUEST_USER_ID)
                await demo_module.acquire_demo_ask_quota(req_b, demo_module.DEMO_GUEST_USER_ID)

    asyncio.run(_run())


def test_anonymous_ask_allowed_in_demo_without_auth():
    client = TestClient(main.app)
    prime_app_state(main.app)
    try:
        with patch("app.auth.is_demo_mode", return_value=True):
            with patch("app.auth.demo_anonymous_enabled", return_value=True):
                with patch.object(main, "with_db_conn_retry", side_effect=run_async_db_fn):
                    with patch.object(main, "resolve_ask_route", return_value="hybrid"):
                        with patch("app.main.HttpEmbedder") as embed_cls:
                            embed_cls.return_value.embed_many = AsyncMock(return_value=[[0.1] * 768])
                            embed_cls.return_value.model = "test-embed"
                            with patch.object(main, "_retrieve_for_ask", new_callable=AsyncMock) as retrieve:
                                retrieve.return_value = []
                                resp = client.post("/ask", json={"question": "roof damage?"})
    finally:
        clear_api_overrides()
    assert resp.status_code == 200


def test_demo_ask_quota_returns_429_on_ask():
    client = api_client()
    prime_app_state(main.app)
    try:
        with patch.object(main, "is_demo_mode", return_value=True):
            with patch.object(main, "acquire_demo_ask_quota", new_callable=AsyncMock) as quota:
                quota.side_effect = LLMRateLimitedError("Demo limit reached")
                resp = client.post("/ask", json={"question": "roof damage?"})
    finally:
        clear_api_overrides()
    assert resp.status_code == 429
    assert "Demo limit" in resp.json()["detail"]
