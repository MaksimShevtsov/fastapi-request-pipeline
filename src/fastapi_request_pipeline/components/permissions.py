"""Permission components — Authenticated, HasPermission, HasRole."""

from __future__ import annotations

from typing import Any

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.exceptions import PermissionDenied


class Authenticated(FlowComponent):
    """Asserts ctx.user is not None."""

    category = ComponentCategory.PERMISSION

    async def resolve(self, ctx: RequestContext) -> None:
        if ctx.user is None:
            raise PermissionDenied()


def _get_collection(user: object, attr: str) -> list[str] | None:
    """Extract a collection from user by dict key or attribute."""
    if isinstance(user, dict):
        val: list[str] | None = user.get(attr)
        return val
    return getattr(user, attr, None)


class HasPermission(FlowComponent):
    """Checks ctx.user has the specified permission."""

    category = ComponentCategory.PERMISSION

    def __init__(self, permission: str) -> None:
        self._permission = permission

    async def resolve(self, ctx: RequestContext) -> None:
        permissions = _get_collection(ctx.user, "permissions")
        if permissions is None or self._permission not in permissions:
            raise PermissionDenied()

    def openapi_spec(self) -> dict[str, Any] | None:
        return {
            "responses": {"403": {"description": "Permission denied"}},
            "x-permissions": [self._permission],
        }


class HasRole(FlowComponent):
    """Checks ctx.user has the specified role."""

    category = ComponentCategory.PERMISSION

    def __init__(self, role: str) -> None:
        self._role = role

    async def resolve(self, ctx: RequestContext) -> None:
        roles = _get_collection(ctx.user, "roles")
        if roles is None or self._role not in roles:
            raise PermissionDenied()

    def openapi_spec(self) -> dict[str, Any] | None:
        return {
            "responses": {"403": {"description": "Permission denied"}},
            "x-roles": [self._role],
        }
