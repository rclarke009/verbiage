"""LangGraph state types for Report Writer."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class SectionDraft(TypedDict, total=False):
    content: str
    status: str
    sources: list[dict[str, Any]]


class ImageAnalysis(TypedDict, total=False):
    image_id: str
    caption: str
    observations: str


class ReportWriterState(TypedDict, total=False):
    claim_id: str
    user_id: str
    run_id: str
    title: str
    field_notes: str
    property_metadata: dict[str, Any]
    report_type: str
    image_analyses: list[ImageAnalysis]
    retrieval_query: str
    retrieved_chunks: list[dict[str, Any]]
    best_cosine: float | None
    retrieval_passed: bool
    sections: dict[str, SectionDraft]
    refusal_reason: str
    run_status: str
    errors: Annotated[list[str], operator.add]
    hitl_action: str
    regenerate_section_key: str | None
