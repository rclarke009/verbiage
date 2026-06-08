"""FastAPI routes for Report Writer."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse

from app.auth import get_current_user
from app.db import get_valid_conn
from app.report_writer.deps import ReportWriterDeps, reset_report_writer_deps, set_report_writer_deps
from app.report_writer.export import draft_to_docx_bytes, draft_to_pdf_bytes
from app.report_writer.constants import REPORT_TYPES, get_report_type, report_type_def, section_keys_for_type
from app.report_writer.models import (
    ClaimCreateRequest,
    ClaimResponse,
    ClaimUpdateRequest,
    ClaimsListResponse,
    GenerateRequest,
    GenerationRunResponse,
    GenerationRunsListResponse,
    RegenerateSectionRequest,
    ReportTypeModel,
    ReportTypeSectionModel,
    ReportTypesListResponse,
    ResumeRequest,
    SectionResponse,
    SectionUpdateRequest,
)
from app.report_writer.queries import (
    claim_has_generated_sections,
    create_claim,
    create_generation_run,
    create_section_revision,
    delete_claim,
    empty_sections_template,
    get_claim,
    get_claim_sections,
    get_generation_run,
    insert_claim_image,
    list_claim_images,
    list_claims,
    list_generation_runs,
    update_claim,
)
from app.report_writer.validation import normalize_report_type_metadata, validate_report_type_metadata
from app.report_writer.sse import stream_graph_events
from app.report_writer.storage import storage_path_for, write_claim_image

router = APIRouter(prefix="/report-writer", tags=["report-writer"])


@router.get("/report-types", response_model=ReportTypesListResponse)
async def get_report_types():
    return ReportTypesListResponse(
        report_types=[
            ReportTypeModel(
                id=t.id,
                label=t.label,
                description=t.description,
                sections=[ReportTypeSectionModel(key=k, label=l) for k, l in t.sections],
            )
            for t in REPORT_TYPES.values()
        ]
    )


def _claim_response(claim: dict, sections: dict | None = None) -> ClaimResponse:
    sec_out = {}
    for key, sec in (sections or {}).items():
        sec_out[key] = SectionResponse(
            section_key=key,
            content=sec.get("content", ""),
            revision_id=sec.get("revision_id"),
            origin=sec.get("origin"),
            sources=sec.get("sources") or [],
        )
    return ClaimResponse(
        claim_id=claim["claim_id"],
        user_id=claim["user_id"],
        title=claim["title"],
        property_metadata=claim["property_metadata"],
        field_notes=claim["field_notes"],
        status=claim["status"],
        created_at=claim.get("created_at"),
        updated_at=claim.get("updated_at"),
        sections=sec_out,
    )


async def _with_conn(request: Request, fn):
    pool = request.app.state.db_pool
    conn = get_valid_conn(pool)
    try:
        return await asyncio.to_thread(fn, conn)
    finally:
        pool.putconn(conn)


@router.post("/claims", response_model=ClaimResponse)
async def post_claim(
    request: Request,
    body: ClaimCreateRequest,
    user_id: str = Depends(get_current_user),
):
    validate_report_type_metadata(body.property_metadata)
    metadata = normalize_report_type_metadata(body.property_metadata)

    def _create(conn):
        return create_claim(
            conn,
            user_id=user_id,
            title=body.title,
            property_metadata=metadata,
            field_notes=body.field_notes,
        )

    claim = await _with_conn(request, _create)
    return _claim_response(claim)


@router.get("/claims", response_model=ClaimsListResponse)
async def get_claims(
    request: Request,
    user_id: str = Depends(get_current_user),
):
    def _list(conn):
        return list_claims(conn, user_id)

    claims = await _with_conn(request, _list)
    return ClaimsListResponse(claims=[_claim_response(c) for c in claims])


@router.get("/claims/{claim_id}", response_model=ClaimResponse)
async def get_claim_detail(
    request: Request,
    claim_id: str,
    user_id: str = Depends(get_current_user),
):
    def _get(conn):
        claim = get_claim(conn, claim_id, user_id)
        if not claim:
            return None
        sections = get_claim_sections(conn, claim_id)
        return claim, sections

    result = await _with_conn(request, _get)
    if not result:
        raise HTTPException(status_code=404, detail="Claim not found")
    claim, sections = result
    return _claim_response(claim, sections)


@router.patch("/claims/{claim_id}", response_model=ClaimResponse)
async def patch_claim(
    request: Request,
    claim_id: str,
    body: ClaimUpdateRequest,
    user_id: str = Depends(get_current_user),
):
    if body.property_metadata is not None:
        validate_report_type_metadata(body.property_metadata)

    def _load_existing(conn):
        return get_claim(conn, claim_id, user_id)

    existing = await _with_conn(request, _load_existing)
    if not existing:
        raise HTTPException(status_code=404, detail="Claim not found")

    metadata = body.property_metadata
    if metadata is not None:
        metadata = normalize_report_type_metadata(metadata)
        old_type = get_report_type(existing["property_metadata"])
        new_type = get_report_type(metadata)
        if old_type != new_type:
            def _has_sections(conn):
                return claim_has_generated_sections(conn, claim_id)

            if await _with_conn(request, _has_sections):
                raise HTTPException(
                    status_code=409,
                    detail="Cannot change report_type after sections have been generated",
                )

    def _update(conn):
        updated = update_claim(
            conn,
            claim_id,
            user_id,
            title=body.title,
            property_metadata=metadata,
            field_notes=body.field_notes,
            status=body.status,
        )
        if not updated:
            return None
        sections = get_claim_sections(conn, claim_id)
        return updated, sections

    result = await _with_conn(request, _update)
    if not result:
        raise HTTPException(status_code=404, detail="Claim not found")
    claim, sections = result
    return _claim_response(claim, sections)


@router.delete("/claims/{claim_id}", status_code=204)
async def remove_claim(
    request: Request,
    claim_id: str,
    user_id: str = Depends(get_current_user),
):
    def _delete(conn):
        return delete_claim(conn, claim_id, user_id)

    deleted = await _with_conn(request, _delete)
    if not deleted:
        raise HTTPException(status_code=404, detail="Claim not found")
    return Response(status_code=204)


@router.patch("/claims/{claim_id}/sections/{section_key}", response_model=SectionResponse)
async def patch_section(
    request: Request,
    claim_id: str,
    section_key: str,
    body: SectionUpdateRequest,
    user_id: str = Depends(get_current_user),
):
    def _edit(conn):
        claim = get_claim(conn, claim_id, user_id)
        if not claim:
            return None
        rev_id = create_section_revision(
            conn,
            claim_id=claim_id,
            section_key=section_key,
            content=body.content,
            origin="user_edit",
            generation_run_id=None,
        )
        return rev_id

    rev_id = await _with_conn(request, _edit)
    if not rev_id:
        raise HTTPException(status_code=404, detail="Claim not found")
    return SectionResponse(
        section_key=section_key,
        content=body.content,
        revision_id=rev_id,
        origin="user_edit",
        sources=[],
    )


@router.post("/claims/{claim_id}/generate")
async def generate_draft(
    request: Request,
    claim_id: str,
    body: GenerateRequest | None = None,
    user_id: str = Depends(get_current_user),
):
    graph = request.app.state.report_writer_graph
    if graph is None:
        raise HTTPException(status_code=503, detail="Report Writer graph not initialized")

    def _load(conn):
        claim = get_claim(conn, claim_id, user_id)
        if not claim:
            return None
        run_id = create_generation_run(conn, claim_id=claim_id, user_id=user_id, thread_id=claim_id)
        return claim, run_id

    loaded = await _with_conn(request, _load)
    if not loaded:
        raise HTTPException(status_code=404, detail="Claim not found")
    claim, run_id = loaded

    validate_report_type_metadata(claim["property_metadata"], required=True)
    report_type = get_report_type(claim["property_metadata"])

    input_state = {
        "claim_id": claim_id,
        "user_id": user_id,
        "run_id": run_id,
        "title": claim["title"],
        "field_notes": claim["field_notes"],
        "property_metadata": claim["property_metadata"],
        "report_type": report_type,
        "sections": empty_sections_template(report_type=report_type),
        "image_analyses": [],
        "errors": [],
    }
    config = {"configurable": {"thread_id": claim_id}}

    deps = ReportWriterDeps(db_pool=request.app.state.db_pool, reranker=request.app.state.reranker)

    async def event_iter():
        token = set_report_writer_deps(deps)
        try:
            async for frame in stream_graph_events(
                graph,
                input_state,
                config,
                run_id=run_id,
                claim_id=claim_id,
            ):
                yield frame
        finally:
            reset_report_writer_deps(token)

    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/claims/{claim_id}/sections/{section_key}/regenerate")
async def regenerate_section(
    request: Request,
    claim_id: str,
    section_key: str,
    body: RegenerateSectionRequest | None = None,
    user_id: str = Depends(get_current_user),
):
    regen_graph = getattr(request.app.state, "report_writer_regen_graph", None)
    if regen_graph is None:
        raise HTTPException(status_code=503, detail="Regenerate graph not initialized")

    def _load(conn):
        claim = get_claim(conn, claim_id, user_id)
        if not claim:
            return None
        sections = get_claim_sections(conn, claim_id)
        run_id = create_generation_run(conn, claim_id=claim_id, user_id=user_id, thread_id=f"{claim_id}:regen:{uuid.uuid4()}")
        return claim, sections, run_id

    loaded = await _with_conn(request, _load)
    if not loaded:
        raise HTTPException(status_code=404, detail="Claim not found")
    claim, sections, run_id = loaded

    validate_report_type_metadata(claim["property_metadata"], required=True)
    report_type = get_report_type(claim["property_metadata"])
    allowed_keys = section_keys_for_type(report_type)
    if section_key not in allowed_keys:
        raise HTTPException(status_code=400, detail=f"Unknown section_key for report type {report_type}")

    notes = claim["field_notes"]
    if body and body.instruction:
        notes = f"{notes}\n\nRegeneration instruction: {body.instruction}".strip()

    section_state = {
        k: {"content": v.get("content", ""), "status": "complete", "sources": v.get("sources", [])}
        for k, v in sections.items()
    }

    input_state = {
        "claim_id": claim_id,
        "user_id": user_id,
        "run_id": run_id,
        "field_notes": notes,
        "property_metadata": claim["property_metadata"],
        "report_type": report_type,
        "sections": section_state,
        "retrieved_chunks": [],
        "retrieval_passed": True,
        "regenerate_section_key": section_key,
        "errors": [],
    }
    config = {"configurable": {"thread_id": f"{claim_id}:regen:{run_id}"}}
    deps = ReportWriterDeps(db_pool=request.app.state.db_pool, reranker=request.app.state.reranker)

    async def event_iter():
        token = set_report_writer_deps(deps)
        try:
            async for frame in stream_graph_events(
                regen_graph,
                input_state,
                config,
                run_id=run_id,
                claim_id=claim_id,
            ):
                yield frame
        finally:
            reset_report_writer_deps(token)

    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/claims/{claim_id}/generate/resume")
async def resume_generation(
    request: Request,
    claim_id: str,
    body: ResumeRequest,
    user_id: str = Depends(get_current_user),
):
    graph = request.app.state.report_writer_graph
    if graph is None:
        raise HTTPException(status_code=503, detail="Report Writer graph not initialized")

    def _check(conn):
        return get_claim(conn, claim_id, user_id)

    claim = await _with_conn(request, _check)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    config = {"configurable": {"thread_id": claim_id}}
    if body.action == "cancel":
        return {"status": "cancelled"}

    deps = ReportWriterDeps(db_pool=request.app.state.db_pool, reranker=request.app.state.reranker)
    run_id = str(uuid.uuid4())

    async def event_iter():
        token = set_report_writer_deps(deps)
        try:
            async for frame in stream_graph_events(
                graph,
                None,
                config,
                run_id=run_id,
                claim_id=claim_id,
            ):
                yield frame
        finally:
            reset_report_writer_deps(token)

    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/claims/{claim_id}/runs", response_model=GenerationRunsListResponse)
async def get_runs(
    request: Request,
    claim_id: str,
    user_id: str = Depends(get_current_user),
):
    def _list(conn):
        return list_generation_runs(conn, claim_id, user_id)

    runs = await _with_conn(request, _list)
    return GenerationRunsListResponse(
        runs=[GenerationRunResponse(**r) for r in runs]
    )


@router.get("/claims/{claim_id}/runs/{run_id}", response_model=GenerationRunResponse)
async def get_run_detail(
    request: Request,
    claim_id: str,
    run_id: str,
    user_id: str = Depends(get_current_user),
):
    def _get(conn):
        return get_generation_run(conn, claim_id, run_id, user_id)

    run = await _with_conn(request, _get)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    sections = {
        k: SectionResponse(
            section_key=k,
            content=v.get("content", ""),
            revision_id=v.get("revision_id"),
            origin=v.get("origin"),
            sources=v.get("sources") or [],
        )
        for k, v in (run.get("sections") or {}).items()
    }
    return GenerationRunResponse(
        run_id=run["run_id"],
        claim_id=run["claim_id"],
        status=run["status"],
        thread_id=run["thread_id"],
        started_at=run.get("started_at"),
        completed_at=run.get("completed_at"),
        error=run.get("error"),
        sections=sections,
    )


@router.post("/claims/{claim_id}/images")
async def upload_image(
    request: Request,
    claim_id: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    data = await file.read()
    filename = file.filename or "photo.jpg"
    content_type = file.content_type or "application/octet-stream"

    def _save(conn):
        claim = get_claim(conn, claim_id, user_id)
        if not claim:
            return None
        image_id = str(uuid.uuid4())
        path = storage_path_for(user_id, claim_id, image_id, filename)
        write_claim_image(path, data)
        return insert_claim_image(
            conn,
            claim_id=claim_id,
            user_id=user_id,
            storage_path=path,
            filename=filename,
            content_type=content_type,
            size_bytes=len(data),
            sort_order=len(list_claim_images(conn, claim_id, user_id)),
        )

    result = await _with_conn(request, _save)
    if not result:
        raise HTTPException(status_code=404, detail="Claim not found")
    return result


@router.get("/claims/{claim_id}/images")
async def get_images(
    request: Request,
    claim_id: str,
    user_id: str = Depends(get_current_user),
):
    def _list(conn):
        claim = get_claim(conn, claim_id, user_id)
        if not claim:
            return None
        return list_claim_images(conn, claim_id, user_id)

    images = await _with_conn(request, _list)
    if images is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return {"images": images}


@router.get("/claims/{claim_id}/export/docx")
async def export_docx(
    request: Request,
    claim_id: str,
    user_id: str = Depends(get_current_user),
):
    def _load(conn):
        claim = get_claim(conn, claim_id, user_id)
        if not claim:
            return None
        sections = get_claim_sections(conn, claim_id)
        images = list_claim_images(conn, claim_id, user_id)
        return claim, sections, images

    result = await _with_conn(request, _load)
    if not result:
        raise HTTPException(status_code=404, detail="Claim not found")
    claim, sections, images = result
    export_title = report_type_def(get_report_type(claim["property_metadata"])).export_title
    data = draft_to_docx_bytes(sections, title=claim["title"] or export_title, claim=claim, images=images)
    filename = (claim["title"] or "report").replace(" ", "_")[:80] + ".docx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/claims/{claim_id}/export/pdf")
async def export_pdf(
    request: Request,
    claim_id: str,
    user_id: str = Depends(get_current_user),
):
    def _load(conn):
        claim = get_claim(conn, claim_id, user_id)
        if not claim:
            return None
        sections = get_claim_sections(conn, claim_id)
        images = list_claim_images(conn, claim_id, user_id)
        return claim, sections, images

    result = await _with_conn(request, _load)
    if not result:
        raise HTTPException(status_code=404, detail="Claim not found")
    claim, sections, images = result
    export_title = report_type_def(get_report_type(claim["property_metadata"])).export_title
    data = draft_to_pdf_bytes(sections, title=claim["title"] or export_title, claim=claim, images=images)
    filename = (claim["title"] or "report").replace(" ", "_")[:80] + ".pdf"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
