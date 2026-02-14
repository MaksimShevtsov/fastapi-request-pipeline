"""Authentication components — JWT, Cookie, API Key."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.exceptions import AuthenticationFailed


class JWTAuthentication(FlowComponent):
    """Extracts Bearer token from Authorization header and decodes via callback."""

    category = ComponentCategory.AUTHENTICATION

    def __init__(
        self,
        decode: Callable[[str], Awaitable[Any]],
        *,
        scheme: str = "Bearer",
        header: str = "Authorization",
    ) -> None:
        self._decode = decode
        self._scheme = scheme
        self._header = header

    async def resolve(self, ctx: RequestContext) -> None:
        auth_value = ctx.request.headers.get(self._header)
        if not auth_value:
            raise AuthenticationFailed()

        parts = auth_value.split(" ", 1)
        if len(parts) != 2 or parts[0] != self._scheme:
            raise AuthenticationFailed()

        token = parts[1]
        try:
            ctx.user = await self._decode(token)
        except AuthenticationFailed:
            raise
        except Exception as exc:
            raise AuthenticationFailed() from exc

    def openapi_spec(self) -> dict[str, Any] | None:
        return {
            "security_schemes": {
                self._scheme: {
                    "type": "http",
                    "scheme": self._scheme.lower(),
                    "bearerFormat": "JWT",
                }
            },
            "security": [{self._scheme: []}],
            "responses": {
                "401": {"description": "Authentication failed"},
            },
        }


class CookieAuthentication(FlowComponent):
    """Extracts session cookie and looks up user via callback."""

    category = ComponentCategory.AUTHENTICATION

    def __init__(
        self,
        lookup: Callable[[str], Awaitable[Any]],
        *,
        cookie_name: str = "session",
    ) -> None:
        self._lookup = lookup
        self._cookie_name = cookie_name

    async def resolve(self, ctx: RequestContext) -> None:
        cookie_value = ctx.request.cookies.get(self._cookie_name)
        if not cookie_value:
            raise AuthenticationFailed()

        try:
            ctx.user = await self._lookup(cookie_value)
        except AuthenticationFailed:
            raise
        except Exception as exc:
            raise AuthenticationFailed() from exc

    def openapi_spec(self) -> dict[str, Any] | None:
        return {
            "security_schemes": {
                "CookieAuth": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": self._cookie_name,
                }
            },
            "security": [{"CookieAuth": []}],
            "responses": {
                "401": {"description": "Authentication failed"},
            },
        }


class APIKeyAuthentication(FlowComponent):
    """Extracts API key from header and validates via callback."""

    category = ComponentCategory.AUTHENTICATION

    def __init__(
        self,
        validate: Callable[[str], Awaitable[Any]],
        *,
        header: str = "X-API-Key",
    ) -> None:
        self._validate = validate
        self._header = header

    async def resolve(self, ctx: RequestContext) -> None:
        key = ctx.request.headers.get(self._header)
        if not key:
            raise AuthenticationFailed()

        try:
            ctx.user = await self._validate(key)
        except AuthenticationFailed:
            raise
        except Exception as exc:
            raise AuthenticationFailed() from exc

    def openapi_spec(self) -> dict[str, Any] | None:
        return {
            "security_schemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": self._header,
                }
            },
            "security": [{"ApiKeyAuth": []}],
            "responses": {
                "401": {"description": "Authentication failed"},
            },
        }


class AllowAnonymous(FlowComponent):
    """Override component that replaces authentication requirements.

    Used with OverrideFlow to allow unauthenticated access.
    """

    category = ComponentCategory.AUTHENTICATION

    async def resolve(self, ctx: RequestContext) -> None:
        pass
