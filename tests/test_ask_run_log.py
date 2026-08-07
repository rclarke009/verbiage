"""Unit tests for structured ask-run logging / decision classification."""

import json
import logging

from app.corrective import SOFT_REFUSE_CANARY
from app.models import RetrievedChunk
from app.monitoring.ask_run_buffer import (
    buffer_size,
    get_ask_run_trace,
    list_ask_run_traces,
    reset_buffer,
)
from app.monitoring.ask_run_log import (
    AskRunBuilder,
    HARD_REFUSE_CANARY,
    ask_debug_scope,
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
    monkeypatch.setattr("app.monitoring.ask_run_buffer.ASK_RUN_BUFFER_ENABLED", True)
    reset_buffer(maxlen=10)
    b = AskRunBuilder(
        answer="Hail struck the tiles.",
        chunks=[_chunk()],
        prompt_text="Context:\n[doc]\n\nQuestion: hail?",
        embed_model="test-embed",
        endpoint="sync",
        retrieval_mode="hybrid",
        top_cosine=0.7,
        question="What about hail?",
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
    # Buffer always gets rich previews even when log is compact
    buffered = get_ask_run_trace(summary.ask_run_id)
    assert buffered is not None
    assert buffered["question_preview"].startswith("What about")
    assert buffered["answer_preview"].startswith("Hail struck")
    assert buffered["chunks"][0]["snippet"]


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


def test_request_scoped_debug_enables_verbose(monkeypatch):
    monkeypatch.setattr("app.monitoring.ask_run_log.ASK_RUN_LOG_VERBOSE", False)
    b = AskRunBuilder(
        answer="ok",
        chunks=[_chunk()],
        question="What hail damage was found?",
        decision="answer",
    )
    with ask_debug_scope(False):
        summary_off = build_ask_run_summary(b)
        payload_off = ask_run_log_payload(summary_off, b)
    assert summary_off.question_preview is None
    assert "snippet" not in payload_off["chunks"][0]

    with ask_debug_scope(True):
        summary_on = build_ask_run_summary(b)
        payload_on = ask_run_log_payload(summary_on, b)
    assert summary_on.question_preview and summary_on.question_preview.startswith("What hail")
    assert payload_on["chunks"][0]["snippet"]


def test_ring_buffer_retains_and_overwrites(monkeypatch):
    monkeypatch.setattr("app.monitoring.ask_run_buffer.ASK_RUN_BUFFER_ENABLED", True)
    reset_buffer(maxlen=2)
    for i in range(3):
        b = AskRunBuilder(
            ask_run_id=f"run-{i}",
            answer=f"answer {i}",
            chunks=[_chunk()],
            question=f"question {i}",
            decision="answer",
        )
        emit_ask_run(b)
    assert buffer_size() == 2
    ids = [r["ask_run_id"] for r in list_ask_run_traces()]
    assert ids == ["run-2", "run-1"]  # newest first; run-0 dropped
    assert get_ask_run_trace("run-0") is None
    assert get_ask_run_trace("run-2") is not None


def test_ring_buffer_disabled_skips_push(monkeypatch):
    monkeypatch.setattr("app.monitoring.ask_run_buffer.ASK_RUN_BUFFER_ENABLED", False)
    reset_buffer(maxlen=10)
    emit_ask_run(
        AskRunBuilder(answer="x", chunks=[], decision="hard_refuse", question="q")
    )
    assert buffer_size() == 0


def test_request_wants_ask_debug_query_and_header():
    from starlette.requests import Request
    from app.monitoring.ask_run_log import request_wants_ask_debug

    def _req(*, query: str = "", headers: dict | None = None) -> Request:
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "path": "/ask",
            "raw_path": b"/ask",
            "root_path": "",
            "scheme": "http",
            "server": ("test", 80),
            "client": ("test", 123),
            "headers": [
                (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
            ],
            "query_string": query.encode(),
        }
        return Request(scope)

    assert request_wants_ask_debug(_req()) is False
    assert request_wants_ask_debug(_req(query="debug=1")) is True
    assert request_wants_ask_debug(_req(query="debug=true")) is True
    assert request_wants_ask_debug(_req(query="debug=0")) is False
    assert request_wants_ask_debug(_req(headers={"x-verbiage-debug": "1"})) is True
    assert request_wants_ask_debug(_req(headers={"X-Verbiage-Debug": "yes"})) is True
