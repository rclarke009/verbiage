"""Prompt builders for Report Writer section generation."""

from __future__ import annotations

from app.report_writer.constants import (
    REPORT_TYPE_KEY,
    get_report_type,
    report_type_def,
    section_guidance_for,
    section_labels_for_type,
)
from app.report_writer.photo_summary import build_photo_context_block

MAX_CONTEXT_CHARS = 8000


def build_retrieval_query(
    field_notes: str,
    property_metadata: dict | None,
    image_analyses: list[dict] | None = None,
) -> str:
    parts: list[str] = []
    meta = property_metadata or {}
    type_id = get_report_type(meta)
    type_def = report_type_def(type_id)
    parts.extend(type_def.retrieval_terms)
    for key in (
        "storm_name",
        "storm_date",
        "storm_type",
        "storm_category",
        "landfall_region",
        "address",
        "property_type",
    ):
        val = meta.get(key)
        if val:
            parts.append(f"{key.replace('_', ' ')}: {val}")
    if field_notes.strip():
        parts.append(field_notes.strip())
    if image_analyses:
        block = build_photo_context_block(image_analyses)
        if block.strip():
            parts.append(block.strip())
    return "\n".join(parts).strip() or field_notes.strip() or "storm damage inspection"


def _context_block(chunks: list[dict]) -> str:
    parts: list[str] = []
    total = 0
    for c in chunks:
        title = (c.get("document_title") or "").strip() or c.get("doc_id", "")
        link = (c.get("source_url") or "").strip()
        link_line = f"Link: {link}\n" if link else ""
        block = (
            f"[doc_id={c.get('doc_id')} title={title!r} chunk_id={c.get('chunk_id')}]\n"
            f"{link_line}{c.get('content_snippet', '')}\n"
        )
        if total + len(block) > MAX_CONTEXT_CHARS:
            break
        parts.append(block)
        total += len(block)
    return "\n".join(parts) if parts else "(No relevant context found.)"


def build_section_prompt(
    section_key: str,
    section_label: str,
    field_notes: str,
    property_metadata: dict | None,
    retrieved_chunks: list[dict],
    prior_sections: dict[str, dict],
    image_analyses: list[dict] | None = None,
    report_type: str | None = None,
) -> str:
    context = _context_block(retrieved_chunks)
    meta = property_metadata or {}
    type_id = report_type or get_report_type(meta)
    type_def = report_type_def(type_id)
    meta_lines = "\n".join(
        f"- {k.replace('_', ' ').title()}: {v}"
        for k, v in meta.items()
        if v and k not in (REPORT_TYPE_KEY, "report_template")
    )
    label_by_key = section_labels_for_type(type_id)
    prior_parts: list[str] = []
    for key, sec in prior_sections.items():
        content = sec.get("content", "")
        if content:
            label = label_by_key.get(key, key)
            prior_parts.append(f"{label}:\n{content}")
    prior = "\n\n".join(prior_parts)
    image_block = build_photo_context_block(image_analyses)

    guidance = section_guidance_for(type_id, section_key)
    guidance_block = f"Section guidance: {guidance}\n\n" if guidance else ""

    return (
        f"{type_def.prompt_preamble} "
        "If the context lacks detail for this section, state only what the field notes support.\n\n"
        f"Report type: {type_def.label}\n"
        f"Section to write: {section_label}\n\n"
        f"{guidance_block}"
        f"Property metadata:\n{meta_lines or '(none)'}\n\n"
        f"{image_block}"
        f"Field notes for this claim:\n{field_notes.strip() or '(none)'}\n\n"
        + (f"Prior sections already drafted (keep consistent):\n{prior}\n\n" if prior else "")
        + "Similar language from past reports (use for style and phrasing, adapt to this claim):\n"
        f"{context}\n\n"
        f"Write only the {section_label} section body. No heading line, no markdown fences."
    )


def build_validate_prompt(sections: dict[str, dict], field_notes: str) -> str:
    body = "\n\n".join(
        f"{key}:\n{sec.get('content', '')}" for key, sec in sections.items() if sec.get("content")
    )
    return (
        "Review this draft report against the field notes. "
        "Reply with exactly OK if every statement is supported by the notes or standard "
        "professional phrasing. Otherwise reply ISSUE: followed by one sentence describing "
        "the main unsupported claim.\n\n"
        f"Field notes:\n{field_notes}\n\nDraft:\n{body}"
    )
