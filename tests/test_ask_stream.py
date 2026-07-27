"""SSE wire contract for POST /ask/stream.

These lock the frames the SPA's useReportSearch hook parses: an `event: error`
frame on a prepare/retrieval failure, and sources+token frames for refusals and
answers (including optional retrieval_debug after rewrite-once). TestClient is
used WITHOUT a context manager so the app lifespan (and its real DB connection)
never runs; with_db_conn_retry is patched.
"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import app.main as main
from app.auth import get_ask_user, get_current_user
from app.models import RetrievalDebug


def _client() -> TestClient:
    def _test_user() -> str:
        return "test-user"

    main.app.dependency_overrides[get_current_user] = _test_user
    main.app.dependency_overrides[get_ask_user] = _test_user
    return TestClient(main.app)


def _clear_overrides() -> None:
    main.app.dependency_overrides.pop(get_current_user, None)
    main.app.dependency_overrides.pop(get_ask_user, None)


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
    """No relevant chunks -> sources then a token refusal, no error."""
    client = _client()
    # do_prepare returns (kind, answer, top_chunks, retrieval_debug)
    prepared = (
        "rag",
        "I don't have relevant context to answer that question.",
        [],
        None,
    )
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


def test_ask_stream_includes_retrieval_debug_when_rewrite_ran():
    client = _client()
    debug = RetrievalDebug(
        retried=True,
        original_query="Which tile-roof properties had intact roof tiles?",
        rewritten_query="intact roof tiles. No storm-created opening was identified",
    )
    prepared = ("rag", "412 Example Drive had intact tiles.", [], debug)
    try:
        with patch.object(
            main, "with_db_conn_retry", new=AsyncMock(return_value=prepared)
        ):
            body = _post_stream(client)
    finally:
        _clear_overrides()

    assert "retrieval_debug" in body
    assert "rewritten_query" in body
    assert "intact roof tiles" in body
