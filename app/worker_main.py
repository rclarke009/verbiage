"""Lightweight ingest worker entrypoint for Render background worker service."""

from __future__ import annotations

import asyncio
import logging
import sys

from app.config import DATABASE_URL, INGEST_WORKER_ENABLED
from app.db import create_db, create_db_pool, get_valid_conn
from app.ingest_worker import ingest_worker_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL must be set for ingest worker")
    if not INGEST_WORKER_ENABLED:
        logger.error("INGEST_WORKER_ENABLED=0; worker exiting")
        sys.exit(1)

    pool = create_db_pool()
    conn = get_valid_conn(pool)
    try:
        create_db(conn)
        conn.commit()
    finally:
        pool.putconn(conn)

    logger.info("Standalone ingest worker running (no web/reranker/report-writer)")
    await ingest_worker_loop(pool)


if __name__ == "__main__":
    asyncio.run(main())
