"""Seed or refresh the synthetic eval corpus in demo deployments."""

from __future__ import annotations

import logging
import os

from psycopg2.extensions import connection as PgConnection

from app.config import DEMO_MODE
from tests.eval.seed import corpus_docs, seed_corpus_sync

logger = logging.getLogger(__name__)

DEMO_RESEED_CORPUS = os.getenv("DEMO_RESEED_CORPUS", "").strip().lower() in (
    "1",
    "true",
    "yes",
)


def _eval_fixture_doc_count(conn: PgConnection) -> int:
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT COUNT(*)::int FROM documents WHERE source = %s",
            ("eval_fixture",),
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0
    finally:
        cur.close()


def clear_eval_fixture(conn: PgConnection) -> int:
    """Remove prior eval_fixture documents. Returns the number removed."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT doc_id FROM documents WHERE source = %s",
            ("eval_fixture",),
        )
        doc_ids = [row[0] for row in cur.fetchall()]
        for doc_id in doc_ids:
            cur.execute(
                "DELETE FROM embeddings WHERE chunk_id IN "
                "(SELECT chunk_id FROM chunks WHERE doc_id = %s)",
                (doc_id,),
            )
            cur.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
            cur.execute("DELETE FROM documents WHERE doc_id = %s", (doc_id,))
        conn.commit()
        return len(doc_ids)
    finally:
        cur.close()


def demo_corpus_needs_seed(conn: PgConnection) -> bool:
    """True when the DB is missing reports or a forced reseed was requested."""
    if DEMO_RESEED_CORPUS:
        return True
    expected = len(corpus_docs())
    current = _eval_fixture_doc_count(conn)
    return current == 0 or current < expected


def maybe_seed_demo_corpus(conn: PgConnection) -> int | None:
    """Insert the synthetic corpus when demo mode is on and seeding is due.

    Returns the number of documents seeded, 0 when skipped, or None when not demo.
    """
    if not DEMO_MODE:
        return None
    if not demo_corpus_needs_seed(conn):
        logger.info(
            "Demo corpus up to date (%s eval_fixture documents)",
            _eval_fixture_doc_count(conn),
        )
        return 0

    removed = clear_eval_fixture(conn)
    if removed:
        logger.info("Demo seed: removed %s prior eval_fixture document(s)", removed)
    n = seed_corpus_sync(conn)
    logger.info("Demo seed: indexed %s synthetic report(s)", n)
    return n
