"""
Prometheus metrics for the RAG stack.

How to use:
  - Prometheus scrapes GET /metrics when METRICS_ENABLED is true (see app.config).
  - Histograms store observations in cumulative buckets; use Prometheus histogram_quantile()
    or Grafana's histogram quantiles for p50/p95 latency or similarity percentiles.
  - "rag_*" metrics describe question answering only (/ask and /ask/stream).
  - Empty retrieval (no chunks) is counted separately from low cosine scores: you may have
    chunks whose embeddings are weak matches — see rag_retrieval_low_quality_total when
    RAG_SIMILARITY_ALERT_THRESHOLD is set.

Empty retrieval vs LLM refusal:
  - rag_no_context_response_total fires when we return the fixed "no relevant context" reply
    because top_chunks was empty.
  - If chunks exist but the model says "not enough information in context", we do not detect
    that yet (would need structured output or classification).
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

from app.config import RAG_SIMILARITY_ALERT_THRESHOLD

# Buckets for cosine similarity scores in [0, 1] from pgvector (1 - distance).
_SIM_BUCKETS = tuple(round(i * 0.05, 2) for i in range(1, 21))

# RAG phases can include slow LLM calls; extend past default Prometheus buckets (~10s).
_PHASE_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
    60.0,
    120.0,
    180.0,
)

# --- HTTP (all routes; labels keep cardinality low via route templates) ---
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "Wall time for HTTP requests until the full response body is sent "
    "(including streaming completion for StreamingResponse).",
    ["method", "route"],
    buckets=_PHASE_BUCKETS,
)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "HTTP responses by status class (2xx / 4xx / 5xx).",
    ["method", "route", "status_class"],
)

# --- RAG phases (embed / retrieve / llm); endpoint is sync vs stream ---
RAG_PHASE_SECONDS = Histogram(
    "rag_phase_seconds",
    "Time spent inside each phase of the ask pipeline.",
    ["phase", "endpoint"],
    buckets=_PHASE_BUCKETS,
)

RAG_RETRIEVAL_EMPTY_TOTAL = Counter(
    "rag_retrieval_empty_total",
    "Ask requests where vector search returned zero chunks.",
    ["endpoint"],
)

RAG_RETRIEVAL_TOP_SIMILARITY = Histogram(
    "rag_retrieval_top_similarity",
    "Cosine similarity of the single best-matching chunk per ask request.",
    ["endpoint"],
    buckets=_SIM_BUCKETS,
)

RAG_RETRIEVAL_MEAN_SIMILARITY = Histogram(
    "rag_retrieval_mean_similarity",
    "Mean cosine similarity across all chunks returned for one ask request.",
    ["endpoint"],
    buckets=_SIM_BUCKETS,
)

RAG_RETRIEVAL_CHUNK_SIMILARITY = Histogram(
    "rag_retrieval_chunk_similarity",
    "Distribution of chunk cosine similarities — one observation per retrieved chunk. "
    "Aggregates across traffic to show overall retrieval strength.",
    ["endpoint"],
    buckets=_SIM_BUCKETS,
)

RAG_RETRIEVAL_LOW_QUALITY_TOTAL = Counter(
    "rag_retrieval_low_quality_total",
    "Requests with at least one chunk but top-1 similarity below "
    "RAG_SIMILARITY_ALERT_THRESHOLD (config).",
    ["endpoint"],
)

RAG_NO_CONTEXT_RESPONSE_TOTAL = Counter(
    "rag_no_context_response_total",
    'Responses using the fixed "no relevant context" path (empty chunk list).',
    ["endpoint"],
)

RAG_STREAM_RETRIEVAL_FAILED_TOTAL = Counter(
    "rag_stream_retrieval_failed_total",
    "SSE ask_stream failures during embedding/retrieve (generic exception path).",
)

UPSTREAM_TIMEOUTS_TOTAL = Counter(
    "upstream_timeouts_total",
    "Exhausted retries ending in a timeout talking to LLM or embedding backends.",
    ["component"],
)

UPSTREAM_FALLBACK_TOTAL = Counter(
    "upstream_fallback_total",
    "Primary remote API failed and caller fell back to local Ollama (when configured).",
    ["kind"],
)


def _clamp_unit_interval(score: float) -> float:
    return max(0.0, min(1.0, float(score)))


def record_rag_phase_seconds(phase: str, endpoint: str, seconds: float) -> None:
    """Observe duration for one pipeline phase (embed, retrieve, llm)."""
    RAG_PHASE_SECONDS.labels(phase=phase, endpoint=endpoint).observe(max(0.0, seconds))


def record_retrieval_scores(endpoint: str, scores: list[float]) -> None:
    """
    Record retrieval quality for one completed retrieve step.

    scores: cosine similarities from DB for each chunk, best-first order.
    """
    if not scores:
        RAG_RETRIEVAL_EMPTY_TOTAL.labels(endpoint=endpoint).inc()
        return

    top = _clamp_unit_interval(scores[0])
    RAG_RETRIEVAL_TOP_SIMILARITY.labels(endpoint=endpoint).observe(top)

    mean_score = _clamp_unit_interval(sum(scores) / len(scores))
    RAG_RETRIEVAL_MEAN_SIMILARITY.labels(endpoint=endpoint).observe(mean_score)

    for s in scores:
        RAG_RETRIEVAL_CHUNK_SIMILARITY.labels(endpoint=endpoint).observe(
            _clamp_unit_interval(s)
        )

    thresh = RAG_SIMILARITY_ALERT_THRESHOLD
    if thresh is not None and top < thresh:
        RAG_RETRIEVAL_LOW_QUALITY_TOTAL.labels(endpoint=endpoint).inc()


def record_no_context_response(endpoint: str) -> None:
    """User-visible no-context reply (empty retrieval)."""
    RAG_NO_CONTEXT_RESPONSE_TOTAL.labels(endpoint=endpoint).inc()


def record_stream_retrieval_failed() -> None:
    """ask_stream could not complete embedding/retrieve (see SSE error event)."""
    RAG_STREAM_RETRIEVAL_FAILED_TOTAL.inc()


def record_upstream_timeout(component: str) -> None:
    """component: llm_openai | llm_ollama | embed_openai | embed_ollama"""
    UPSTREAM_TIMEOUTS_TOTAL.labels(component=component).inc()


def record_upstream_fallback(kind: str) -> None:
    """kind: llm | embed"""
    UPSTREAM_FALLBACK_TOTAL.labels(kind=kind).inc()


def http_status_class(code: int) -> str:
    if 200 <= code < 300:
        return "2xx"
    if 400 <= code < 500:
        return "4xx"
    return "5xx"
