"""Prompt builders for Report Writer section generation."""

from __future__ import annotations

from app.report_writer.constants import REPORT_SECTIONS

MAX_CONTEXT_CHARS = 8000


def build_retrieval_query(
    field_notes: str,
    property_metadata: dict | None,
    image_analyses: list[dict] | None = None,
) -> str:
    parts: list[str] = []
    meta = property_metadata or {}
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
        for img in image_analyses:
            cap = (img.get("caption") or "").strip()
            obs = (img.get("observations") or "").strip()
            if cap or obs:
                parts.append(f"Photo: {cap} {obs}".strip())
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
) -> str:
    context = _context_block(retrieved_chunks)
    meta = property_metadata or {}
    meta_lines = "\n".join(
        f"- {k.replace('_', ' ').title()}: {v}"
        for k, v in meta.items()
        if v and k != "report_template"
    )
    prior_parts: list[str] = []
    label_by_key = dict(REPORT_SECTIONS)
    for key, sec in prior_sections.items():
        content = sec.get("content", "")
        if content:
            label = label_by_key.get(key, key)
            prior_parts.append(f"{label}:\n{content}")
    prior = "\n\n".join(prior_parts)
    image_block = ""
    if image_analyses:
        lines = []
        for img in image_analyses:
            cap = img.get("caption") or ""
            obs = img.get("observations") or ""
            if cap or obs:
                lines.append(f"- {cap} {obs}".strip())
        if lines:
            image_block = "Photo observations from this claim:\n" + "\n".join(lines) + "\n\n"

    return (
        "You are drafting a storm damage engineering report section. "
        "Write professional inspection language grounded in the field notes and retrieved "
        "similar reports below. Do not invent damage not supported by the notes or context. "
        "If the context lacks detail for this section, state only what the field notes support.\n\n"
        f"Section to write: {section_label}\n\n"
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
