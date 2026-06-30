"""
Supabase Auth: verify JWT from Authorization header and expose current user to routes.

Supports legacy HS256 tokens (SUPABASE_JWT_SECRET) and asymmetric ES256/RS256 tokens
via Supabase JWKS ({SUPABASE_URL}/auth/v1/.well-known/jwks.json).
"""

import logging
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import SUPABASE_JWT_SECRET, SUPABASE_URL
from app.demo import DEMO_GUEST_USER_ID, demo_anonymous_enabled, is_demo_mode

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

_jwks_client: PyJWKClient | None = None


def _jwks_url() -> str | None:
    if not SUPABASE_URL:
        return None
    return f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"


def _get_jwks_client() -> PyJWKClient | None:
    global _jwks_client
    url = _jwks_url()
    if not url:
        return None
    if _jwks_client is None:
        _jwks_client = PyJWKClient(url, cache_keys=True)
    return _jwks_client


def _reset_jwks_client_for_tests() -> None:
    """Clear cached JWKS client (tests only)."""
    global _jwks_client
    _jwks_client = None


def _auth_configured() -> bool:
    return bool(SUPABASE_JWT_SECRET or _jwks_url())


def verify_supabase_token(token: str) -> dict:
    """
    Decode and verify a Supabase access token (JWT). Returns payload dict with at least 'sub' (user id).
    Raises jwt.InvalidTokenError if invalid or expired.
    """
    decode_options = {"verify_aud": True}
    audience = "authenticated"

    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        raise

    alg = header.get("alg")
    if alg == "HS256":
        if not SUPABASE_JWT_SECRET:
            raise jwt.InvalidTokenError("HS256 token but SUPABASE_JWT_SECRET is not configured")
        return jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience=audience,
            options=decode_options,
        )

    if alg in ("ES256", "RS256"):
        client = _get_jwks_client()
        if not client:
            raise jwt.InvalidTokenError(f"{alg} token but Supabase JWKS is not configured (set SUPABASE_URL)")
        signing_key = client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=[alg],
            audience=audience,
            options=decode_options,
        )

    raise jwt.InvalidTokenError(f"Unsupported JWT algorithm: {alg}")


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
) -> str:
    """
    FastAPI dependency: require valid Supabase JWT and return the user id (sub).
    Returns 401 if missing or invalid.
    """
    if not _auth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase Auth not configured (set SUPABASE_URL and/or SUPABASE_JWT_SECRET)",
        )
    token = None
    if credentials:
        token = credentials.credentials
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header (Bearer token required)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = verify_supabase_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        # Log at warning so deploy logs (e.g. Render) show signature/audience errors; never log the token.
        logger.warning("JWT verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token (no sub)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return sub


def get_ask_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
) -> str:
    """
    FastAPI dependency for /ask routes. In demo anonymous mode, missing auth yields a guest id.
    Otherwise requires a valid Supabase JWT (same as get_current_user).
    """
    if is_demo_mode() and demo_anonymous_enabled():
        token = credentials.credentials if credentials else None
        if token:
            try:
                payload = verify_supabase_token(token)
                sub = payload.get("sub")
                if sub:
                    return sub
            except jwt.InvalidTokenError:
                pass
        return DEMO_GUEST_USER_ID
    return get_current_user(request, credentials)
