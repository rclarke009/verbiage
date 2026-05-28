"""
HTTP-level Prometheus instrumentation.

Skips recording for GET /metrics so scrape traffic does not skew latency totals.
Uses matched route templates (e.g. /documents/{doc_id}) as the ``route`` label to avoid
high cardinality from raw URLs.

Recording runs only when app.config.metrics_enabled() is true so tests can toggle via env
without restarting Python (constants like METRICS_ENABLED on the app are still import-time).
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import StreamingResponse

from app.config import metrics_enabled
from app.monitoring.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    http_status_class,
)


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return request.url.path


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not metrics_enabled():
            return await call_next(request)

        route_path = _route_template(request)
        if route_path == "/metrics":
            return await call_next(request)

        method = request.method.upper()
        start = time.perf_counter()

        def record_http_metrics(status_code: int) -> None:
            elapsed = time.perf_counter() - start
            cls = http_status_class(status_code)
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method, route=route_path
            ).observe(elapsed)
            HTTP_REQUESTS_TOTAL.labels(
                method=method, route=route_path, status_class=cls
            ).inc()

        try:
            response = await call_next(request)
        except BaseException:
            record_http_metrics(500)
            raise

        # Streaming bodies finish after the handler returns; wrap iterator so duration includes stream end.
        if isinstance(response, StreamingResponse):

            async def wrapped_body():
                try:
                    async for chunk in response.body_iterator:
                        yield chunk
                finally:
                    record_http_metrics(response.status_code)

            return StreamingResponse(
                wrapped_body(),
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
                background=response.background,
            )

        record_http_metrics(response.status_code)
        return response
