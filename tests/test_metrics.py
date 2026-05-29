"""Prometheus metrics helpers and HTTP middleware (no database required)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY, generate_latest

from app.monitoring.middleware import PrometheusMiddleware
from app.monitoring.metrics import (
    record_hybrid_scores,
    record_lexical_scores,
    record_retrieval_scores,
    record_upstream_fallback,
)


def _sample(name: str, **labels) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_prometheus_middleware_increments_http_counters(monkeypatch):
    monkeypatch.setenv("METRICS_ENABLED", "true")

    app = FastAPI()
    app.add_middleware(PrometheusMiddleware)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    client = TestClient(app)
    client.get("/ping")

    body = generate_latest(REGISTRY).decode()
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body


def test_record_retrieval_scores_and_fallback_increment_metrics():
    record_upstream_fallback("llm")
    record_retrieval_scores("sync", [0.92, 0.41])

    body = generate_latest(REGISTRY).decode()
    assert "upstream_fallback_total" in body
    assert "rag_retrieval_chunk_similarity" in body
    assert "rag_retrieval_top_similarity" in body


def test_record_lexical_scores_stays_off_cosine_metrics():
    ep = "lex_present"
    before_empty = _sample("rag_retrieval_empty_total", endpoint=ep)
    before_cosine = _sample("rag_retrieval_top_similarity_count", endpoint=ep)

    record_lexical_scores(ep, [0.05, 0.02])

    assert _sample("rag_retrieval_top_lexical_score_count", endpoint=ep) == 1.0
    # cosine histograms and the empty counter must NOT move for lexical-only hits
    assert _sample("rag_retrieval_empty_total", endpoint=ep) == before_empty
    assert _sample("rag_retrieval_top_similarity_count", endpoint=ep) == before_cosine


def test_record_lexical_scores_empty_increments_empty_counter():
    ep = "lex_empty"
    before = _sample("rag_retrieval_empty_total", endpoint=ep)
    record_lexical_scores(ep, [])
    assert _sample("rag_retrieval_empty_total", endpoint=ep) == before + 1
    assert _sample("rag_retrieval_top_lexical_score_count", endpoint=ep) == 0.0


def test_record_hybrid_scores_populates_all_three_scales():
    ep = "hyb_all"
    record_hybrid_scores(ep, [0.8, 0.7], [0.05], [0.032, 0.016])

    assert _sample("rag_retrieval_top_similarity_count", endpoint=ep) == 1.0
    assert _sample("rag_retrieval_top_lexical_score_count", endpoint=ep) == 1.0
    assert _sample("rag_retrieval_top_rrf_score_count", endpoint=ep) == 1.0
    # cosine signal stays on its own scale (top-1 cosine recorded as-is)
    assert _sample("rag_retrieval_top_similarity_sum", endpoint=ep) == 0.8


def test_record_hybrid_scores_skips_absent_lexical():
    ep = "hyb_no_lex"
    record_hybrid_scores(ep, [0.8], [], [0.016])
    assert _sample("rag_retrieval_top_lexical_score_count", endpoint=ep) == 0.0
    assert _sample("rag_retrieval_top_rrf_score_count", endpoint=ep) == 1.0
    assert _sample("rag_retrieval_top_similarity_count", endpoint=ep) == 1.0
