"""Fail-fast checks so demo mode never serves a prod or non-synthetic corpus."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.config import (
    DATABASE_URL,
    DEMO_DATABASE_URL,
    DEMO_MODE,
    GOOGLE_REFRESH_TOKEN,
    PROD_SUPABASE_PROJECT_REF,
    SUPABASE_URL,
    dual_tenant_enabled,
)

if TYPE_CHECKING:
    from psycopg2.extensions import connection as PgConnection

_DB_REF_RE = re.compile(
    r"(?:postgres\.([a-z0-9]+)|db\.([a-z0-9]+)\.supabase\.co)",
    re.IGNORECASE,
)
_SUPABASE_URL_REF_RE = re.compile(r"https?://([a-z0-9]+)\.supabase\.co", re.IGNORECASE)


def extract_supabase_project_ref_from_database_url(url: str) -> str | None:
    """Parse Supabase project ref from a Postgres connection URI."""
    match = _DB_REF_RE.search(url or "")
    if not match:
        return None
    return (match.group(1) or match.group(2)).lower()


def extract_supabase_project_ref_from_supabase_url(url: str) -> str | None:
    """Parse Supabase project ref from https://<ref>.supabase.co."""
    match = _SUPABASE_URL_REF_RE.search(url or "")
    if not match:
        return None
    return match.group(1).lower()


def assert_demo_database_config() -> None:
    """Refuse demo/dual-tenant startup when the demo URL points at TrueDB or Drive is on a demo-only process."""
    if dual_tenant_enabled():
        demo_ref = extract_supabase_project_ref_from_database_url(DEMO_DATABASE_URL)
        if PROD_SUPABASE_PROJECT_REF and demo_ref and demo_ref == PROD_SUPABASE_PROJECT_REF:
            raise RuntimeError(
                "Dual tenant: DEMO_DATABASE_URL points at the production Supabase project "
                f"({demo_ref}). Use the verbiage-demo project for DEMO_DATABASE_URL."
            )
        live_ref = extract_supabase_project_ref_from_database_url(DATABASE_URL)
        if PROD_SUPABASE_PROJECT_REF and live_ref and live_ref != PROD_SUPABASE_PROJECT_REF:
            raise RuntimeError(
                "Dual tenant: DATABASE_URL does not point at the production Supabase project "
                f"(expected {PROD_SUPABASE_PROJECT_REF}, got {live_ref}). "
                "Signed-in users would search the demo corpus. "
                "Set DATABASE_URL to TrueDB and DEMO_DATABASE_URL to verbiage-demo."
            )
        return

    if not DEMO_MODE:
        return

    if GOOGLE_REFRESH_TOKEN:
        raise RuntimeError(
            "Demo mode: GOOGLE_REFRESH_TOKEN must not be set. "
            "Use a demo-only Supabase project with scripts/seed_demo_db.py."
        )

    db_ref = extract_supabase_project_ref_from_database_url(DATABASE_URL)
    if PROD_SUPABASE_PROJECT_REF and db_ref and db_ref == PROD_SUPABASE_PROJECT_REF:
        raise RuntimeError(
            "Demo mode: DATABASE_URL points at the production Supabase project "
            f"({db_ref}). Use the demo Supabase project and run scripts/seed_demo_db.py."
        )

    if SUPABASE_URL and db_ref:
        api_ref = extract_supabase_project_ref_from_supabase_url(SUPABASE_URL)
        if api_ref and api_ref != db_ref:
            raise RuntimeError(
                "Demo mode: DATABASE_URL and SUPABASE_URL refer to different Supabase "
                f"projects (db={db_ref}, api={api_ref})."
            )


def assert_demo_database_content(conn: PgConnection) -> None:
    """Refuse demo startup when the DB already holds non-synthetic documents."""
    if not DEMO_MODE and not dual_tenant_enabled():
        return

    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT source, COUNT(*)::int
            FROM documents
            WHERE source IS DISTINCT FROM 'eval_fixture'
            GROUP BY source
            ORDER BY COUNT(*) DESC
            LIMIT 5
            """
        )
        rows = cur.fetchall()
        if rows:
            detail = ", ".join(f"{src or '(null)'}={count}" for src, count in rows)
            raise RuntimeError(
                "Demo mode: database contains non-synthetic documents "
                f"({detail}). Use a demo-only Supabase project seeded with "
                "scripts/seed_demo_db.py."
            )
    finally:
        cur.close()
