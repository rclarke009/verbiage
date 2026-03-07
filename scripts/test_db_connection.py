#!/usr/bin/env python3
"""
Test Postgres/Supabase connection using DATABASE_URL from .env.
Run from project root: python scripts/test_db_connection.py
Tries: (1) pooler 5432, (2) pooler 6543, (3) direct db.REF.supabase.co (IPv6).
Also runs a TLS-only probe to see if the server closes during TLS or after.
Exits 0 on success.
"""
import os
import re
import socket
import ssl
import sys
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, urlunparse

# Load .env from project root
root = Path(__file__).resolve().parent.parent
dotenv = root / ".env"
if dotenv.exists():
    for line in dotenv.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            v = v.strip().strip("'\"")
            os.environ.setdefault(k.strip(), v)

url = os.getenv("DATABASE_URL", "").strip()
if not url:
    print("MYDEBUG → DATABASE_URL is not set (check .env)", file=sys.stderr)
    sys.exit(1)

# Same SSL fix as app/config.py for Supabase
if "pooler.supabase.com" in url and "sslmode=" not in url:
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}sslmode=require"


def tls_probe(host: str, port: int) -> bool:
    """Try a plain TLS handshake to host:port. Returns True if handshake completes."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                pass
        return True
    except Exception as e:
        print(f"MYDEBUG → TLS probe {host}:{port} failed: {e}", file=sys.stderr)
        return False


def try_connect(conn_url: str, label: str) -> bool:
    import psycopg2
    try:
        conn = psycopg2.connect(conn_url)
        cur = conn.cursor()
        cur.execute("SELECT 1 AS ok")
        row = cur.fetchone()
        cur.close()
        conn.close()
        print(f"MYDEBUG → {label} → SELECT 1 → {row}")
        print("Connection OK.")
        return True
    except Exception as e:
        print(f"MYDEBUG → {label} failed: {type(e).__name__}: {e}", file=sys.stderr)
        return False


def switch_pooler_port(conn_url: str, new_port: int) -> str:
    """Replace pooler port in URI (e.g. 5432 -> 6543)."""
    return re.sub(r":5432/", f":{new_port}/", conn_url)


def build_direct_url(pooler_url: str) -> str | None:
    """
    Build Supabase direct connection URL (db.REF.supabase.co, user postgres).
    Direct uses IPv6 by default and can succeed when pooler (IPv4) fails.
    """
    try:
        p = urlparse(pooler_url)
        if not p.hostname or "pooler.supabase.com" not in p.hostname:
            return None
        # Username is postgres.REF (e.g. postgres.dunxzvbxekxqrfnmtzmj)
        if not p.username or not p.username.startswith("postgres."):
            return None
        ref = p.username.split(".", 1)[1]
        # p.password may be already decoded by urlparse; unquote then quote to avoid double-encode
        password = unquote(p.password or "")
        encoded_password = quote(password, safe="")
        direct_host = f"db.{ref}.supabase.co"
        # Build postgresql://postgres:ENC@db.REF.supabase.co:5432/postgres?sslmode=require
        netloc = f"postgres:{encoded_password}@{direct_host}:5432"
        new_p = p._replace(netloc=netloc)
        direct = urlunparse(new_p)
        params = []
        if "sslmode=" not in direct:
            params.append("sslmode=require")
        params.append("gssencmode=disable")  # avoid GSSAPI/Kerberos "Credential cache is empty"
        direct += "?" if "?" not in direct else "&"
        direct += "&".join(params)
        return direct
    except Exception:
        return None


if "@" in url and ".supabase.com" in url:
    try:
        part = url.split("@", 1)[1].split("/")[0]
        print(f"MYDEBUG → Host:port = {part}")
    except Exception:
        pass

# TLS-only probe: if the server closes during TLS, we see it here (no Postgres involved).
if "pooler.supabase.com" in url:
    try:
        p = urlparse(url)
        host, port = p.hostname, p.port or 5432
        print("MYDEBUG → TLS probe (no Postgres)...", file=sys.stderr)
        if tls_probe(host, port):
            print("MYDEBUG → TLS handshake to pooler OK; failure is likely Postgres-level.", file=sys.stderr)
        else:
            print("MYDEBUG → TLS handshake failed; connection is being closed during SSL.", file=sys.stderr)
    except Exception as e:
        print(f"MYDEBUG → TLS probe error: {e}", file=sys.stderr)

if try_connect(url, "port 5432 (session)"):
    sys.exit(0)

if "pooler.supabase.com" in url and ":5432" in url:
    url_6543 = switch_pooler_port(url, 6543)
    print("MYDEBUG → Retrying with port 6543 (transaction mode)...", file=sys.stderr)
    if try_connect(url_6543, "port 6543 (transaction)"):
        print(
            "\nUse DATABASE_URL with port 6543 in .env.",
            file=sys.stderr,
        )
        sys.exit(0)

# Direct connection: try exact string from dashboard first, else build from pooler URL.
direct_url = os.getenv("DIRECT_DATABASE_URL", "").strip()
if direct_url:
    if "sslmode=" not in direct_url:
        direct_url += "&sslmode=require" if "?" in direct_url else "?sslmode=require"
    if "gssencmode=" not in direct_url:
        direct_url += "&gssencmode=disable" if "?" in direct_url else "?gssencmode=disable"
elif "pooler.supabase.com" in url:
    direct_url = build_direct_url(url)
else:
    direct_url = None
if direct_url:
    label = "direct (DIRECT_DATABASE_URL)" if os.getenv("DIRECT_DATABASE_URL") else "direct (db.REF.supabase.co)"
    print(f"MYDEBUG → Retrying with direct connection ({label})...", file=sys.stderr)
    if try_connect(direct_url, label):
        print(
            "\nDirect works. In .env set DATABASE_URL to the Direct URI (Supabase → Connect → Direct)\n"
            "so the app uses it. Add gssencmode=disable if you see GSSAPI errors.",
            file=sys.stderr,
        )
        sys.exit(0)

print(
    "\nAll connection types failed. 'Server closed the connection unexpectedly' often means:\n"
    "  - TLS/SSL is being closed by the server or a middlebox (firewall, VPN, ISP).\n"
    "  - Try from another network (e.g. phone hotspot) to rule out local firewall/DPI.\n"
    "  - If TLS probe also failed, the path to Supabase may be blocking or altering TLS.",
    file=sys.stderr,
)
sys.exit(1)
