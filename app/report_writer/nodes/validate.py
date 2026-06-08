"""Graph node: lightweight faithfulness validation."""

from __future__ import annotations

from app import llm_client
from app.report_writer.prompts import build_validate_prompt
from app.report_writer.state import ReportWriterState


async def validate_draft(state: ReportWriterState) -> dict:
    sections = state.get("sections") or {}
    if not any(s.get("content") for s in sections.values()):
        return {"errors": ["Draft has no section content."]}
    prompt = build_validate_prompt(sections, state.get("field_notes") or "")
    result = (await llm_client.answer_with_context(prompt, temperature=0.0)).strip()
    if result.upper().startswith("OK"):
        return {}
    if result.upper().startswith("ISSUE:"):
        return {"errors": [result[6:].strip()]}
    return {}
