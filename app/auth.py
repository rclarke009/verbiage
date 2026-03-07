"""
Supabase Auth: verify JWT from Authorization header and expose current user to routes.
Uses SUPABASE_JWT_SECRET to validate access tokens issued by Supabase.
"""

import logging
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import SUPABASE_JWT_SECRET

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


def verify_supabase_token(token: str) -> dict:
    """
    Decode and verify a Supabase access token (JWT). Returns payload dict with at least 'sub' (user id).
    Raises jwt.InvalidTokenError if invalid or expired.
    """
    return jwt.decode(
        token,
        SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        audience="authenticated",
        options={"verify_aud": True},
    )


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
) -> str:
    """
    FastAPI dependency: require valid Supabase JWT and return the user id (sub).
    Returns 401 if missing or invalid.
    """
    if not SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase Auth not configured (SUPABASE_JWT_SECRET)",
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
        logger.debug("Invalid JWT: %s", e)
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
