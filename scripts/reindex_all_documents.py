#!/usr/bin/env python3
"""
Reindex every ingested document from stored full_text.

Uses the same path as POST /documents/{doc_id}/reindex: re-chunk with current
defaults (paragraph strategy, breadcrumb v2), re-embed, replace chunks.

Run from project root:
  PYTHONPATH=. python scripts/reindex_all_documents.py
  PYTHONPATH=. python scripts/reindex_all_documents.py --dry-run
  PYTHONPATH=. python scripts/reindex_all_documents.py --limit 10 --offset 0
  PYTHONPATH=. python scripts/reindex_all_documents.py --limit 10 --offset 10
  PYTHONPATH=. python scripts/reindex_all_documents.py --use-stored-config

Requires DATABASE_URL (and embedding API / Ollama per app config). Can take a
while and incur embedding cost for the full corpus.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path


def _setup_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


@dataclass
class ReindexTarget:
    doc_id: str
    title: str | None
    chunking_config: dict | None


@dataclass
class ReindexOutcome:
    doc_id: str
    title: str | None
    ok: bool
    num_chunks: int | None = None
    error: str | None = None


def connect_db():
    import psycopg2
    from pgvector.psycopg2 import register_vector

    from app.config import DATABASE_CONNECTION_KWARGS, DATABASE_URL
    from app.db import NoPrepareConnection

    if not DATABASE_URL:
        raise SystemExit("DATABASE_URL is not set (check .env)")

    if DATABASE_CONNECTION_KWARGS:
        conn_kwargs = dict(DATABASE_CONNECTION_KWARGS)
        host = conn_kwargs.get("host", "")
        if "pooler.supabase.com" in host and conn_kwargs.get("port") == 6543:
            conn_kwargs["connection_factory"] = NoPrepareConnection
        conn = psycopg2.connect(**conn_kwargs)
    else:
        kwargs: dict = {"dsn": DATABASE_URL}
        if "pooler.supabase.com" in DATABASE_URL and ":6543" in DATABASE_URL:
            kwargs["connection_factory"] = NoPrepareConnection
        conn = psycopg2.connect(**kwargs)

    register_vector(conn)
    return conn


def list_reindexable_documents(conn) -> list[ReindexTarget]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT doc_id, title, chunking_config
            FROM documents
            WHERE full_text IS NOT NULL AND TRIM(full_text) <> ''
            ORDER BY created_at ASC
            """
        )
        rows = cur.fetchall()
    finally:
        cur.close()

    targets: list[ReindexTarget] = []
    for doc_id, title, chunking_config in rows:
        config_dict = chunking_config
        if isinstance(chunking_config, str):
            config_dict = json.loads(chunking_config)
        targets.append(ReindexTarget(doc_id, title, config_dict))
    return targets


def select_targets(
    targets: list[ReindexTarget],
    *,
    offset: int,
    limit: int,
) -> tuple[list[ReindexTarget], int]:
    """Return (slice, total_count). offset/limit paginate in stable created_at order."""
    total = len(targets)
    if offset < 0:
        raise SystemExit("--offset must be >= 0")
    if limit < 0:
        raise SystemExit("--limit must be >= 0")
    if offset >= total:
        return [], total
    end = total if limit <= 0 else min(offset + limit, total)
    return targets[offset:end], total


def chunking_options_for(target: ReindexTarget, use_stored_config: bool):
    from app.models import ChunkingOptions

    if use_stored_config and target.chunking_config:
        return ChunkingOptions(**target.chunking_config)
    return ChunkingOptions()


async def reindex_one(conn, target: ReindexTarget, use_stored_config: bool) -> ReindexOutcome:
    from app.db import get_document_full_text
    from app.embeddings import HttpEmbedder
    from app.indexing import reindex_document

    label = target.title or target.doc_id
    try:
        full_text = get_document_full_text(conn, target.doc_id)
        if full_text is None or not full_text.strip():
            return ReindexOutcome(
                target.doc_id,
                target.title,
                ok=False,
                error="missing or empty full_text",
            )
        opts = chunking_options_for(target, use_stored_config)
        embedder = HttpEmbedder()
        result = await reindex_document(
            conn,
            target.doc_id,
            full_text,
            chunking_options=opts,
            embedder=embedder,
        )
        conn.commit()
        return ReindexOutcome(
            target.doc_id,
            target.title,
            ok=True,
            num_chunks=result.num_chunks,
        )
    except Exception as exc:
        conn.rollback()
        return ReindexOutcome(
            target.doc_id,
            target.title,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        )


async def reindex_all(
    conn,
    targets: list[ReindexTarget],
    *,
    use_stored_config: bool,
    fail_fast: bool,
) -> list[ReindexOutcome]:
    outcomes: list[ReindexOutcome] = []
    total = len(targets)
    for index, target in enumerate(targets, start=1):
        label = target.title or target.doc_id
        print(f"[{index}/{total}] Reindexing {target.doc_id} ({label!r})...")
        outcome = await reindex_one(conn, target, use_stored_config)
        outcomes.append(outcome)
        if outcome.ok:
            print(
                f"  OK — {outcome.num_chunks} chunk(s)"
            )
        else:
            print(f"  FAILED — {outcome.error}", file=sys.stderr)
            if fail_fast:
                break
    return outcomes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reindex all ingested documents from stored full_text."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List documents that would be reindexed without calling embed API.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max documents to process (0 = all remaining after --offset).",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Skip this many reindexable documents (stable created_at order).",
    )
    parser.add_argument(
        "--doc-id",
        action="append",
        dest="doc_ids",
        default=[],
        help="Only reindex these doc_id values (repeatable).",
    )
    parser.add_argument(
        "--use-stored-config",
        action="store_true",
        help="Use each document's saved chunking_config instead of current defaults.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first failure instead of continuing.",
    )
    return parser.parse_args()


def main() -> int:
    _setup_path()
    args = parse_args()

    conn = connect_db()
    try:
        targets = list_reindexable_documents(conn)
    finally:
        conn.close()

    if args.doc_ids:
        wanted = set(args.doc_ids)
        targets = [t for t in targets if t.doc_id in wanted]
        missing = wanted - {t.doc_id for t in targets}
        for doc_id in sorted(missing):
            print(f"MYDEBUG → skipping unknown or empty doc_id: {doc_id}", file=sys.stderr)

    total_reindexable = len(targets)
    targets, _ = select_targets(targets, offset=args.offset, limit=args.limit)

    if not targets:
        if total_reindexable == 0:
            print("No documents with stored full_text to reindex.")
        else:
            print(
                f"No documents in this batch (offset {args.offset}, "
                f"{total_reindexable} reindexable total)."
            )
        return 0

    batch_end = args.offset + len(targets)
    print(
        f"Found {len(targets)} document(s) to reindex "
        f"(positions {args.offset + 1}–{batch_end} of {total_reindexable})."
    )
    if args.dry_run:
        for index, target in enumerate(targets, start=args.offset + 1):
            label = target.title or target.doc_id
            print(f"  [{index}/{total_reindexable}] {target.doc_id} ({label!r})")
        print("Dry run only — no changes made.")
        if args.limit > 0 and batch_end < total_reindexable:
            print(
                f"Next batch: PYTHONPATH=. python scripts/reindex_all_documents.py "
                f"--limit {args.limit} --offset {batch_end}"
            )
        return 0

    conn = connect_db()
    try:
        outcomes = asyncio.run(
            reindex_all(
                conn,
                targets,
                use_stored_config=args.use_stored_config,
                fail_fast=args.fail_fast,
            )
        )
    finally:
        conn.close()

    ok_count = sum(1 for o in outcomes if o.ok)
    fail_count = len(outcomes) - ok_count
    chunk_total = sum(o.num_chunks or 0 for o in outcomes if o.ok)

    print()
    print(
        f"Done: {ok_count} succeeded, {fail_count} failed, "
        f"{chunk_total} total chunk(s) written."
    )
    next_offset = args.offset + len(outcomes)
    if args.limit > 0 and next_offset < total_reindexable:
        print(
            f"Next batch: PYTHONPATH=. python scripts/reindex_all_documents.py "
            f"--limit {args.limit} --offset {next_offset}"
        )
    if fail_count:
        print("Failures:", file=sys.stderr)
        for outcome in outcomes:
            if not outcome.ok:
                label = outcome.title or outcome.doc_id
                print(
                    f"  - {outcome.doc_id} ({label!r}): {outcome.error}",
                    file=sys.stderr,
                )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
