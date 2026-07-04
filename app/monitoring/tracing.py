"""
OpenTelemetry tracing for the RAG stack.

How this fits with Prometheus (app/monitoring/metrics.py):
  - Metrics = aggregates over time ("p95 embed latency across all /ask requests").
  - Traces = one request's span tree ("this slow /ask spent 4s in rag.llm, 0.2s in rag.retrieve").
  We keep both: metrics for dashboards/alerts, traces for debugging individual requests.

Span naming mirrors Prometheus rag_phase_seconds labels: rag.embed, rag.retrieve, rag.rerank, rag.llm.

Design choices:
  - OTEL_ENABLED gates everything (default off) so tests and prod without a collector pay zero cost.
  - FastAPIInstrumentor creates the HTTP parent span; HTTPXClientInstrumentor adds child spans
    for OpenAI/Ollama calls inside llm_client and embedders without editing those files.
  - Manual rag_phase_span() wraps phases metrics already time — same boundaries, two signals.
  - Attributes are low-cardinality only (no question text, doc IDs, or chunk content — PII + cost).
  - BatchSpanProcessor buffers exports so OTLP does not block request handling.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, Status, StatusCode

from app.config import (
    OTEL_EXPORTER_OTLP_ENDPOINT,
    OTEL_SERVICE_NAME,
    tracing_enabled,
)

logger = logging.getLogger(__name__)

_tracer_provider: TracerProvider | None = None
_fastapi_instrumented = False
_httpx_instrumented = False


class TraceContextFilter(logging.Filter):
    """Inject trace_id/span_id into log records for correlation in Grafana Loki (future)."""

    def filter(self, record: logging.LogRecord) -> bool:
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
        else:
            record.trace_id = ""
            record.span_id = ""
        return True


def init_tracing(app: FastAPI) -> TracerProvider | None:
    """
    Configure OTLP export and auto-instrument FastAPI + httpx.

    Call once at module import time, immediately after ``app = FastAPI(...)`` and any
    ``add_middleware`` calls — **not** from lifespan startup. FastAPIInstrumentor registers
    ASGI middleware; if that runs too late the HTTP parent span is never created and each
    ``rag.*`` phase becomes its own orphan trace.

    Returns the provider or None when tracing is disabled. Call ``shutdown_tracing()`` from
    lifespan shutdown to flush spans on exit.
    """
    global _tracer_provider, _fastapi_instrumented, _httpx_instrumented

    if not tracing_enabled():
        logger.info("OpenTelemetry tracing disabled (OTEL_ENABLED not set)")
        return None

    resource = Resource.create({"service.name": OTEL_SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=f"{OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces",
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _tracer_provider = provider

    if not _fastapi_instrumented:
        FastAPIInstrumentor.instrument_app(app)
        _fastapi_instrumented = True

    if not _httpx_instrumented:
        HTTPXClientInstrumentor().instrument()
        _httpx_instrumented = True

    root = logging.getLogger()
    if not any(isinstance(f, TraceContextFilter) for f in root.filters):
        root.addFilter(TraceContextFilter())

    logger.info(
        "OpenTelemetry tracing enabled (service=%s, endpoint=%s)",
        OTEL_SERVICE_NAME,
        OTEL_EXPORTER_OTLP_ENDPOINT,
    )
    return provider


def shutdown_tracing(provider: TracerProvider | None = None) -> None:
    """Flush and shut down the tracer provider on app shutdown."""
    global _tracer_provider
    active = provider if provider is not None else _tracer_provider
    if active is not None:
        active.shutdown()
        _tracer_provider = None


def _get_tracer():
    return trace.get_tracer("verbiage.rag")


@contextmanager
def rag_phase_span(
    phase: str,
    *,
    endpoint: str,
    **attrs: Any,
) -> Iterator[Span | None]:
    """
    Context manager for one RAG pipeline phase.

    Yields the active Span when tracing is enabled, else None (callers can ignore).
    Records exceptions as span errors and re-raises.
    """
    if not tracing_enabled():
        yield None
        return

    tracer = _get_tracer()
    span_name = f"rag.{phase}"
    with tracer.start_as_current_span(span_name) as span:
        span.set_attribute("rag.endpoint", endpoint)
        for key, value in attrs.items():
            if value is not None:
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise


def set_retrieval_attributes(
    span: Span | None,
    *,
    retrieval_mode: str,
    auto_routed: bool = False,
    chunk_count: int | None = None,
    top_cosine: float | None = None,
    gate_blocked: bool | None = None,
) -> None:
    """Attach retrieval outcome attributes to the active retrieve span."""
    if span is None:
        return
    span.set_attribute("rag.retrieval_mode", retrieval_mode)
    span.set_attribute("rag.auto_routed", auto_routed)
    if chunk_count is not None:
        span.set_attribute("rag.chunk_count", chunk_count)
    if top_cosine is not None:
        span.set_attribute("rag.top_cosine", round(top_cosine, 4))
    if gate_blocked is not None:
        span.set_attribute("rag.gate_blocked", gate_blocked)


def set_route_attribute(span: Span | None, route: str) -> None:
    """rag | nearby_storm — which ask path ran."""
    if span is not None:
        span.set_attribute("rag.route", route)


def set_refused_attribute(span: Span | None, refused: bool) -> None:
    """True when we returned the fixed no-context reply (empty chunks or gate)."""
    if span is not None:
        span.set_attribute("rag.refused", refused)
