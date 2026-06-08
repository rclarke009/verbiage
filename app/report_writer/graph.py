"""Build and compile the Report Writer LangGraph."""

from __future__ import annotations

import os

from langgraph.graph import END, START, StateGraph

from app.report_writer.nodes.analyze_images import analyze_images
from app.report_writer.nodes.gate import gate_retrieval, route_after_gate
from app.report_writer.nodes.generate import generate_sections
from app.report_writer.nodes.normalize import normalize_inputs
from app.report_writer.nodes.persist import persist_draft
from app.report_writer.nodes.refuse import refuse
from app.report_writer.nodes.retrieve import retrieve_similar
from app.report_writer.nodes.validate import validate_draft
from app.report_writer.state import ReportWriterState

HITL_ENABLED = os.getenv("REPORT_WRITER_HITL", "").lower() in ("1", "true", "yes")


def build_report_writer_graph(checkpointer):
    graph = StateGraph(ReportWriterState)

    graph.add_node("analyze_images", analyze_images)
    graph.add_node("normalize_inputs", normalize_inputs)
    graph.add_node("retrieve_similar", retrieve_similar)
    graph.add_node("gate_retrieval", gate_retrieval)
    graph.add_node("generate_sections", generate_sections)
    graph.add_node("validate_draft", validate_draft)
    graph.add_node("persist_draft", persist_draft)
    graph.add_node("refuse", refuse)

    graph.add_edge(START, "analyze_images")
    graph.add_edge("analyze_images", "normalize_inputs")
    graph.add_edge("normalize_inputs", "retrieve_similar")
    graph.add_edge("retrieve_similar", "gate_retrieval")
    graph.add_conditional_edges("gate_retrieval", route_after_gate, {
        "generate_sections": "generate_sections",
        "refuse": "refuse",
    })
    graph.add_edge("generate_sections", "validate_draft")
    graph.add_edge("validate_draft", "persist_draft")
    graph.add_edge("refuse", "persist_draft")
    graph.add_edge("persist_draft", END)

    interrupt_before = ["generate_sections"] if HITL_ENABLED else None
    return graph.compile(checkpointer=checkpointer, interrupt_before=interrupt_before)


def build_regenerate_section_graph(checkpointer):
    """Subgraph for per-section regeneration (Phase 3)."""
    graph = StateGraph(ReportWriterState)
    graph.add_node("normalize_inputs", normalize_inputs)
    graph.add_node("retrieve_similar", retrieve_similar)
    graph.add_node("generate_sections", generate_sections)
    graph.add_node("validate_draft", validate_draft)
    graph.add_node("persist_draft", persist_draft)
    graph.add_edge(START, "normalize_inputs")
    graph.add_edge("normalize_inputs", "retrieve_similar")
    graph.add_edge("retrieve_similar", "generate_sections")
    graph.add_edge("generate_sections", "validate_draft")
    graph.add_edge("validate_draft", "persist_draft")
    graph.add_edge("persist_draft", END)
    return graph.compile(checkpointer=checkpointer)
