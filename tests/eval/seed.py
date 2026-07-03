"""Seed the ephemeral eval DB with the frozen corpus.

Reuses the app demo corpus seed path (``app/demo_corpus/``) so production
demo deployments and the faithfulness eval share the same synthetic reports.
Embeddings come from CachedEmbedder so the seed is reproducible run-to-run.

Run standalone to (re)warm the embeddings cache against a live backend:

    EVAL_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/verbiage_eval \
      python -m tests.eval.seed
"""

from __future__ import annotations

import asyncio
import os

import psycopg2
from pgvector.psycopg2 import register_vector

from app.db import create_db
from app.demo_corpus.seed import corpus_docs, seed_corpus_sync

try:  # support both `python -m tests.eval.seed` and pytest's path-based import
    from .embedding_cache import CachedEmbedder
except ImportError:  # pragma: no cover - fallback when imported as a top-level module
    from embedding_cache import CachedEmbedder


def _connect_from_env():
    url = os.environ["EVAL_DATABASE_URL"]
    conn = psycopg2.connect(url)
    register_vector(conn)
    return conn


def main() -> None:
    conn = _connect_from_env()
    try:
        create_db(conn)
        n = seed_corpus_sync(conn, embedder=CachedEmbedder())
        print(f"MYDEBUG -> seeded {n} documents into eval DB")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
