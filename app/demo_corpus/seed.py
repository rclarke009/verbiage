"""Seed the demo/eval synthetic corpus into Postgres."""

from __future__ import annotations

import asyncio
from pathlib import Path

import yaml

from app.db import insert_document, update_document_geo_storm_metadata
from app.indexing import index_document
from app.models import ChunkingOptions

CORPUS_DIR = Path(__file__).parent
METADATA_PATH = CORPUS_DIR / "metadata.yaml"
SEED_CREATED_AT = 1_700_000_000
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


async def seed_corpus(conn, embedder=None) -> int:
    """Insert + index every corpus document. Returns the number of documents seeded."""
    if embedder is None:
        from app.embeddings import HttpEmbedder

        embedder = HttpEmbedder()

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


def seed_corpus_sync(conn, embedder=None) -> int:
    return asyncio.run(seed_corpus(conn, embedder))
