"""
Unit tests for auth dependencies.

JWT verification logic is tested with mocked PyJWKClient so we don't
need real Clerk credentials.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from starlette.requests import Request


class TestGetOptionalUserId:
    """Tests for get_optional_user_id dependency."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_auth_header(self):
        from app.auth.dependencies import get_optional_user_id

        scope = {"type": "http", "headers": []}
        request = Request(scope)
        result = await get_optional_user_id(request)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_wrong_scheme(self):
        from app.auth.dependencies import get_optional_user_id

        scope = {
            "type": "http",
            "headers": [(b"authorization", b"Basic abc123")],
        }
        request = Request(scope)
        result = await get_optional_user_id(request)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_clerk_not_configured(self):
        """When CLERK_JWKS_URL is empty, _get_jwks_client returns None → no user."""
        from app.auth import dependencies

        scope = {
            "type": "http",
            "headers": [(b"authorization", b"Bearer fake.jwt.token")],
        }
        request = Request(scope)

        # Ensure the cache is cleared and jwks_url is empty
        dependencies._get_jwks_client.cache_clear()
        with patch.object(dependencies.settings, "clerk_jwks_url", ""):
            result = await dependencies.get_optional_user_id(request)
        dependencies._get_jwks_client.cache_clear()

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_user_id_from_valid_token(self):
        """With a mock JWKS client, a well-formed token returns the sub claim."""
        from app.auth import dependencies

        mock_signing_key = MagicMock()
        mock_signing_key.key = "fake-public-key"

        mock_jwks_client = MagicMock()
        mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

        scope = {
            "type": "http",
            "headers": [(b"authorization", b"Bearer valid.jwt.token")],
        }
        request = Request(scope)

        dependencies._get_jwks_client.cache_clear()
        with (
            patch.object(dependencies.settings, "clerk_jwks_url", "https://example.clerk.accounts.dev/.well-known/jwks.json"),
            patch("app.auth.dependencies.PyJWKClient", return_value=mock_jwks_client),
            patch(
                "app.auth.dependencies.jwt.decode",
                return_value={"sub": "user_abc123", "exp": 9999999999},
            ),
        ):
            result = await dependencies.get_optional_user_id(request)
        dependencies._get_jwks_client.cache_clear()

        assert result == "user_abc123"


class TestRequireUserId:
    """Tests for require_user_id dependency (raises 401 when unauthenticated)."""

    @pytest.mark.asyncio
    async def test_raises_401_when_no_token(self):
        from fastapi import HTTPException
        from app.auth.dependencies import require_user_id

        scope = {"type": "http", "headers": []}
        request = Request(scope)

        with pytest.raises(HTTPException) as exc_info:
            await require_user_id(request)

        assert exc_info.value.status_code == 401
