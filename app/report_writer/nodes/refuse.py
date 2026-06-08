"""Graph node: refuse when retrieval is too weak."""

from __future__ import annotations

from app.report_writer.state import ReportWriterState


def refuse(state: ReportWriterState) -> dict:
    reason = state.get("refusal_reason") or "Unable to generate a grounded draft."
    return {
        "run_status": "refused",
        "refusal_reason": reason,
    }
