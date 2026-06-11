#!/usr/bin/env python3
"""Print whether env vars required by rag-ingest-worker are set (values not shown)."""

from __future__ import annotations

import sys

from app.config import (
    DATABASE_URL,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REFRESH_TOKEN,
    INGEST_WORKER_ENABLED,
    OPENAI_API_KEY,
)

REQUIRED = {
    "DATABASE_URL": DATABASE_URL,
    "OPENAI_API_KEY": OPENAI_API_KEY,
    "GOOGLE_CLIENT_ID": GOOGLE_CLIENT_ID,
    "GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET,
    "GOOGLE_REFRESH_TOKEN": GOOGLE_REFRESH_TOKEN,
}


def main() -> int:
    print("rag-ingest-worker env check")
    print(f"  INGEST_WORKER_ENABLED={INGEST_WORKER_ENABLED}")
    missing: list[str] = []
    for name, value in REQUIRED.items():
        ok = bool(value and str(value).strip())
        print(f"  {name}: {'ok' if ok else 'MISSING'}")
        if not ok:
            missing.append(name)
    if missing:
        print("\nFix: copy these from rag-document-analysis-backend on Render (or .env locally).")
        return 1
    if not INGEST_WORKER_ENABLED:
        print("\nWarning: INGEST_WORKER_ENABLED is off; worker will exit immediately.")
        return 1
    print("\nAll required vars present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
