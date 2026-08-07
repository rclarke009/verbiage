"""In-memory ring buffer of recent ask-run traces for local diagnosis.

Keeps the last N rich payloads so a weird answer can be inspected without
reproducing the request. Gated by ASK_RUN_BUFFER_ENABLED; no Postgres table.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Any

from app.config import ASK_RUN_BUFFER_ENABLED, ASK_RUN_BUFFER_SIZE

_lock = threading.Lock()
_buffer: deque[dict[str, Any]] = deque(maxlen=ASK_RUN_BUFFER_SIZE)


def reset_buffer(*, maxlen: int | None = None) -> None:
    """Clear the buffer (tests). Optionally resize maxlen."""
    global _buffer
    with _lock:
        size = maxlen if maxlen is not None else ASK_RUN_BUFFER_SIZE
        _buffer = deque(maxlen=max(1, size))


def push_ask_run_trace(record: dict[str, Any]) -> None:
    """Append one rich ask-run record; oldest dropped when full."""
    if not ASK_RUN_BUFFER_ENABLED:
        return
    with _lock:
        _buffer.append(record)


def list_ask_run_traces(*, limit: int | None = None) -> list[dict[str, Any]]:
    """Newest-first list of buffered records (compact index view)."""
    with _lock:
        items = list(_buffer)
    items.reverse()
    if limit is not None and limit >= 0:
        items = items[:limit]
    return items


def get_ask_run_trace(ask_run_id: str) -> dict[str, Any] | None:
    with _lock:
        for record in reversed(_buffer):
            if record.get("ask_run_id") == ask_run_id:
                return record
    return None


def buffer_size() -> int:
    with _lock:
        return len(_buffer)
