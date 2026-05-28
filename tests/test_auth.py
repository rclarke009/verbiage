"""Supabase JWT verification (HS256 legacy + ES256 JWKS)."""

from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.auth import _reset_jwks_client_for_tests, verify_supabase_token


def test_verify_hs256_token():
    secret = "test-jwt-secret"
    token = pyjwt.encode(
        {"sub": "user-hs256", "aud": "authenticated"},
        secret,
        algorithm="HS256",
    )
    with patch("app.auth.SUPABASE_JWT_SECRET", secret):
        payload = verify_supabase_token(token)
    assert payload["sub"] == "user-hs256"


def test_verify_es256_token_via_jwks():
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    token = pyjwt.encode(
        {"sub": "user-es256", "aud": "authenticated"},
        private_key,
        algorithm="ES256",
        headers={"kid": "test-kid"},
    )

    mock_client = MagicMock()
    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

    _reset_jwks_client_for_tests()
    with patch("app.auth.SUPABASE_URL", "https://test.supabase.co"):
        with patch("app.auth._get_jwks_client", return_value=mock_client):
            payload = verify_supabase_token(token)
    assert payload["sub"] == "user-es256"


def test_verify_es256_without_supabase_url():
    private_key = ec.generate_private_key(ec.SECP256R1())
    token = pyjwt.encode(
        {"sub": "user-es256", "aud": "authenticated"},
        private_key,
        algorithm="ES256",
    )
    with patch("app.auth.SUPABASE_URL", ""):
        with patch("app.auth.SUPABASE_JWT_SECRET", ""):
            _reset_jwks_client_for_tests()
            with pytest.raises(pyjwt.InvalidTokenError, match="JWKS"):
                verify_supabase_token(token)
