"""Tests for Report Writer report type registry and API."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.auth import get_current_user
from app.report_writer.constants import (
    REPORT_TYPES,
    get_report_type,
    section_keys_for_type,
    sections_for_type,
)
from app.report_writer.nodes.generate import generate_sections
from app.report_writer.prompts import build_retrieval_query, build_section_prompt
from app.report_writer.validation import validate_report_type_metadata


def test_each_report_type_has_unique_section_keys_within_type():
    for type_id in REPORT_TYPES:
        keys = section_keys_for_type(type_id)
        assert keys
        assert len(keys) == len(set(keys))


def test_get_report_type_defaults_to_engineering():
    assert get_report_type({}) == "engineering"
    assert get_report_type({"report_type": "roof"}) == "roof"


def test_retrieval_query_includes_type_terms():
    query = build_retrieval_query(
        "Shingle damage on north slope",
        {"report_type": "roof", "address": "100 Main St"},
    )
    assert "roof report" in query
    assert "100 Main St" in query


def test_section_prompt_uses_type_preamble():
    prompt = build_section_prompt(
        "summary",
        "Summary",
        "Brittle test failed",
        {"report_type": "roof"},
        [],
        {},
    )
    assert "roof inspection report" in prompt.lower()
    assert "Summary" in prompt


def test_generate_sections_emits_roof_section_keys():
    import asyncio

    from app.models import RetrievedChunk

    state = {
        "field_notes": "Roof has debris impacts",
        "property_metadata": {"report_type": "roof"},
        "report_type": "roof",
        "sections": {},
        "retrieved_chunks": [{"chunk_id": "c1", "content_snippet": "roof report"}],
        "image_analyses": [],
    }
    fake_chunks = [
        RetrievedChunk(
            chunk_id="c1",
            doc_id="d1",
            score=0.8,
            content_snippet="roof report",
            document_title="Roof Report",
        )
    ]
    mock_deps = MagicMock()
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.getconn.return_value = mock_conn
    mock_deps.db_pool = mock_pool

    with (
        patch("app.report_writer.nodes.generate.get_stream_writer", return_value=None),
        patch("app.report_writer.nodes.generate.get_report_writer_deps", return_value=mock_deps),
        patch("app.report_writer.nodes.generate.HttpEmbedder") as mock_embedder_cls,
        patch(
            "app.report_writer.nodes.generate.retrieve_similar_chunks",
            new=AsyncMock(return_value=(fake_chunks, 0.8)),
        ),
        patch("app.report_writer.nodes.generate.llm_client.answer_with_context_stream") as mock_stream,
    ):
        mock_embedder = mock_embedder_cls.return_value
        mock_embedder.model = "test-model"
        mock_embedder.embed_many = AsyncMock(return_value=[[0.1, 0.2]])

        async def _stream(_prompt):
            yield "Test content."

        mock_stream.side_effect = _stream
        out = asyncio.run(generate_sections(state))

    assert set(out["sections"].keys()) == set(section_keys_for_type("roof"))


def _client() -> TestClient:
    main.app.dependency_overrides[get_current_user] = lambda: "test-user"
    main.app.state.report_writer_graph = MagicMock()
    return TestClient(main.app)


def _clear_overrides() -> None:
    main.app.dependency_overrides.pop(get_current_user, None)


def test_report_types_endpoint():
    client = _client()
    try:
        resp = client.get("/report-writer/report-types")
        assert resp.status_code == 200
        data = resp.json()
        ids = {t["id"] for t in data["report_types"]}
        assert ids == {"engineering", "roof", "window_test"}
        engineering = next(t for t in data["report_types"] if t["id"] == "engineering")
        assert len(engineering["sections"]) == len(sections_for_type("engineering"))
    finally:
        _clear_overrides()


def test_generate_requires_report_type():
    client = _client()
    try:
        claim = {
            "claim_id": "c1",
            "title": "Test",
            "field_notes": "notes",
            "property_metadata": {},
        }
        with patch("app.report_writer.router._with_conn", new=AsyncMock(return_value=(claim, "run-1"))):
            resp = client.post("/report-writer/claims/c1/generate", json={})
        assert resp.status_code == 400
        assert "report_type" in resp.json()["detail"]
    finally:
        _clear_overrides()


def test_validate_report_type_metadata_rejects_unknown():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        validate_report_type_metadata({"report_type": "siding"})
    assert exc.value.status_code == 400
