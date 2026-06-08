"""Graph nodes: section generation with streaming."""

from __future__ import annotations

from langgraph.config import get_stream_writer

from app import llm_client
from app.report_writer.constants import get_report_type, section_labels_for_type, sections_for_type
from app.report_writer.prompts import build_section_prompt
from app.report_writer.state import ReportWriterState


def _chunk_sources(chunks: list[dict]) -> list[dict]:
    return [
        {
            "chunk_id": c.get("chunk_id"),
            "doc_id": c.get("doc_id"),
            "score": c.get("score"),
            "snippet": (c.get("content_snippet") or "")[:400],
            "document_title": c.get("document_title"),
            "source_url": c.get("source_url"),
        }
        for c in chunks
    ]


async def generate_sections(state: ReportWriterState) -> dict:
    """Generate all report sections sequentially, streaming tokens per section."""
    writer = get_stream_writer()
    sections = dict(state.get("sections") or {})
    chunks = state.get("retrieved_chunks") or []
    sources = _chunk_sources(chunks)
    field_notes = state.get("field_notes") or ""
    meta = state.get("property_metadata") or {}
    images = state.get("image_analyses") or []
    regen_key = state.get("regenerate_section_key")
    type_id = state.get("report_type") or get_report_type(meta)

    keys_to_run = [regen_key] if regen_key else [k for k, _ in sections_for_type(type_id)]
    labels = section_labels_for_type(type_id)

    for section_key in keys_to_run:
        label = labels.get(section_key, section_key)
        if writer:
            writer({"event": "section_start", "section_key": section_key})
        prompt = build_section_prompt(
            section_key,
            label,
            field_notes,
            meta,
            chunks,
            sections,
            images,
            report_type=type_id,
        )
        parts: list[str] = []
        async for delta in llm_client.answer_with_context_stream(prompt):
            if delta:
                parts.append(delta)
                if writer:
                    writer({"event": "section_delta", "section_key": section_key, "delta": delta})
        content = "".join(parts).strip()
        sections[section_key] = {
            "content": content,
            "status": "complete",
            "sources": sources,
        }
        if writer:
            writer(
                {
                    "event": "section_complete",
                    "section_key": section_key,
                    "content": content,
                    "sources": sources,
                }
            )

    return {"sections": sections, "regenerate_section_key": None}


async def generate_single_section(state: ReportWriterState) -> dict:
    """Regenerate one section (Phase 3 subgraph entry)."""
    return await generate_sections(state)
