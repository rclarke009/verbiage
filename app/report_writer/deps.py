"""Request-scoped dependencies for Report Writer graph nodes."""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Any


@dataclass
class ReportWriterDeps:
    db_pool: Any
    reranker: Any | None


_deps_var: contextvars.ContextVar[ReportWriterDeps | None] = contextvars.ContextVar(
    "report_writer_deps", default=None
)


def set_report_writer_deps(deps: ReportWriterDeps) -> contextvars.Token:
    return _deps_var.set(deps)


def reset_report_writer_deps(token: contextvars.Token) -> None:
    _deps_var.reset(token)


def get_report_writer_deps() -> ReportWriterDeps:
    deps = _deps_var.get()
    if deps is None:
        raise RuntimeError("Report Writer deps not set for this request")
    return deps
