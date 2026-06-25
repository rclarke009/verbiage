"""Ask query routing and nearby-storm structured retrieval."""

from __future__ import annotations

import re
from typing import Literal

from app.db import get_first_chunks_for_docs, retrieve_nearby_storm_docs
from app.geocode.nominatim import geocode_address
from app.models import AskRequest, ClaimContext, RetrievedChunk
from app.source_url import resolved_source_url
from app.storms.florida_storms import get_storm_by_id

AskRoute = Literal["rag", "nearby_storm"]

_NEARBY_STORM_HINT = re.compile(
    r"\b(closest|nearest|nearby|same storm|other places|other properties|other reports)\b",
    re.IGNORECASE,
)


def resolve_ask_route(
    question: str,
    query_mode: str,
    claim_context: ClaimContext | None,
) -> AskRoute:
    """Pick structured nearby-storm lookup vs standard RAG."""
    mode = (query_mode or "auto").strip().lower()
    if mode == "rag":
        return "rag"
    if mode == "nearby_storm":
        return "nearby_storm"
    if mode != "auto":
        return "rag"

    if not _NEARBY_STORM_HINT.search(question or ""):
        return "rag"
    if claim_context is None:
        return "rag"
    if claim_context.storm_id or claim_context.storm_name:
        if claim_context.has_anchor():
            return "nearby_storm"
    return "rag"


async def _resolve_anchor(
    claim_context: ClaimContext,
) -> tuple[float, float] | None:
    if claim_context.latitude is not None and claim_context.longitude is not None:
        return claim_context.latitude, claim_context.longitude
    if claim_context.address:
        geocoded = await geocode_address(claim_context.address)
        if geocoded is not None:
            return geocoded.latitude, geocoded.longitude
    return None


def _resolve_storm_id(claim_context: ClaimContext) -> str | None:
    if claim_context.storm_id:
        storm = get_storm_by_id(claim_context.storm_id)
        return storm.id if storm else claim_context.storm_id.strip()
    if claim_context.storm_name:
        needle = claim_context.storm_name.strip().lower()
        from app.storms.florida_storms import FLORIDA_STORMS

        for storm in FLORIDA_STORMS:
            if storm.name.lower() == needle:
                return storm.id
    return None


def format_nearby_storm_answer(
    rows: list[tuple[str, str | None, str | None, float]],
    *,
    storm_label: str,
    anchor_address: str | None,
) -> str:
    if not rows:
        return "No source documents contain other properties for that storm near this location."

    lines = [
        f"Other properties with the same storm ({storm_label}), sorted by distance"
        + (f" from {anchor_address}" if anchor_address else "")
        + ":",
        "",
    ]
    for idx, (_doc_id, title, address, distance_mi) in enumerate(rows, start=1):
        label = (address or title or "Unknown property").strip()
        lines.append(f"{idx}. {label} — {distance_mi:.1f} mi")
    return "\n".join(lines)


async def retrieve_nearby_storm_chunks(
    conn,
    ask_request: AskRequest,
) -> tuple[str | None, list[RetrievedChunk]]:
    """Structured nearby-storm lookup. None answer means caller should refuse."""
    ctx = ask_request.claim_context
    if ctx is None:
        return None, []

    storm_id = _resolve_storm_id(ctx)
    anchor = await _resolve_anchor(ctx)
    if not storm_id or anchor is None:
        return None, []

    lat, lng = anchor
    rows = retrieve_nearby_storm_docs(
        conn,
        storm_id=storm_id,
        latitude=lat,
        longitude=lng,
        limit=ask_request.top_k,
    )
    storm = get_storm_by_id(storm_id)
    storm_label = storm.name if storm else (ctx.storm_name or storm_id)
    if storm and storm.storm_type == "hurricane":
        storm_label = f"Hurricane {storm.name}"

    answer = format_nearby_storm_answer(
        rows,
        storm_label=storm_label,
        anchor_address=ctx.address,
    )

    doc_ids = [doc_id for doc_id, _, _, _ in rows]
    chunk_map = get_first_chunks_for_docs(conn, doc_ids)
    chunks: list[RetrievedChunk] = []
    for doc_id, title, address, distance_mi in rows:
        hit = chunk_map.get(doc_id)
        if not hit:
            continue
        chunk_id, content, doc_title, source, source_url = hit
        display_title = title or doc_title or address or doc_id
        chunks.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                score=round(-distance_mi, 4),
                content_snippet=content,
                document_title=display_title,
                source=source,
                source_url=resolved_source_url(source, doc_id, source_url),
                distance_mi=round(distance_mi, 1),
            )
        )

    return answer, chunks
