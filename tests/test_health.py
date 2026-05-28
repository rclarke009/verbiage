"""Health endpoints: liveness, readiness (DB), deep (optional upstream)."""

from unittest.mock import AsyncMock, MagicMock, patch

import asyncio

import psycopg2
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.health import (
    build_deep_response,
    build_ready_response,
    check_database,
    check_embed_backend,
)


def _make_request(pool=None):
    request = MagicMock()
    app = MagicMock()
    app.state.db_pool = pool
    request.app = app
    return request


def test_check_database_ok():
    pool = MagicMock()
    conn = MagicMock()
    with patch("app.health.get_valid_conn", return_value=conn):
        ok, msg = check_database(_make_request(pool))
    assert ok is True
    assert msg == "ok"
    pool.putconn.assert_called_once_with(conn)


def test_check_database_no_pool():
    ok, msg = check_database(_make_request(pool=None))
    assert ok is False
    assert "not initialized" in msg


def test_check_database_error():
    pool = MagicMock()
    with patch(
        "app.health.get_valid_conn",
        side_effect=psycopg2.OperationalError("connection refused"),
    ):
        ok, msg = check_database(_make_request(pool))
    assert ok is False
    assert "connection refused" in msg


def test_build_ready_response_200_and_503():
    with patch("app.health.check_database", return_value=(True, "ok")):
        resp = build_ready_response(_make_request())
    assert resp.status_code == 200
    assert resp.body == b'{"ready":true,"checks":{"database":"ok"}}'

    with patch("app.health.check_database", return_value=(False, "down")):
        resp = build_ready_response(_make_request())
    assert resp.status_code == 503
    assert resp.body == b'{"ready":false,"checks":{"database":"down"}}'


def test_build_deep_response_embed_failure():
    with (
        patch("app.health.check_database", return_value=(True, "ok")),
        patch("app.health.check_embed_backend", return_value=(False, "timeout")),
    ):
        resp = asyncio.run(build_deep_response(_make_request()))
    assert resp.status_code == 503
    body = resp.body.decode()
    assert '"healthy":false' in body
    assert '"embed":"timeout"' in body
    assert '"llm":"skipped"' in body


def test_build_deep_response_all_ok():
    with (
        patch("app.health.check_database", return_value=(True, "ok")),
        patch("app.health.check_embed_backend", return_value=(True, "ok")),
    ):
        resp = asyncio.run(build_deep_response(_make_request()))
    assert resp.status_code == 200
    body = resp.body.decode()
    assert '"healthy":true' in body


def test_health_routes_on_minimal_app():
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"healthy": True}

    @app.get("/health/ready")
    def health_ready(request: Request):
        return build_ready_response(request)

    @app.get("/health/deep")
    async def health_deep(request: Request):
        return await build_deep_response(request)

    client = TestClient(app)
    assert client.get("/health").json() == {"healthy": True}

    with patch("app.health.check_database", return_value=(True, "ok")):
        r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["ready"] is True

    with (
        patch("app.health.check_database", return_value=(True, "ok")),
        patch("app.health.check_embed_backend", return_value=(True, "ok")),
    ):
        r = client.get("/health/deep")
    assert r.status_code == 200
    assert r.json()["healthy"] is True


def test_check_embed_backend_ollama_ok():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"embeddings": [[0.1]]}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.health.OPENAI_API_KEY", ""),
        patch("app.health.EMBED_LOCAL_ONLY", False),
        patch("httpx.AsyncClient", return_value=mock_client),
    ):
        ok, msg = asyncio.run(check_embed_backend())
    assert ok is True
    assert msg == "ok"
