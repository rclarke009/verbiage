#!/usr/bin/env python3
"""Seed the demo Postgres database with the synthetic eval corpus.

Uses DATABASE_URL from the environment (demo Supabase). Safe to re-run: removes
prior eval_fixture documents before seeding.

Usage:
    DATABASE_URL=postgresql://... python scripts/seed_demo_db.py
"""

from __future__ import annotations

import os
import sys

from pgvector.psycopg2 import register_vector
import psycopg2

# Repo root on sys.path when invoked as scripts/seed_demo_db.py
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from app.db import create_db  # noqa: E402
from tests.eval.seed import seed_corpus_sync  # noqa: E402


def _connect() -> psycopg2.extensions.connection:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("DATABASE_URL must be set")
    conn = psycopg2.connect(url)
    register_vector(conn)
    return conn


def _clear_eval_fixture(conn) -> int:
    cur = conn.cursor()
    try:
        cur.execute("SELECT doc_id FROM documents WHERE source = %s", ("eval_fixture",))
        doc_ids = [row[0] for row in cur.fetchall()]
        for doc_id in doc_ids:
            cur.execute("DELETE FROM embeddings WHERE chunk_id IN (SELECT chunk_id FROM chunks WHERE doc_id = %s)", (doc_id,))
            cur.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
            cur.execute("DELETE FROM documents WHERE doc_id = %s", (doc_id,))
        conn.commit()
        return len(doc_ids)
    finally:
        cur.close()


def main() -> None:
    conn = _connect()
    try:
        create_db(conn)
        removed = _clear_eval_fixture(conn)
        if removed:
            print(f"MYDEBUG -> removed {removed} prior eval_fixture document(s)")
        n = seed_corpus_sync(conn)
        print(f"MYDEBUG -> seeded {n} documents into demo DB")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
