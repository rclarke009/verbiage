"""Graph node: normalize field notes into retrieval query."""

from __future__ import annotations

from app.report_writer.constants import get_report_type
from app.report_writer.prompts import build_retrieval_query
from app.report_writer.queries import empty_sections_template
from app.report_writer.state import ReportWriterState


def normalize_inputs(state: ReportWriterState) -> dict:
    notes = (state.get("field_notes") or "").strip()
    meta = state.get("property_metadata") or {}
    images = state.get("image_analyses") or []
    type_id = state.get("report_type") or get_report_type(meta)
    query = build_retrieval_query(notes, meta, images)
    sections = state.get("sections") or empty_sections_template(report_type=type_id)
    return {
        "retrieval_query": query,
        "sections": sections,
        "report_type": type_id,
    }
