"""Lightweight ingest worker entrypoint for Render background worker service."""

from __future__ import annotations

import asyncio
import logging
import sys

from app.config import (
    DATABASE_URL,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REFRESH_TOKEN,
    INGEST_WORKER_ENABLED,
    OPENAI_API_KEY,
)
from app.db import create_db, create_db_pool, get_valid_conn
from app.ingest_worker import ingest_worker_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_WORKER_REQUIRED = {
    "DATABASE_URL": DATABASE_URL,
    "OPENAI_API_KEY": OPENAI_API_KEY,
    "GOOGLE_CLIENT_ID": GOOGLE_CLIENT_ID,
    "GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET,
    "GOOGLE_REFRESH_TOKEN": GOOGLE_REFRESH_TOKEN,
}


def _verify_worker_env() -> None:
    missing = [name for name, val in _WORKER_REQUIRED.items() if not (val and str(val).strip())]
    if missing:
        logger.error(
            "Worker missing required env (copy from rag-document-analysis-backend): %s",
            ", ".join(missing),
        )
        sys.exit(1)
    logger.info(
        "Worker env ok (DATABASE_URL, OPENAI_API_KEY, GOOGLE_* set; INGEST_WORKER_ENABLED=%s)",
        INGEST_WORKER_ENABLED,
    )


async def main() -> None:
    if not INGEST_WORKER_ENABLED:
        logger.error("INGEST_WORKER_ENABLED=0; worker exiting")
        sys.exit(1)
    _verify_worker_env()

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
