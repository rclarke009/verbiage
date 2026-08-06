"""Unit tests for structured ask-run logging / decision classification."""

import json
import logging

from app.corrective import SOFT_REFUSE_CANARY
from app.models import RetrievedChunk
from app.monitoring.ask_run_log import (
    AskRunBuilder,
    HARD_REFUSE_CANARY,
    ask_run_log_payload,
    build_ask_run_summary,
    emit_ask_run,
)


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="c1",
        doc_id="d1",
        score=0.77,
        content_snippet="Hail damaged the tile roof at the property.",
        document_title="Gulfview Report",
        source="eval_fixture",
    )


def test_classify_hard_refuse():
    b = AskRunBuilder(
        answer=HARD_REFUSE_CANARY,
        chunks=[],
        gate_blocked=True,
        top_cosine=0.42,
    )
    assert b.classify_decision() == "hard_refuse"
    summary = build_ask_run_summary(b)
    assert summary.decision == "hard_refuse"
    assert summary.refused_hard is True
    assert summary.gate is not None
    assert summary.gate.blocked is True


def test_classify_soft_refuse():
    b = AskRunBuilder(answer=SOFT_REFUSE_CANARY, chunks=[_chunk()], top_cosine=0.6)
    assert b.classify_decision() == "soft_refuse"
    summary = build_ask_run_summary(b)
    assert summary.soft_refuse is True
    assert summary.chunks[0].chunk_id == "c1"
    assert summary.chunks[0].snippet is None  # not verbose on API summary


def test_classify_answer():
    b = AskRunBuilder(answer="Hail struck the tiles.", chunks=[_chunk()])
    assert b.classify_decision() == "answer"


def test_emit_ask_run_json_line(caplog, monkeypatch):
    monkeypatch.setattr("app.monitoring.ask_run_log.ASK_RUN_LOG_ENABLED", True)
    monkeypatch.setattr("app.monitoring.ask_run_log.ASK_RUN_LOG_VERBOSE", False)
    b = AskRunBuilder(
        answer="Hail struck the tiles.",
        chunks=[_chunk()],
        prompt_text="Context:\n[doc]\n\nQuestion: hail?",
        embed_model="test-embed",
        endpoint="sync",
        retrieval_mode="hybrid",
        top_cosine=0.7,
    )
    with caplog.at_level(logging.INFO, logger="app.monitoring.ask_run_log"):
        summary = emit_ask_run(b)
    assert summary.decision == "answer"
    assert summary.prompt is not None
    assert summary.prompt.chars > 0
    assert summary.models is not None
    lines = [r.getMessage() for r in caplog.records if "ask_run" in r.getMessage()]
    assert lines
    payload = json.loads(lines[0])
    assert payload["event"] == "ask_run"
    assert payload["decision"] == "answer"
    assert "question_preview" not in payload or payload.get("question_preview") is None
    assert "snippet" not in payload["chunks"][0]


def test_verbose_log_includes_snippet_preview(monkeypatch):
    monkeypatch.setattr("app.monitoring.ask_run_log.ASK_RUN_LOG_VERBOSE", True)
    b = AskRunBuilder(
        answer="ok",
        chunks=[_chunk()],
        question="What hail damage was found?",
        decision="answer",
    )
    summary = build_ask_run_summary(b)
    payload = ask_run_log_payload(summary, b)
    assert payload["chunks"][0]["snippet"]
    assert payload["question_preview"].startswith("What hail")
