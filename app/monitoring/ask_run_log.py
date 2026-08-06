"""Structured ask-run log + response summary for diagnosing one /ask request.

Emits a single JSON line (event=ask_run) and builds AskRunSummary for the API/SSE.
Tempo spans stay low-cardinality; rich citation detail lives here and on the response.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from opentelemetry import trace

from app.config import (
    ASK_RUN_LOG_ENABLED,
    ASK_RUN_LOG_VERBOSE,
    EMBED_LOCAL_ONLY,
    EMBED_MODEL,
    LLM_MODEL,
    LLM_OPENAI_MODEL,
    OPENAI_API_KEY,
    RAG_MIN_RELEVANCE_SCORE,
)
from app.corrective import is_soft_refuse
from app.embeddings_openai import OPENAI_EMBED_MODEL
from app.models import (
    AskRunChunkRef,
    AskRunGate,
    AskRunLatency,
    AskRunModels,
    AskRunPromptMeta,
    AskRunRewrite,
    AskRunSummary,
    RetrievedChunk,
)

logger = logging.getLogger(__name__)

AskDecision = Literal[
    "answer",
    "hard_refuse",
    "soft_refuse",
    "nearby_storm",
    "error",
]

HARD_REFUSE_CANARY = "I don't have relevant context to answer that question."
_VERBOSE_SNIPPET_CHARS = 120
_VERBOSE_QUESTION_CHARS = 200


@dataclass
class RetrieveOutcome:
    """Chunks plus gate/mode metadata from one retrieve pass."""

    chunks: list[RetrievedChunk]
    top_cosine: float | None = None
    gate_blocked: bool = False
    retrieval_mode: str = "auto"
    auto_routed: bool = False
    rerank_ms: float | None = None


@dataclass
class AskRunBuilder:
    """Mutable accumulator for one ask request; finalize into AskRunSummary + JSON log."""

    ask_run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    endpoint: str = "sync"
    route: str = "rag"
    user_id: str | None = None
    question: str | None = None
    normalized_query: str | None = None
    retrieval_mode: str | None = None
    auto_routed: bool | None = None
    gate_blocked: bool = False
    top_cosine: float | None = None
    chunks: list[RetrievedChunk] = field(default_factory=list)
    rewrite_retried: bool = False
    rewritten_query: str | None = None
    embed_model: str | None = None
    prompt_text: str | None = None
    answer: str | None = None
    decision: AskDecision | None = None
    embed_ms: float | None = None
    retrieve_ms: float | None = None
    rerank_ms: float | None = None
    llm_ms: float | None = None
    total_ms: float | None = None
    error_type: str | None = None
    error_message: str | None = None

    def apply_retrieve(self, outcome: RetrieveOutcome, *, elapsed_ms: float | None = None) -> None:
        self.chunks = list(outcome.chunks)
        self.top_cosine = outcome.top_cosine
        self.gate_blocked = outcome.gate_blocked
        self.retrieval_mode = outcome.retrieval_mode
        self.auto_routed = outcome.auto_routed
        if elapsed_ms is not None:
            self.retrieve_ms = (self.retrieve_ms or 0.0) + elapsed_ms
        if outcome.rerank_ms is not None:
            self.rerank_ms = (self.rerank_ms or 0.0) + outcome.rerank_ms

    def classify_decision(self) -> AskDecision:
        if self.decision == "error" or self.error_type:
            return "error"
        if self.route == "nearby_storm":
            return "nearby_storm"
        answer = self.answer or ""
        if not self.chunks and (
            answer.startswith(HARD_REFUSE_CANARY)
            or self.gate_blocked
            or not answer
        ):
            return "hard_refuse"
        if is_soft_refuse(answer):
            return "soft_refuse"
        return "answer"


def new_ask_run_id() -> str:
    return str(uuid.uuid4())


def current_trace_id() -> str | None:
    try:
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if not ctx.is_valid:
            return None
        tid = ctx.trace_id
        if not isinstance(tid, int) or tid == 0:
            return None
        return format(tid, "032x")
    except Exception:
        return None


def hash_user_id(user_id: str | None) -> str | None:
    if not user_id:
        return None
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]


def resolve_model_names(embed_model: str | None = None) -> AskRunModels:
    use_openai_llm = bool(OPENAI_API_KEY)
    use_openai_embed = bool(OPENAI_API_KEY) and not EMBED_LOCAL_ONLY
    return AskRunModels(
        embed=embed_model or (OPENAI_EMBED_MODEL if use_openai_embed else EMBED_MODEL),
        llm=LLM_OPENAI_MODEL if use_openai_llm else LLM_MODEL,
        provider="openai" if use_openai_llm else "ollama",
    )


def prompt_meta(prompt: str | None) -> AskRunPromptMeta | None:
    if prompt is None:
        return None
    return AskRunPromptMeta(
        sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        chars=len(prompt),
    )


def chunk_refs(
    chunks: list[RetrievedChunk],
    *,
    verbose: bool = False,
) -> list[AskRunChunkRef]:
    refs: list[AskRunChunkRef] = []
    for c in chunks:
        snippet = None
        if verbose and c.content_snippet:
            snippet = c.content_snippet[:_VERBOSE_SNIPPET_CHARS]
        refs.append(
            AskRunChunkRef(
                chunk_id=c.chunk_id,
                doc_id=c.doc_id,
                score=round(c.score, 6),
                title=c.document_title,
                source=c.source,
                snippet=snippet,
            )
        )
    return refs


def build_ask_run_summary(builder: AskRunBuilder) -> AskRunSummary:
    decision = builder.decision or builder.classify_decision()
    soft = is_soft_refuse(builder.answer or "")
    hard = decision == "hard_refuse"
    models = resolve_model_names(builder.embed_model)
    verbose = ASK_RUN_LOG_VERBOSE
    return AskRunSummary(
        ask_run_id=builder.ask_run_id,
        trace_id=current_trace_id(),
        endpoint=builder.endpoint,
        route=builder.route,
        decision=decision,
        retrieval_mode=builder.retrieval_mode,
        auto_routed=builder.auto_routed,
        gate=AskRunGate(
            blocked=builder.gate_blocked,
            top_cosine=round(builder.top_cosine, 4) if builder.top_cosine is not None else None,
            threshold=RAG_MIN_RELEVANCE_SCORE,
        ),
        models=models,
        prompt=prompt_meta(builder.prompt_text),
        chunks=chunk_refs(builder.chunks, verbose=False),
        rewrite=(
            AskRunRewrite(
                retried=True,
                rewritten_query=builder.rewritten_query,
            )
            if builder.rewrite_retried
            else None
        ),
        latency_ms=AskRunLatency(
            embed=round(builder.embed_ms, 1) if builder.embed_ms is not None else None,
            retrieve=round(builder.retrieve_ms, 1) if builder.retrieve_ms is not None else None,
            rerank=round(builder.rerank_ms, 1) if builder.rerank_ms is not None else None,
            llm=round(builder.llm_ms, 1) if builder.llm_ms is not None else None,
            total=round(builder.total_ms, 1) if builder.total_ms is not None else None,
        ),
        answer_chars=len(builder.answer) if builder.answer is not None else None,
        refused_hard=hard,
        soft_refuse=soft,
        normalized_query_len=len(builder.normalized_query) if builder.normalized_query else None,
        question_preview=(
            (builder.question or "")[:_VERBOSE_QUESTION_CHARS] if verbose and builder.question else None
        ),
        user_id_hash=hash_user_id(builder.user_id),
        error_type=builder.error_type,
        error_message=builder.error_message,
    )


def ask_run_log_payload(summary: AskRunSummary, builder: AskRunBuilder) -> dict[str, Any]:
    """JSON-serializable dict for the log line (may include verbose extras)."""
    payload = summary.model_dump(mode="json", exclude_none=True)
    payload["event"] = "ask_run"
    if ASK_RUN_LOG_VERBOSE:
        payload["chunks"] = [
            r.model_dump(mode="json", exclude_none=True)
            for r in chunk_refs(builder.chunks, verbose=True)
        ]
        if builder.question:
            payload["question_preview"] = builder.question[:_VERBOSE_QUESTION_CHARS]
    return payload


def emit_ask_run(builder: AskRunBuilder) -> AskRunSummary:
    """Build summary, optionally log one JSON line, return summary for the response."""
    summary = build_ask_run_summary(builder)
    if ASK_RUN_LOG_ENABLED:
        payload = ask_run_log_payload(summary, builder)
        logger.info("%s", json.dumps(payload, separators=(",", ":"), default=str))
    return summary


def finalize_ask_run(builder: AskRunBuilder, *, t0: float, now: float) -> AskRunSummary:
    builder.total_ms = (now - t0) * 1000.0
    if builder.decision is None:
        builder.decision = builder.classify_decision()
    return emit_ask_run(builder)
