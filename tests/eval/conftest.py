"""Fixtures + markers for the faithfulness eval suite.

The whole suite is opt-in (set VERBIAGE_EVAL=1), mirroring the VERBIAGE_INTEGRATION
gate in tests/test_retrieval_integration.py, so a normal `pytest` run stays fast
and offline.

DB lifecycle:
  - EVAL_DATABASE_URL  : Postgres URL for the throwaway eval DB
                         (default postgresql://postgres:postgres@localhost:5433/verbiage_eval).
  - When EVAL_DATABASE_URL is NOT explicitly set, the session fixture brings the
    docker-compose.eval.yml container up (--wait) and tears it down afterwards, so
    `pytest -m eval_fast tests/eval` is self-contained. `make eval` instead sets
    EVAL_DATABASE_URL and manages the container itself.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).parent
REPO_ROOT = EVAL_DIR.parent.parent
COMPOSE_FILE = REPO_ROOT / "docker-compose.eval.yml"
DEFAULT_URL = "postgresql://postgres:postgres@localhost:5433/verbiage_eval"

# Make sibling helper modules importable as top-level (seed, runner, judges, ...).
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

ENABLED = os.getenv("VERBIAGE_EVAL") == "1"

# When the eval is not opted into, skip collecting its test modules entirely. This
# keeps a normal `pytest` run green and avoids importing eval-only deps (yaml,
# sentence-transformers) or touching app.main during collection.
if not ENABLED:
    collect_ignore_glob = ["test_*.py"]

pytestmark = pytest.mark.skipif(
    not ENABLED, reason="faithfulness eval: set VERBIAGE_EVAL=1 to run"
)


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "eval_fast: fast faithfulness gate (local NLI judge); run after every tweak"
    )
    config.addinivalue_line(
        "markers", "eval_full: deep faithfulness eval (OpenAI LLM judge); nightly/manual"
    )


def _compose(*args: str) -> None:
    # --env-file /dev/null: the eval stack uses no repo .env vars; skipping it avoids
    # docker compose interpolation warnings from $-containing secrets in .env.
    subprocess.run(
        ["docker", "compose", "--env-file", "/dev/null", "-f", str(COMPOSE_FILE), *args],
        check=True,
        cwd=str(REPO_ROOT),
    )


def _connect(url: str):
    """Open a raw connection, retrying only on genuine connection errors.

    The pgvector adapter is intentionally NOT registered here: the `vector` type
    does not exist until create_db() runs `CREATE EXTENSION vector`. create_db()
    registers the adapter on this same connection afterwards (via _ensure_pgvector),
    matching exactly how production initializes a connection in app/db.py.
    """
    import psycopg2

    last_exc = None
    for _ in range(30):
        try:
            return psycopg2.connect(url)
        except psycopg2.OperationalError as e:  # container may still be starting
            last_exc = e
            time.sleep(1)
    raise RuntimeError(f"could not connect to eval DB at {url}: {last_exc}")


@pytest.fixture(scope="session")
def eval_conn():
    """Ephemeral pgvector DB: (optionally) start container, create schema, seed corpus."""
    from app.db import create_db
    from seed import seed_corpus_sync

    manage = "EVAL_DATABASE_URL" not in os.environ
    url = os.getenv("EVAL_DATABASE_URL", DEFAULT_URL)

    if manage:
        if not COMPOSE_FILE.exists():
            pytest.skip(f"compose file not found: {COMPOSE_FILE}")
        _compose("up", "-d", "--wait")

    conn = None
    try:
        conn = _connect(url)
        create_db(conn)
        seed_corpus_sync(conn)
        yield conn
    finally:
        if conn is not None:
            conn.close()
        if manage:
            _compose("down", "-v")
