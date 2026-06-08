"""Tests for Report Writer graph routing and SSE wire contract."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.auth import get_current_user
from app.report_writer.nodes.gate import gate_retrieval, route_after_gate
from app.report_writer.nodes.normalize import normalize_inputs
from app.report_writer.state import ReportWriterState


def test_normalize_inputs_builds_retrieval_query():
    state: ReportWriterState = {
        "field_notes": "Missing shingles on north slope",
        "property_metadata": {"address": "100 Maple Ct", "property_type": "two-story"},
    }
    out = normalize_inputs(state)
    assert "Missing shingles" in out["retrieval_query"]
    assert "100 Maple Ct" in out["retrieval_query"]


def test_gate_blocks_empty_retrieval():
    state: ReportWriterState = {"retrieved_chunks": []}
    out = gate_retrieval(state)
    assert out["retrieval_passed"] is False
    assert route_after_gate({**state, **out}) == "refuse"


def test_gate_passes_with_chunks():
    state: ReportWriterState = {
        "retrieved_chunks": [{"chunk_id": "c1", "score": 0.7}],
        "best_cosine": 0.7,
    }
    out = gate_retrieval(state)
    assert out["retrieval_passed"] is True
    assert route_after_gate({**state, **out}) == "generate_sections"


def _client() -> TestClient:
    main.app.dependency_overrides[get_current_user] = lambda: "test-user"
    main.app.state.report_writer_graph = MagicMock()
    return TestClient(main.app)


def _clear_overrides() -> None:
    main.app.dependency_overrides.pop(get_current_user, None)


async def _fake_stream(*args, **kwargs):
    yield 'event: run_started\ndata: {"run_id":"r1","claim_id":"c1"}\n\n'
    yield 'event: run_complete\ndata: {"run_id":"r1","status":"completed"}\n\n'


def test_generate_route_returns_sse_when_claim_missing():
    client = _client()
    try:
        with patch("app.report_writer.router._with_conn", new=AsyncMock(return_value=None)):
            resp = client.post("/report-writer/claims/00000000-0000-0000-0000-000000000001/generate", json={})
        assert resp.status_code == 404
    finally:
        _clear_overrides()


def test_stream_graph_events_emits_run_started_and_complete():
    async def _run():
        from app.report_writer.sse import stream_graph_events

        graph = MagicMock()

        async def _astream(*a, **k):
            yield ("updates", {"normalize_inputs": {"retrieval_query": "q"}})

        graph.astream = _astream
        frames = []
        async for frame in stream_graph_events(
            graph,
            {"claim_id": "c1"},
            {"configurable": {"thread_id": "c1"}},
            run_id="r1",
            claim_id="c1",
        ):
            frames.append(frame)
        assert any("event: run_started" in f for f in frames)
        assert any("event: run_complete" in f for f in frames)

    import asyncio

    asyncio.run(_run())
