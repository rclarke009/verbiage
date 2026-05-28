"""Prometheus metrics helpers and HTTP middleware (no database required)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY, generate_latest

from app.monitoring.middleware import PrometheusMiddleware
from app.monitoring.metrics import record_retrieval_scores, record_upstream_fallback


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
