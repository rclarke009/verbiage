"""Seed the ephemeral eval DB with the frozen corpus.

Reuses the exact ingest path the app uses (insert_document -> index_document),
so chunking, embedding storage, and the content_tsv full-text column are all
populated the same way as production. Embeddings come from CachedEmbedder so the
seed is reproducible run-to-run.

Run standalone to (re)warm the embeddings cache against a live backend:

    EVAL_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/verbiage_eval \
      python -m tests.eval.seed
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import yaml

from app.db import create_db, insert_document, update_document_geo_storm_metadata
from app.indexing import index_document
from app.models import ChunkingOptions

try:  # support both `python -m tests.eval.seed` and pytest's path-based import
    from .embedding_cache import CachedEmbedder
except ImportError:  # pragma: no cover - fallback when imported as a top-level module
    from embedding_cache import CachedEmbedder

CORPUS_DIR = Path(__file__).parent / "corpus"
METADATA_PATH = Path(__file__).parent / "corpus_metadata.yaml"
# Fixed timestamp keeps document rows byte-stable across reseeds.
SEED_CREATED_AT = 1_700_000_000
# Pin chunking so retrieval behaviour under test is the app default, held constant.
CHUNKING = ChunkingOptions()


def corpus_docs() -> list[tuple[str, str, str]]:
    """Return (doc_id, title, full_text) for every report in the corpus dir."""
    docs = []
    for path in sorted(CORPUS_DIR.glob("*.txt")):
        text = path.read_text().strip()
        title = text.splitlines()[0].strip() if text else path.stem
        docs.append((path.stem, title, text))
    return docs


def load_corpus_metadata() -> dict[str, dict]:
    if not METADATA_PATH.exists():
        return {}
    data = yaml.safe_load(METADATA_PATH.read_text()) or {}
    return data if isinstance(data, dict) else {}


async def seed_corpus(conn, embedder: CachedEmbedder | None = None) -> int:
    """Insert + index every corpus document. Returns the number of documents seeded."""
    embedder = embedder or CachedEmbedder()
    metadata_by_doc = load_corpus_metadata()
    docs = corpus_docs()
    for doc_id, title, full_text in docs:
        insert_document(
            conn,
            doc_id,
            SEED_CREATED_AT,
            title=title,
            source="eval_fixture",
            full_text=full_text,
        )
        meta = metadata_by_doc.get(doc_id, {})
        if meta:
            update_document_geo_storm_metadata(
                conn,
                doc_id,
                storm_id=meta.get("storm_id"),
                storm_name=meta.get("storm_name"),
                storm_date_iso=meta.get("storm_date_iso"),
                address=meta.get("address"),
                latitude=meta.get("latitude"),
                longitude=meta.get("longitude"),
            )
        await index_document(conn, doc_id, full_text, CHUNKING, embedder=embedder)
    conn.commit()
    return len(docs)


def _connect_from_env():
    import os

    import psycopg2
    from pgvector.psycopg2 import register_vector

    url = os.environ["EVAL_DATABASE_URL"]
    conn = psycopg2.connect(url)
    register_vector(conn)
    return conn


def main() -> None:
    conn = _connect_from_env()
    try:
        create_db(conn)
        n = seed_corpus_sync(conn)
        print(f"MYDEBUG -> seeded {n} documents into eval DB")
    finally:
        conn.close()


def seed_corpus_sync(conn, embedder: CachedEmbedder | None = None) -> int:
    return asyncio.run(seed_corpus(conn, embedder))


if __name__ == "__main__":
    main()
