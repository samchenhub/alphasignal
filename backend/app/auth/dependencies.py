"""
Clerk JWT verification for FastAPI.

Uses PyJWT + Clerk's JWKS endpoint to verify tokens server-side.
When CLERK_JWKS_URL is not set, auth is disabled and all endpoints
behave as if the user is anonymous (no 401s on optional routes).
"""
import logging
from functools import lru_cache

import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_jwks_client() -> "PyJWKClient | None":
    """Cached JWKS client — fetches Clerk's public keys once on first call."""
    if not settings.clerk_jwks_url:
        return None
    return PyJWKClient(settings.clerk_jwks_url, cache_keys=True)


def _verify_token(token: str) -> dict | None:
    """Verify a Clerk JWT and return its payload, or None on failure."""
    client = _get_jwks_client()
    if client is None:
        return None
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_exp": True},
        )
        return payload
    except Exception as exc:
        logger.debug("JWT verification failed: %s", exc)
        return None


async def get_optional_user_id(request: Request) -> str | None:
    """
    FastAPI dependency: extracts Clerk user ID from Bearer token.
    Returns None (not 401) when unauthenticated — callers decide
    whether to require auth.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    payload = _verify_token(auth[7:])
    return payload.get("sub") if payload else None


async def require_user_id(request: Request) -> str:
    """
    FastAPI dependency: like get_optional_user_id but raises 401
    when the user is not authenticated.
    """
    user_id = await get_optional_user_id(request)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id
