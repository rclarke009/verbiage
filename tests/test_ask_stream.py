"""SSE wire contract for POST /ask/stream.

These lock the frames the SPA's useReportSearch hook parses: an `event: error`
frame on a prepare/retrieval failure, and an `event: token` refusal when there is
no relevant context. TestClient is used WITHOUT a context manager so the app
lifespan (and its real DB connection) never runs; with_db_conn_retry is patched.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import app.main as main
from app.auth import get_current_user


def _client() -> TestClient:
    main.app.dependency_overrides[get_current_user] = lambda: "test-user"
    return TestClient(main.app)


def _clear_overrides() -> None:
    main.app.dependency_overrides.pop(get_current_user, None)


def _post_stream(client: TestClient) -> str:
    resp = client.post("/ask/stream", json={"question": "wind damage", "top_k": 5})
    assert resp.status_code == 200
    return resp.text


def test_ask_stream_emits_error_frame_when_prepare_fails():
    """A failure before generation must reach the client as `event: error`."""
    client = _client()
    try:
        with patch.object(
            main, "with_db_conn_retry", new=AsyncMock(side_effect=RuntimeError("boom"))
        ):
            body = _post_stream(client)
    finally:
        _clear_overrides()

    assert "event: error" in body
    assert "retrieval_failed" in body


def test_ask_stream_emits_refusal_token_when_no_context():
    """No relevant chunks -> a token refusal plus an empty sources frame, no error."""
    client = _client()
    rate_limiter = MagicMock()
    # do_prepare returns (rate_limiter, prompt, top_chunks); prompt=None is the
    # "no context" path, which must not call the LLM or the rate limiter.
    prepared = (rate_limiter, None, [])
    try:
        with patch.object(
            main, "with_db_conn_retry", new=AsyncMock(return_value=prepared)
        ):
            body = _post_stream(client)
    finally:
        _clear_overrides()

    assert "event: token" in body
    assert "don't have relevant context" in body
    assert "event: sources" in body
    assert "event: error" not in body
    rate_limiter.acquire.assert_not_called()
