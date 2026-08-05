#!/usr/bin/env python3
"""
Backfill documents.address from full_text and reindex so [Location:] breadcrumbs
land in chunk text / embeddings.

Uses the same indexing path as POST /documents/{doc_id}/reindex (metadata refresh
+ re-chunk + re-embed).

Run from project root:
  PYTHONPATH=. python scripts/backfill_document_addresses.py --dry-run
  PYTHONPATH=. python scripts/backfill_document_addresses.py
  PYTHONPATH=. python scripts/backfill_document_addresses.py --limit 10
  PYTHONPATH=. python scripts/backfill_document_addresses.py --doc-id 1v8F8CdoMU0NyfFu85Xlnale3k9KAV8PK

Requires DATABASE_URL (and embedding API / Ollama per app config).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path


def _setup_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


@dataclass
class Target:
    doc_id: str
    title: str | None
    current_address: str | None
    extracted_address: str


@dataclass
class Outcome:
    doc_id: str
    title: str | None
    ok: bool
    extracted_address: str | None = None
    num_chunks: int | None = None
    error: str | None = None
    skipped: bool = False


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


def list_backfill_targets(conn, *, only_missing: bool) -> list[Target]:
    from app.document_metadata import extract_address

    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT doc_id, title, address, full_text
            FROM documents
            WHERE full_text IS NOT NULL AND TRIM(full_text) <> ''
            ORDER BY created_at ASC
            """
        )
        rows = cur.fetchall()
    finally:
        cur.close()

    targets: list[Target] = []
    for doc_id, title, address, full_text in rows:
        extracted = extract_address(full_text or "", title)
        if not extracted:
            continue
        current = (address or "").strip() or None
        if only_missing and current:
            continue
        if current and current == extracted:
            # Still reindex if address column matches but we want breadcrumb refresh
            # when only_missing is False — caller filters via --force / default.
            pass
        targets.append(
            Target(
                doc_id=doc_id,
                title=title,
                current_address=current,
                extracted_address=extracted,
            )
        )
    return targets


def needs_reindex(target: Target, *, force: bool) -> bool:
    if force:
        return True
    if not target.current_address:
        return True
    # Address already set to the same extracted value — breadcrumbs may still
    # lack [Location:] from an older index. Force those via --force; by default
    # reindex when stored address differs or was empty.
    return target.current_address != target.extracted_address


async def backfill_one(conn, target: Target) -> Outcome:
    from app.db import get_document_full_text
    from app.embeddings import HttpEmbedder
    from app.indexing import reindex_document
    from app.models import ChunkingOptions

    label = target.title or target.doc_id
    try:
        full_text = get_document_full_text(conn, target.doc_id)
        if full_text is None or not full_text.strip():
            return Outcome(
                target.doc_id,
                target.title,
                ok=False,
                extracted_address=target.extracted_address,
                error="missing or empty full_text",
            )
        embedder = HttpEmbedder()
        result = await reindex_document(
            conn,
            target.doc_id,
            full_text,
            chunking_options=ChunkingOptions(),
            embedder=embedder,
        )
        conn.commit()
        print(f"MYDEBUG → backfilled {target.doc_id} address={target.extracted_address!r}")
        return Outcome(
            target.doc_id,
            target.title,
            ok=True,
            extracted_address=target.extracted_address,
            num_chunks=result.num_chunks,
        )
    except Exception as exc:
        conn.rollback()
        return Outcome(
            target.doc_id,
            target.title,
            ok=False,
            extracted_address=target.extracted_address,
            error=f"{type(exc).__name__}: {exc}",
        )


async def backfill_all(
    conn,
    targets: list[Target],
    *,
    fail_fast: bool,
) -> list[Outcome]:
    outcomes: list[Outcome] = []
    total = len(targets)
    for index, target in enumerate(targets, start=1):
        label = target.title or target.doc_id
        print(
            f"[{index}/{total}] {target.doc_id} ({label!r}) "
            f"→ {target.extracted_address!r}"
            + (f" (was {target.current_address!r})" if target.current_address else "")
        )
        outcome = await backfill_one(conn, target)
        outcomes.append(outcome)
        if outcome.ok:
            print(f"  OK — {outcome.num_chunks} chunk(s)")
        else:
            print(f"  FAILED — {outcome.error}", file=sys.stderr)
            if fail_fast:
                break
    return outcomes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill document addresses and reindex Location breadcrumbs."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List docs that would be backfilled without writing or embedding.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max documents to process (0 = all).",
    )
    parser.add_argument(
        "--doc-id",
        action="append",
        dest="doc_ids",
        default=[],
        help="Only process these doc_id values (repeatable).",
    )
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Also reindex docs that already have a non-empty address column.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reindex even when stored address already equals extracted address.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first failure.",
    )
    return parser.parse_args()


def main() -> int:
    _setup_path()
    args = parse_args()

    conn = connect_db()
    try:
        targets = list_backfill_targets(conn, only_missing=not args.include_existing)
    finally:
        conn.close()

    if args.doc_ids:
        wanted = set(args.doc_ids)
        targets = [t for t in targets if t.doc_id in wanted]
        # Also allow explicit doc-ids that already have addresses.
        if args.doc_ids and not targets:
            conn = connect_db()
            try:
                targets = list_backfill_targets(conn, only_missing=False)
            finally:
                conn.close()
            targets = [t for t in targets if t.doc_id in wanted]

    if not args.force:
        targets = [t for t in targets if needs_reindex(t, force=False)]
    else:
        targets = [t for t in targets if needs_reindex(t, force=True)]

    if args.limit > 0:
        targets = targets[: args.limit]

    if not targets:
        print("No documents need address backfill/reindex.")
        return 0

    print(f"Found {len(targets)} document(s) to backfill+reindex.")
    if args.dry_run:
        for index, target in enumerate(targets, start=1):
            label = target.title or target.doc_id
            print(
                f"  [{index}] {target.doc_id} ({label!r}) → {target.extracted_address!r}"
            )
        print("Dry run only — no changes made.")
        return 0

    conn = connect_db()
    try:
        outcomes = asyncio.run(
            backfill_all(conn, targets, fail_fast=args.fail_fast)
        )
    finally:
        conn.close()

    ok_count = sum(1 for o in outcomes if o.ok)
    fail_count = len(outcomes) - ok_count
    print()
    print(f"Done: {ok_count} succeeded, {fail_count} failed.")
    if fail_count:
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
