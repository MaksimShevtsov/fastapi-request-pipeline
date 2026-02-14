"""Tests for authentication components."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from fastapi_request_pipeline.component import ComponentCategory
from fastapi_request_pipeline.components.authentication import (
    APIKeyAuthentication,
    CookieAuthentication,
    JWTAuthentication,
)
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.exceptions import AuthenticationFailed


class TestJWTAuthentication:
    def test_category_is_authentication(self) -> None:
        comp = JWTAuthentication(decode=AsyncMock())
        assert comp.category == ComponentCategory.AUTHENTICATION

    async def test_extracts_bearer_token(
        self, make_request: Any, mock_decode: AsyncMock
    ) -> None:
        request = make_request(headers={"Authorization": "Bearer my-token"})
        ctx = RequestContext(request=request)
        comp = JWTAuthentication(decode=mock_decode)
        await comp.resolve(ctx)
        mock_decode.assert_awaited_once_with("my-token")

    async def test_sets_ctx_user_on_success(
        self, make_request: Any, mock_decode: AsyncMock
    ) -> None:
        request = make_request(headers={"Authorization": "Bearer valid"})
        ctx = RequestContext(request=request)
        comp = JWTAuthentication(decode=mock_decode)
        await comp.resolve(ctx)
        assert ctx.user == mock_decode.return_value

    async def test_raises_on_missing_header(self, make_request: Any) -> None:
        request = make_request()
        ctx = RequestContext(request=request)
        comp = JWTAuthentication(decode=AsyncMock())
        with pytest.raises(AuthenticationFailed):
            await comp.resolve(ctx)

    async def test_raises_on_invalid_scheme(self, make_request: Any) -> None:
        request = make_request(headers={"Authorization": "Basic creds"})
        ctx = RequestContext(request=request)
        comp = JWTAuthentication(decode=AsyncMock())
        with pytest.raises(AuthenticationFailed):
            await comp.resolve(ctx)

    async def test_raises_on_decode_failure(self, make_request: Any) -> None:
        decode = AsyncMock(side_effect=Exception("bad token"))
        request = make_request(headers={"Authorization": "Bearer bad"})
        ctx = RequestContext(request=request)
        comp = JWTAuthentication(decode=decode)
        with pytest.raises(AuthenticationFailed):
            await comp.resolve(ctx)

    async def test_custom_scheme(self, make_request: Any) -> None:
        decode = AsyncMock(return_value={"user": "ok"})
        request = make_request(headers={"Authorization": "Token my-token"})
        ctx = RequestContext(request=request)
        comp = JWTAuthentication(decode=decode, scheme="Token")
        await comp.resolve(ctx)
        decode.assert_awaited_once_with("my-token")

    async def test_custom_header(self, make_request: Any) -> None:
        decode = AsyncMock(return_value={"user": "ok"})
        request = make_request(headers={"X-Auth": "Bearer my-token"})
        ctx = RequestContext(request=request)
        comp = JWTAuthentication(decode=decode, header="X-Auth")
        await comp.resolve(ctx)
        decode.assert_awaited_once_with("my-token")


class TestCookieAuthentication:
    def test_category_is_authentication(self) -> None:
        comp = CookieAuthentication(lookup=AsyncMock())
        assert comp.category == ComponentCategory.AUTHENTICATION

    async def test_extracts_cookie(
        self, make_request: Any, mock_lookup: AsyncMock
    ) -> None:
        request = make_request(headers={"cookie": "session=abc123"})
        ctx = RequestContext(request=request)
        comp = CookieAuthentication(lookup=mock_lookup)
        await comp.resolve(ctx)
        mock_lookup.assert_awaited_once_with("abc123")

    async def test_sets_ctx_user(
        self, make_request: Any, mock_lookup: AsyncMock
    ) -> None:
        request = make_request(headers={"cookie": "session=abc123"})
        ctx = RequestContext(request=request)
        comp = CookieAuthentication(lookup=mock_lookup)
        await comp.resolve(ctx)
        assert ctx.user == mock_lookup.return_value

    async def test_raises_on_missing_cookie(self, make_request: Any) -> None:
        request = make_request()
        ctx = RequestContext(request=request)
        comp = CookieAuthentication(lookup=AsyncMock())
        with pytest.raises(AuthenticationFailed):
            await comp.resolve(ctx)

    async def test_raises_on_lookup_failure(self, make_request: Any) -> None:
        lookup = AsyncMock(side_effect=Exception("session expired"))
        request = make_request(headers={"cookie": "session=expired"})
        ctx = RequestContext(request=request)
        comp = CookieAuthentication(lookup=lookup)
        with pytest.raises(AuthenticationFailed):
            await comp.resolve(ctx)

    async def test_custom_cookie_name(self, make_request: Any) -> None:
        lookup = AsyncMock(return_value={"user": "ok"})
        request = make_request(headers={"cookie": "auth_token=xyz"})
        ctx = RequestContext(request=request)
        comp = CookieAuthentication(lookup=lookup, cookie_name="auth_token")
        await comp.resolve(ctx)
        lookup.assert_awaited_once_with("xyz")


class TestAPIKeyAuthentication:
    def test_category_is_authentication(self) -> None:
        comp = APIKeyAuthentication(validate=AsyncMock())
        assert comp.category == ComponentCategory.AUTHENTICATION

    async def test_extracts_api_key(
        self, make_request: Any, mock_validate: AsyncMock
    ) -> None:
        request = make_request(headers={"X-API-Key": "key-123"})
        ctx = RequestContext(request=request)
        comp = APIKeyAuthentication(validate=mock_validate)
        await comp.resolve(ctx)
        mock_validate.assert_awaited_once_with("key-123")

    async def test_sets_ctx_user(
        self, make_request: Any, mock_validate: AsyncMock
    ) -> None:
        request = make_request(headers={"X-API-Key": "key-123"})
        ctx = RequestContext(request=request)
        comp = APIKeyAuthentication(validate=mock_validate)
        await comp.resolve(ctx)
        assert ctx.user == mock_validate.return_value

    async def test_raises_on_missing_header(self, make_request: Any) -> None:
        request = make_request()
        ctx = RequestContext(request=request)
        comp = APIKeyAuthentication(validate=AsyncMock())
        with pytest.raises(AuthenticationFailed):
            await comp.resolve(ctx)

    async def test_raises_on_validate_failure(self, make_request: Any) -> None:
        validate = AsyncMock(side_effect=Exception("invalid key"))
        request = make_request(headers={"X-API-Key": "bad-key"})
        ctx = RequestContext(request=request)
        comp = APIKeyAuthentication(validate=validate)
        with pytest.raises(AuthenticationFailed):
            await comp.resolve(ctx)

    async def test_custom_header(self, make_request: Any) -> None:
        validate = AsyncMock(return_value={"service": "ok"})
        request = make_request(headers={"X-Service-Key": "key-456"})
        ctx = RequestContext(request=request)
        comp = APIKeyAuthentication(validate=validate, header="X-Service-Key")
        await comp.resolve(ctx)
        validate.assert_awaited_once_with("key-456")
