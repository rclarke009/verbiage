"""Demo mode: config, route gates, per-user Ask quota, open signup safety."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

import app.demo as demo_module
import app.main as main
from app.errors import LLMRateLimitedError
from app.monitoring.ask_run_log import RetrieveOutcome
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
        with patch.object(main, "dual_tenant_enabled", return_value=False):
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
        with patch.object(main, "dual_tenant_enabled", return_value=False):
            resp = TestClient(main.app).get("/config")
    data = resp.json()
    assert data["demo_mode"] is False
    assert "google_drive_default_folder_id" in data


def test_config_dual_tenant_includes_auth_and_guest_flags():
    with patch.object(main, "is_demo_mode", return_value=False):
        with patch.object(main, "dual_tenant_enabled", return_value=True):
            with patch.object(main, "demo_anonymous_enabled", return_value=True):
                resp = TestClient(main.app).get("/config")
    data = resp.json()
    assert data["demo_mode"] is False
    assert data["demo_anonymous"] is True
    assert data["enabled_tabs"] == ["chat", "preferences"]
    assert "google_drive_default_folder_id" in data


def test_is_demo_only_service_false_when_dual_tenant():
    with patch.object(demo_module, "DEMO_MODE", True):
        with patch.object(demo_module, "dual_tenant_enabled", return_value=True):
            assert demo_module.is_demo_only_service() is False
    with patch.object(demo_module, "DEMO_MODE", True):
        with patch.object(demo_module, "dual_tenant_enabled", return_value=False):
            assert demo_module.is_demo_only_service() is True


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
        with patch.object(main, "is_demo_only_service", return_value=True):
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


def test_block_in_demo_skips_dual_tenant():
    with patch.object(main, "is_demo_only_service", return_value=False):
        main.block_in_demo()
    with patch.object(main, "is_demo_only_service", return_value=True):
        with pytest.raises(Exception) as exc:
            main.block_in_demo()
    assert getattr(exc.value, "status_code", None) == 403


def test_documents_forbidden_in_demo():
    client = api_client()
    try:
        with patch.object(main, "is_demo_only_service", return_value=True):
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
                            retrieve.return_value = RetrieveOutcome(chunks=[])
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
        with patch("app.auth.demo_anonymous_enabled", return_value=True):
            with patch.object(main, "with_db_conn_retry", side_effect=run_async_db_fn):
                with patch.object(main, "resolve_ask_route", return_value="hybrid"):
                    with patch("app.main.HttpEmbedder") as embed_cls:
                        embed_cls.return_value.embed_many = AsyncMock(return_value=[[0.1] * 768])
                        embed_cls.return_value.model = "test-embed"
                        with patch.object(main, "_retrieve_for_ask", new_callable=AsyncMock) as retrieve:
                            retrieve.return_value = RetrieveOutcome(chunks=[])
                            resp = client.post("/ask", json={"question": "roof damage?"})
    finally:
        clear_api_overrides()
    assert resp.status_code == 200


def test_ask_with_invalid_token_is_401_not_guest():
    client = TestClient(main.app)
    prime_app_state(main.app)
    try:
        with patch("app.auth.demo_anonymous_enabled", return_value=True):
            with patch("app.auth._auth_configured", return_value=True):
                resp = client.post(
                    "/ask",
                    json={"question": "roof damage?"},
                    headers={"Authorization": "Bearer not-a-jwt"},
                )
    finally:
        clear_api_overrides()
    assert resp.status_code == 401
    client = api_client()
    prime_app_state(main.app)
    try:
        with patch.object(main, "is_demo_only_service", return_value=True):
            with patch.object(main, "acquire_demo_ask_quota", new_callable=AsyncMock) as quota:
                quota.side_effect = LLMRateLimitedError("Demo limit reached")
                resp = client.post("/ask", json={"question": "roof damage?"})
    finally:
        clear_api_overrides()
    assert resp.status_code == 429
    assert "Demo limit" in resp.json()["detail"]


def test_ingest_without_auth_is_401_not_demo_forbidden():
    client = TestClient(main.app)
    try:
        with patch.object(main, "is_demo_mode", return_value=False):
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
    assert resp.status_code in (401, 503)


def test_get_ask_user_with_bearer_sets_prod_tenant():
    from fastapi import Request

    from app.auth import get_ask_user

    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.headers = {"authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.e30.x"}
    creds = MagicMock()
    creds.credentials = "eyJhbGciOiJIUzI1NiJ9.e30.x"

    with patch("app.auth.demo_anonymous_enabled", return_value=True):
        with patch("app.auth.get_current_user", return_value="user-1") as current:
            user_id = get_ask_user(req, creds)
    assert user_id == "user-1"
    current.assert_called_once()


def test_get_ask_user_without_bearer_is_guest():
    from fastapi import Request

    from app.auth import get_ask_user
    from app.demo import DEMO_GUEST_USER_ID

    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.headers = {}

    with patch("app.auth.demo_anonymous_enabled", return_value=True):
        user_id = get_ask_user(req, None)
    assert user_id == DEMO_GUEST_USER_ID
    assert req.state.db_tenant == "demo"
    req = MagicMock()
    req.state.db_tenant = "demo"
    demo = object()
    prod = object()
    req.app.state.demo_db_pool = demo
    req.app.state.db_pool = prod
    assert main.pool_for_request(req) is demo
    req.state.db_tenant = "prod"
    assert main.pool_for_request(req) is prod


def test_assert_demo_database_config_dual_tenant_allows_google():
    from app.demo_database import assert_demo_database_config

    demo_url = "postgresql://postgres.zhahqzozdngghmvbeaxx:secret@aws-0-us-west-2.pooler.supabase.com:5432/postgres"
    live_url = "postgresql://postgres.dunxzvbxekxqrfnmtzmj:secret@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    with patch("app.demo_database.dual_tenant_enabled", return_value=True):
        with patch("app.demo_database.DEMO_DATABASE_URL", demo_url):
            with patch("app.demo_database.DATABASE_URL", live_url):
                with patch("app.demo_database.PROD_SUPABASE_PROJECT_REF", "dunxzvbxekxqrfnmtzmj"):
                    with patch("app.demo_database.GOOGLE_REFRESH_TOKEN", "token"):
                        assert_demo_database_config()


def test_assert_demo_database_config_dual_tenant_blocks_prod_demo_url():
    from app.demo_database import assert_demo_database_config

    bad = "postgresql://postgres.dunxzvbxekxqrfnmtzmj:secret@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    live_url = "postgresql://postgres.dunxzvbxekxqrfnmtzmj:secret@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    with patch("app.demo_database.dual_tenant_enabled", return_value=True):
        with patch("app.demo_database.DEMO_DATABASE_URL", bad):
            with patch("app.demo_database.DATABASE_URL", live_url):
                with patch("app.demo_database.PROD_SUPABASE_PROJECT_REF", "dunxzvbxekxqrfnmtzmj"):
                    with pytest.raises(RuntimeError, match="DEMO_DATABASE_URL"):
                        assert_demo_database_config()


def test_assert_demo_database_config_dual_tenant_blocks_demo_as_live_url():
    from app.demo_database import assert_demo_database_config

    demo_url = "postgresql://postgres.zhahqzozdngghmvbeaxx:secret@aws-0-us-west-2.pooler.supabase.com:5432/postgres"
    with patch("app.demo_database.dual_tenant_enabled", return_value=True):
        with patch("app.demo_database.DEMO_DATABASE_URL", demo_url):
            with patch("app.demo_database.DATABASE_URL", demo_url):
                with patch("app.demo_database.PROD_SUPABASE_PROJECT_REF", "dunxzvbxekxqrfnmtzmj"):
                    with pytest.raises(RuntimeError, match="DATABASE_URL"):
                        assert_demo_database_config()


def test_extract_supabase_project_ref_from_database_url():
    from app.demo_database import extract_supabase_project_ref_from_database_url

    url = "postgresql://postgres.abc123xyz:secret@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    assert extract_supabase_project_ref_from_database_url(url) == "abc123xyz"


def test_extract_supabase_project_ref_from_supabase_url():
    from app.demo_database import extract_supabase_project_ref_from_supabase_url

    assert extract_supabase_project_ref_from_supabase_url("https://abc123xyz.supabase.co") == "abc123xyz"


def test_assert_demo_database_config_blocks_prod_ref():
    from app.demo_database import assert_demo_database_config

    db_url = "postgresql://postgres.prodref:secret@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    with patch("app.demo_database.DEMO_MODE", True):
        with patch("app.demo_database.DATABASE_URL", db_url):
            with patch("app.demo_database.PROD_SUPABASE_PROJECT_REF", "prodref"):
                with patch("app.demo_database.SUPABASE_URL", "https://demoref.supabase.co"):
                    with patch("app.demo_database.GOOGLE_REFRESH_TOKEN", ""):
                        with pytest.raises(RuntimeError, match="production Supabase project"):
                            assert_demo_database_config()


def test_assert_demo_database_config_blocks_google_refresh_token():
    from app.demo_database import assert_demo_database_config

    with patch("app.demo_database.DEMO_MODE", True):
        with patch("app.demo_database.GOOGLE_REFRESH_TOKEN", "token"):
            with pytest.raises(RuntimeError, match="GOOGLE_REFRESH_TOKEN"):
                assert_demo_database_config()


def test_assert_demo_database_content_blocks_non_eval_fixture():
    from app.demo_database import assert_demo_database_content

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchall.return_value = [("google_drive", 12)]

    with patch("app.demo_database.DEMO_MODE", True):
        with pytest.raises(RuntimeError, match="non-synthetic documents"):
            assert_demo_database_content(conn)


def test_assert_demo_database_content_allows_eval_fixture_only():
    from app.demo_database import assert_demo_database_content

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchall.return_value = []

    with patch("app.demo_database.DEMO_MODE", True):
        assert_demo_database_content(conn)


def test_assert_live_database_content_blocks_eval_fixture_only():
    from app.demo_database import assert_live_database_content

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = (12, 0)

    with patch("app.demo_database.dual_tenant_enabled", return_value=True):
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            assert_live_database_content(conn)


def test_assert_live_database_content_allows_real_docs():
    from app.demo_database import assert_live_database_content

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = (0, 225)

    with patch("app.demo_database.dual_tenant_enabled", return_value=True):
        assert_live_database_content(conn)
