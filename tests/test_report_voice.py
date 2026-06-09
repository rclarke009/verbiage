"""Tests for Report Writer voice, terminology, and section retrieval."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from app.models import RetrievedChunk
from app.report_writer.constants import (
    section_outline_for,
    section_retrieval_extra_for,
    terminology_rules_for,
)
from app.report_writer.nodes.generate import generate_sections
from app.report_writer.prompts import (
    build_section_prompt,
    build_section_retrieval_query,
    build_validate_prompt,
)
from app.report_writer.retrieval import filter_chunks_for_report_type


def test_section_retrieval_query_includes_section_terms():
    query = build_section_retrieval_query(
        "conclusion",
        "Brittle test failed on north slope",
        {"report_type": "roof", "address": "67 Washington Terrace"},
    )
    assert "section: Conclusion" in query
    assert "brittle test" in query.lower()
    assert "67 Washington Terrace" in query


def test_roof_conclusion_prompt_includes_terminology_and_outline():
    prompt = build_section_prompt(
        "conclusion",
        "Conclusion",
        "Brittle test failed; torn shingles observed",
        {"report_type": "roof", "storm_name": "Ian"},
        [{"chunk_id": "c1", "content_snippet": "roof report conclusion replacement"}],
        {"recommendations": {"content": "Full roof replacement recommended."}},
        report_type="roof",
    )
    assert "Terminology rules:" in prompt
    assert "structural integrity" in prompt
    assert "Vocabulary contract:" in prompt
    assert "reuse their terminology verbatim" in prompt.lower()
    assert "brittle test failed" in prompt.lower()
    outline = section_outline_for("roof", "conclusion")
    assert outline[:20] in prompt


def test_validate_prompt_checks_terminology():
    prompt = build_validate_prompt(
        {"conclusion": {"content": "Shingles lost structural integrity."}},
        "Brittle test failed",
        report_type="roof",
    )
    assert "structural integrity" in prompt
    assert "Terminology rules:" in prompt
    assert any("brittle" in rule.lower() for rule in terminology_rules_for("roof"))


def test_filter_chunks_for_report_type_prefers_matching_titles():
    chunks = [
        RetrievedChunk(
            chunk_id="1",
            doc_id="d1",
            score=0.9,
            content_snippet="engineering structural assessment",
            document_title="Engineering Storm Report",
        ),
        RetrievedChunk(
            chunk_id="2",
            doc_id="d2",
            score=0.8,
            content_snippet="brittle test failed replacement",
            document_title="Roof Report - Smith",
        ),
        RetrievedChunk(
            chunk_id="3",
            doc_id="d3",
            score=0.7,
            content_snippet="roof inspection conclusion",
            document_title="Roof Inspection 2023",
        ),
        RetrievedChunk(
            chunk_id="4",
            doc_id="d4",
            score=0.6,
            content_snippet="conclusion wind damage",
            document_title="Roof Report 2024",
        ),
    ]
    filtered = filter_chunks_for_report_type(chunks, "roof")
    titles = [c.document_title for c in filtered]
    assert all("roof" in (t or "").lower() for t in titles)
    assert "Engineering Storm Report" not in titles


def test_filter_chunks_falls_back_when_too_few_matches():
    chunks = [
        RetrievedChunk(
            chunk_id="1",
            doc_id="d1",
            score=0.9,
            content_snippet="generic storm damage",
            document_title="Storm Report",
        ),
    ]
    assert filter_chunks_for_report_type(chunks, "roof") == chunks


def test_section_retrieval_extra_for_roof_conclusion():
    extra = section_retrieval_extra_for("roof", "conclusion")
    assert "conclusion" in extra
    assert "brittle test" in extra


def test_generate_sections_uses_per_section_retrieval():
    import asyncio

    state = {
        "field_notes": "Roof has debris impacts; brittle test failed",
        "property_metadata": {"report_type": "roof"},
        "report_type": "roof",
        "sections": {},
        "image_analyses": [],
    }
    fake_chunks = [
        RetrievedChunk(
            chunk_id="c1",
            doc_id="d1",
            score=0.8,
            content_snippet="roof conclusion brittle",
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
        ) as mock_retrieve,
        patch("app.report_writer.nodes.generate.llm_client.answer_with_context_stream") as mock_stream,
    ):
        mock_embedder = mock_embedder_cls.return_value
        mock_embedder.model = "test-model"
        mock_embedder.embed_many = AsyncMock(return_value=[[0.1, 0.2]])

        async def _stream(_prompt):
            yield "Test content."

        mock_stream.side_effect = _stream
        out = asyncio.run(generate_sections(state))

    assert set(out["sections"].keys()) == {"summary", "areas_of_concern", "recommendations", "conclusion"}
    assert mock_retrieve.await_count == 4
    conclusion_call = mock_retrieve.await_args_list[-1]
    assert "roof report conclusion" in conclusion_call.args[1].lower()
