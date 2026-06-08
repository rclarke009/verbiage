"""LangGraph → SSE adapter for Report Writer generation."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator


def format_sse(event: str, payload: dict[str, Any], *, seq: int, run_id: str) -> str:
    return (
        f"id: {run_id}:{seq}\n"
        f"event: {event}\n"
        f"data: {json.dumps(payload)}\n\n"
    )


async def stream_graph_events(
    graph,
    input_state: dict,
    config: dict,
    *,
    run_id: str,
    claim_id: str,
) -> AsyncIterator[str]:
    seq = 0
    last_run_status = "completed"
    yield format_sse("run_started", {"run_id": run_id, "claim_id": claim_id}, seq=seq, run_id=run_id)
    seq += 1

    try:
        async for mode, chunk in graph.astream(
            input_state,
            config,
            stream_mode=["updates", "custom"],
        ):
            if mode == "custom":
                if isinstance(chunk, dict):
                    event = chunk.get("event")
                    if event == "section_start":
                        yield format_sse(
                            "section_start",
                            {"section_key": chunk.get("section_key")},
                            seq=seq,
                            run_id=run_id,
                        )
                        seq += 1
                    elif event == "section_delta":
                        yield format_sse(
                            "section_delta",
                            {
                                "section_key": chunk.get("section_key"),
                                "delta": chunk.get("delta", ""),
                            },
                            seq=seq,
                            run_id=run_id,
                        )
                        seq += 1
                    elif event == "section_complete":
                        yield format_sse(
                            "section_complete",
                            {
                                "section_key": chunk.get("section_key"),
                                "content": chunk.get("content", ""),
                                "sources": chunk.get("sources", []),
                            },
                            seq=seq,
                            run_id=run_id,
                        )
                        seq += 1
            elif mode == "updates":
                for node_name, update in chunk.items():
                    if not isinstance(update, dict):
                        continue
                    if node_name == "retrieve_similar" and update.get("retrieved_chunks"):
                        yield format_sse(
                            "sources",
                            {"chunks": update["retrieved_chunks"]},
                            seq=seq,
                            run_id=run_id,
                        )
                        seq += 1
                    if node_name in ("gate_retrieval", "refuse", "persist_draft", "generate_sections"):
                        partial = {k: v for k, v in update.items() if k != "sections"}
                        if node_name == "persist_draft" and update.get("run_status"):
                            last_run_status = update["run_status"]
                        yield format_sse(
                            "node_update",
                            {"node": node_name, "partial_state": partial},
                            seq=seq,
                            run_id=run_id,
                        )
                        seq += 1
                    if update.get("run_status") == "refused":
                        last_run_status = "refused"
                        yield format_sse(
                            "refused",
                            {"reason": update.get("refusal_reason", "")},
                            seq=seq,
                            run_id=run_id,
                        )
                        seq += 1

        final_status = last_run_status or "completed"
        yield format_sse(
            "run_complete",
            {"run_id": run_id, "status": final_status},
            seq=seq,
            run_id=run_id,
        )
    except Exception as exc:
        yield format_sse(
            "error",
            {"code": "generation_failed", "detail": str(exc)[:500]},
            seq=seq,
            run_id=run_id,
        )
        raise
