"""Graph node: relevance gate."""

from __future__ import annotations

from app.config import RAG_MIN_RELEVANCE_SCORE
from app.report_writer.state import ReportWriterState


def gate_retrieval(state: ReportWriterState) -> dict:
    chunks = state.get("retrieved_chunks") or []
    if not chunks:
        return {
            "retrieval_passed": False,
            "refusal_reason": "No similar reports found in the document library.",
            "run_status": "refused",
        }
    best_cosine = state.get("best_cosine")
    if best_cosine is not None and best_cosine < RAG_MIN_RELEVANCE_SCORE:
        return {
            "retrieval_passed": False,
            "refusal_reason": (
                "Retrieved reports are not similar enough to this claim to draft safely."
            ),
            "run_status": "refused",
        }
    return {"retrieval_passed": True}


def route_after_gate(state: ReportWriterState) -> str:
    if state.get("retrieval_passed"):
        return "generate_sections"
    return "refuse"
