"""Graph node: persist draft revisions and finalize run."""

from __future__ import annotations

import asyncio

from app.db import get_valid_conn
from app.report_writer.deps import get_report_writer_deps
from app.report_writer.queries import (
    create_section_revision,
    finish_generation_run,
    set_claim_status_after_run,
)
from app.report_writer.state import ReportWriterState


async def persist_draft(state: ReportWriterState) -> dict:
    deps = get_report_writer_deps()
    claim_id = state["claim_id"]
    run_id = state["run_id"]
    run_status = state.get("run_status") or "completed"
    sections = state.get("sections") or {}

    def _persist(conn):
        if run_status == "refused":
            finish_generation_run(conn, run_id, status="refused", error=state.get("refusal_reason"))
            set_claim_status_after_run(conn, claim_id, "draft")
            return
        for section_key, sec in sections.items():
            content = (sec.get("content") or "").strip()
            if not content:
                continue
            if not state.get("regenerate_section_key") and sec.get("origin") == "user_edit":
                continue
            create_section_revision(
                conn,
                claim_id=claim_id,
                section_key=section_key,
                content=content,
                origin="regenerate" if state.get("regenerate_section_key") else "generation",
                generation_run_id=run_id,
                sources=sec.get("sources"),
            )
        finish_generation_run(conn, run_id, status="completed")
        set_claim_status_after_run(conn, claim_id, "ready")

    conn = get_valid_conn(deps.db_pool)
    try:
        await asyncio.to_thread(_persist, conn)
    finally:
        deps.db_pool.putconn(conn)

    return {"run_status": run_status}
