"""Tests for nearby-storm structured document retrieval."""

import psycopg2
import pytest
from pgvector.psycopg2 import register_vector

from app.db import (
    create_db,
    insert_document,
    retrieve_nearby_storm_docs,
    update_document_geo_storm_metadata,
)


@pytest.fixture
def conn():
    c = psycopg2.connect("postgresql://postgres:postgres@localhost:5433/verbiage_eval")
    register_vector(c)
    yield c
    c.close()


@pytest.mark.skip(reason="requires eval Postgres with seeded corpus; run via make eval")
def test_retrieve_nearby_storm_docs_orders_by_distance(conn):
    rows = retrieve_nearby_storm_docs(
        conn,
        storm_id="ian-2022",
        latitude=26.976,
        longitude=-82.090,
        limit=3,
    )
    assert len(rows) >= 2
    addresses = [row[2] or row[1] or "" for row in rows]
    assert any("Maple" in addr for addr in addresses)
    distances = [row[3] for row in rows]
    assert distances == sorted(distances)


def test_retrieve_nearby_storm_docs_in_memory_sqlite_style():
    """Unit test with ephemeral connection when DATABASE_URL unavailable uses create_db pattern."""
    # Lightweight test using any postgres - skip if not available
    try:
        c = psycopg2.connect("postgresql://postgres:postgres@localhost:5433/verbiage_eval")
    except Exception:
        pytest.skip("eval postgres not running")
    register_vector(c)
    try:
        create_db(c)
        for doc_id, lat, lng, addr in (
            ("near_a", 26.955, -82.055, "100 Maple Court"),
            ("near_b", 26.935, -82.035, "200 Birch Avenue"),
            ("far_c", 27.773, -82.407, "6317 Wisteria Lane"),
        ):
            if not _doc_exists(c, doc_id):
                insert_document(c, doc_id, 1, title=addr, source="test", full_text="x")
            update_document_geo_storm_metadata(
                c,
                doc_id,
                storm_id="ian-2022",
                storm_name="Ian",
                storm_date_iso="2022-09-28",
                address=addr,
                latitude=lat,
                longitude=lng,
            )
        c.commit()

        rows = retrieve_nearby_storm_docs(
            c,
            storm_id="ian-2022",
            latitude=26.976,
            longitude=-82.090,
            limit=2,
        )
        assert len(rows) == 2
        assert "Maple" in (rows[0][2] or "")
    finally:
        c.close()


def _doc_exists(conn, doc_id: str) -> bool:
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM documents WHERE doc_id = %s", (doc_id,))
        return cur.fetchone() is not None
    finally:
        cur.close()
