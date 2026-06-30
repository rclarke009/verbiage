"""
Config from environment: database, embedding/LLM URLs and models, Google Drive.
Sensible defaults where safe; no default secrets.
"""

import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

load_dotenv()

# Database: SQLite (local) or Postgres (Supabase)
# - For SQLite: set DATABASE_PATH (default verbiage.db). Leave DATABASE_URL unset/empty.
# - For Postgres/Supabase: set DATABASE_URL to the Postgres connection string from
#   Project Settings → Database → "Connection string" (choose URI). It looks like:
#   postgresql://postgres.[ref]:[PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres
#   (This is not the project URL https://xxx.supabase.co — that's for the JS client.)
#   Use pooler port 6543 for short-lived connections; use with psycopg2 or asyncpg.
#   Supabase requires SSL: we add sslmode=require for pooler URLs if not already set.
_raw_database_url = os.getenv("DATABASE_URL", "").strip().strip("'\"")
if _raw_database_url:
    _sep = "&" if "?" in _raw_database_url else "?"
    if "pooler.supabase.com" in _raw_database_url and "sslmode=" not in _raw_database_url:
        _raw_database_url = f"{_raw_database_url}{_sep}sslmode=require"
DATABASE_URL = _raw_database_url


def _parse_database_url(url: str) -> dict | None:
    """Parse Postgres URI into kwargs for psycopg2.connect(). Handles passwords with =, &, ?."""
    if not url:
        return None
    p = urlparse(url)
    netloc = p.netloc
    if "@" not in netloc:
        return None
    userinfo, _, hostport = netloc.rpartition("@")
    user, _, password = userinfo.partition(":")
    if not user or not hostport:
        return None
    host, _, port_str = hostport.rpartition(":")
    port = int(port_str) if port_str.isdigit() else 5432
    dbname = (p.path or "/postgres").lstrip("/") or "postgres"
    kwargs: dict = {"host": host, "port": port, "user": user, "password": password, "dbname": dbname}
    qs = parse_qs(p.query)
    if "sslmode" in qs:
        kwargs["sslmode"] = qs["sslmode"][0]
    elif "pooler.supabase.com" in host and port == 6543:
        kwargs["sslmode"] = "require"
    return kwargs


# Parsed connection kwargs for psycopg2 (avoids DSN parse errors when password contains =, &, ?).
DATABASE_CONNECTION_KWARGS = _parse_database_url(DATABASE_URL) if DATABASE_URL else None


def report_writer_database_url() -> str:
    """Postgres URL for LangGraph AsyncPostgresSaver.

    Supabase transaction-mode pooler (port 6543) breaks psycopg3 checkpointer setup even with
    prepare_threshold=0. Prefer session mode (5432), then DIRECT_DATABASE_URL, then DATABASE_URL.
    """
    direct = os.getenv("DIRECT_DATABASE_URL", "").strip().strip("'\"")
    if direct:
        return direct
    if "pooler.supabase.com" in DATABASE_URL and ":6543" in DATABASE_URL:
        return DATABASE_URL.replace(":6543/", ":5432/", 1)
    return DATABASE_URL

DB_PATH = os.getenv("DATABASE_PATH", "verbiage.db")

# OpenAI: when OPENAI_API_KEY is set, use OpenAI for embeddings and LLM first; optional fallback to Ollama via env flags.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
EMBED_LOCAL_ONLY = os.getenv("EMBED_LOCAL_ONLY", "").lower() in ("1", "true", "yes")
EMBED_FALLBACK_TO_LOCAL = os.getenv("EMBED_FALLBACK_TO_LOCAL", "").lower() in ("1", "true", "yes")
LLM_FALLBACK_TO_LOCAL = os.getenv("LLM_FALLBACK_TO_LOCAL", "").lower() in ("1", "true", "yes")

# Embeddings: OpenAI (text-embedding-3-small with dimensions=768) or Ollama
EMBED_BASE_URL = os.getenv("EMBED_BASE_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
EMBED_TIMEOUT = int(os.getenv("EMBED_TIMEOUT", 30))
EMBED_MAX_ATTEMPTS = int(os.getenv("EMBED_MAX_ATTEMPTS", 3))

# LLM: OpenAI (gpt-4o-mini or LLM_OPENAI_MODEL) or Ollama
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
LLM_OPENAI_MODEL = os.getenv("LLM_OPENAI_MODEL", "gpt-4o-mini")
# Low (not zero) so borderline retrievals resolve consistently toward quoting relevant
# passages instead of flip-flopping into spurious "not enough context" refusals.
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", 60))
LLM_MAX_ATTEMPTS = int(os.getenv("LLM_MAX_ATTEMPTS", 3))
LLM_TOKEN_LIMIT = int(os.getenv("LLM_TOKEN_LIMIT", 10))
LLM_RATE_LIMIT_SECONDS = int(os.getenv("LLM_RATE_LIMIT_SECONDS", 60))

# Health: /health/ready (DB); /health/deep (DB + embed; optional LLM via HEALTH_DEEP_CHECK_LLM)
HEALTH_DEEP_TIMEOUT = int(os.getenv("HEALTH_DEEP_TIMEOUT", "5"))
# Ingest background worker (Postgres job queue)
INGEST_WORKER_ENABLED = os.getenv("INGEST_WORKER_ENABLED", "1").strip().lower() in ("1", "true", "yes")
# Reclaim ingest_jobs stuck in running after a crash/OOM (worker startup + periodic reclaim).
STALE_JOB_MINUTES = int(os.getenv("STALE_JOB_MINUTES", "15"))

# Report export (PDF/DOCX): cap embedded photos to avoid OOM/timeouts on small Render instances.
REPORT_EXPORT_MAX_PHOTOS = max(0, int(os.getenv("REPORT_EXPORT_MAX_PHOTOS", "12")))
REPORT_EXPORT_DAMAGE_PHOTOS_ONLY = os.getenv("REPORT_EXPORT_DAMAGE_PHOTOS_ONLY", "1").strip().lower() in (
    "1",
    "true",
    "yes",
)

HEALTH_DEEP_CHECK_LLM = os.getenv("HEALTH_DEEP_CHECK_LLM", "").lower() in ("1", "true", "yes")


def _google_env(name: str, default: str = "") -> str:
    """Strip whitespace and a single pair of outer quotes (common .env paste mistakes)."""
    raw = os.getenv(name, default) or ""
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        v = v[1:-1].strip()
    return v


GOOGLE_CLIENT_ID = _google_env("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = _google_env("GOOGLE_CLIENT_SECRET")
GOOGLE_REFRESH_TOKEN = _google_env("GOOGLE_REFRESH_TOKEN")
GOOGLE_REDIRECT_URI = _google_env(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback"
)
GOOGLE_DRIVE_DEFAULT_FOLDER_ID = _google_env("GOOGLE_DRIVE_DEFAULT_FOLDER_ID")
GOOGLE_DRIVE_DEFAULT_FOLDER_LABEL = _google_env("GOOGLE_DRIVE_DEFAULT_FOLDER_LABEL")
# Jobs root: parent folder of address-named job photo folders (Report Writer Step 1 lookup).
GOOGLE_DRIVE_JOBS_ROOT_FOLDER_ID = _google_env("GOOGLE_DRIVE_JOBS_ROOT_FOLDER_ID")
GOOGLE_DRIVE_JOBS_ROOT_FOLDER_LABEL = _google_env("GOOGLE_DRIVE_JOBS_ROOT_FOLDER_LABEL")
GOOGLE_MAPS_API_KEY = _google_env("GOOGLE_MAPS_API_KEY")

# Supabase Auth: verify JWTs and expose URL/anon key to frontend via GET /config
# SUPABASE_JWT_SECRET must be Project Settings → API → JWT Secret (the symmetric secret used
# to verify access tokens). Do not use the anon key, service role key, or a secret from another project.
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "").strip()
# Server-only: create users via Auth Admin API (never expose to the browser)
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
# Optional shared invite code; if set, matching code allows signup without an allowlist row
SIGNUP_INVITE_CODE = os.getenv("SIGNUP_INVITE_CODE", "").strip()
# Optional canonical browser origin for auth email links (password reset redirect). No trailing slash.
PUBLIC_APP_URL = os.getenv("PUBLIC_APP_URL", "").strip().rstrip("/")

# RAG relevance gate: /ask refuses (no LLM call, canary marker) when the best retrieved
# chunk's cosine similarity to the query is below this. Cosine is the only signal that is
# comparable across queries -- RRF (hybrid) and ts_rank (lexical) are rank/term-frequency
# artifacts whose magnitude says nothing about absolute relevance -- so the gate always
# evaluates the cosine component regardless of retrieval mode. Pure lexical lookups carry
# no cosine and are exempt (a lexical hit already means the query terms matched).
# 0.5 reliably refuses clearly off-corpus questions (cosine ~0.42 on the eval corpus) while
# clearing every grounded gold question (lowest grounded cosine ~0.56). Borderline off-topic
# queries that score just above the gate still depend on the model's own refusal.
RAG_MIN_RELEVANCE_SCORE = float(os.getenv("RAG_MIN_RELEVANCE_SCORE", "0.5"))

# Prometheus metrics: expose GET /metrics when METRICS_ENABLED; optional Bearer METRICS_TOKEN for scrape auth.
def metrics_enabled() -> bool:
    """True when METRICS_ENABLED env is set (read each time for tests)."""
    return os.getenv("METRICS_ENABLED", "").lower() in ("1", "true", "yes")


METRICS_ENABLED = metrics_enabled()
METRICS_TOKEN = os.getenv("METRICS_TOKEN", "").strip()
# When set (e.g. 0.35), increments rag_retrieval_low_quality_total when top-1 similarity is below this but chunks exist.
_raw_sim_thresh = os.getenv("RAG_SIMILARITY_ALERT_THRESHOLD", "").strip()
RAG_SIMILARITY_ALERT_THRESHOLD: float | None = (
    float(_raw_sim_thresh) if _raw_sim_thresh else None
)

# Visual Crossing Timeline API — historical wind for Report Writer weather section.
VISUAL_CROSSING_API_KEY = os.getenv("VISUAL_CROSSING_API_KEY", "").strip()

# Multi-source weather aggregation
WEATHER_MAX_DISTANCE_MI = float(os.getenv("WEATHER_MAX_DISTANCE_MI", "50"))
WEATHER_ENABLE_OPEN_METEO = os.getenv("WEATHER_ENABLE_OPEN_METEO", "true").lower() in (
    "1",
    "true",
    "yes",
)
OPEN_METEO_ATTRIBUTION = os.getenv(
    "OPEN_METEO_ATTRIBUTION",
    "Open-Meteo (CC BY 4.0)",
).strip()

# Nominatim (OpenStreetMap) address autocomplete — Report Writer Step 1.
# Public API requires a valid User-Agent; see https://operations.osmfoundation.org/policies/nominatim/
NOMINATIM_USER_AGENT = os.getenv(
    "NOMINATIM_USER_AGENT",
    "Verbiage/1.0 (local dev)",
).strip()
NOMINATIM_BASE_URL = os.getenv(
    "NOMINATIM_BASE_URL",
    "https://nominatim.openstreetmap.org",
).strip().rstrip("/")

# Cross-encoder reranking of the retrieved candidate pool before prompt assembly.
# Off by default: loading the ~100MB CrossEncoder is undesirable in tests/CI. Enable
# in deployment with RERANK_ENABLED=1.
RERANK_ENABLED = os.getenv("RERANK_ENABLED", "").lower() in ("1", "true", "yes")

# Demo deployment (separate Render service + Supabase). All demo-only behavior requires DEMO_MODE=1.
DEMO_MODE = os.getenv("DEMO_MODE", "").strip().lower() in ("1", "true", "yes")
DEMO_OPEN_SIGNUP = os.getenv("DEMO_OPEN_SIGNUP", "").strip().lower() in ("1", "true", "yes")
DEMO_ASK_LIMIT = max(1, int(os.getenv("DEMO_ASK_LIMIT", "10")))
DEMO_ASK_WINDOW_SECONDS = max(60, int(os.getenv("DEMO_ASK_WINDOW_SECONDS", "3600")))
DEMO_SIGNUP_LIMIT = max(1, int(os.getenv("DEMO_SIGNUP_LIMIT", "5")))
DEMO_SIGNUP_WINDOW_SECONDS = max(60, int(os.getenv("DEMO_SIGNUP_WINDOW_SECONDS", "3600")))
DEMO_GATE_MESSAGE_TEMPLATE = os.getenv(
    "DEMO_GATE_MESSAGE_TEMPLATE",
    "{feature} is available in the full version. Contact us for details.",
).strip()
