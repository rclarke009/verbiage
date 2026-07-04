"""OpenTelemetry tracing helpers (no Docker or database required)."""

import pytest
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.monitoring.tracing import (
    rag_phase_span,
    set_retrieval_attributes,
    tracing_enabled,
)


@pytest.fixture(scope="module")
def memory_exporter():
    """Capture spans in memory; reuse provider if app.main already called init_tracing."""
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    provider = trace.get_tracer_provider()
    owns_provider = False
    if isinstance(provider, TracerProvider):
        provider.add_span_processor(processor)
    else:
        provider = TracerProvider(resource=Resource.create({"service.name": "test-verbiage"}))
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        owns_provider = True
    yield exporter
    if owns_provider:
        provider.shutdown()


def test_rag_phase_span_disabled_is_noop(monkeypatch):
    monkeypatch.delenv("OTEL_ENABLED", raising=False)
    assert not tracing_enabled()

    with rag_phase_span("embed", endpoint="sync"):
        pass


def test_rag_phase_span_exports_phases(monkeypatch, memory_exporter):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    memory_exporter.clear()

    with rag_phase_span("embed", endpoint="sync"):
        with rag_phase_span("retrieve", endpoint="sync") as retrieve_span:
            set_retrieval_attributes(
                retrieve_span,
                retrieval_mode="hybrid",
                auto_routed=True,
                chunk_count=3,
                top_cosine=0.72,
            )
        with rag_phase_span("llm", endpoint="sync"):
            pass

    names = sorted(s.name for s in memory_exporter.get_finished_spans())
    assert names == ["rag.embed", "rag.llm", "rag.retrieve"]

    retrieve = next(
        s for s in memory_exporter.get_finished_spans() if s.name == "rag.retrieve"
    )
    attrs = dict(retrieve.attributes or {})
    assert attrs["rag.endpoint"] == "sync"
    assert attrs["rag.retrieval_mode"] == "hybrid"
    assert attrs["rag.auto_routed"] is True
    assert attrs["rag.chunk_count"] == 3
    assert attrs["rag.top_cosine"] == 0.72


def test_rag_phase_span_records_exception(monkeypatch, memory_exporter):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    memory_exporter.clear()

    try:
        with rag_phase_span("llm", endpoint="stream"):
            raise RuntimeError("llm down")
    except RuntimeError:
        pass

    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].status.status_code.name == "ERROR"
