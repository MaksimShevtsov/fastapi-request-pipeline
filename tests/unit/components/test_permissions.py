"""Tests for permission components."""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from fastapi_request_pipeline.component import ComponentCategory
from fastapi_request_pipeline.components.permissions import (
    Authenticated,
    HasPermission,
    HasRole,
)
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.exceptions import PermissionDenied


class TestAuthenticated:
    def test_category_is_permission(self) -> None:
        assert Authenticated().category == ComponentCategory.PERMISSION

    async def test_passes_when_user_set(self, make_request: Any) -> None:
        ctx = RequestContext(request=make_request(), user={"id": "user-1"})
        await Authenticated().resolve(ctx)

    async def test_raises_when_user_is_none(self, make_request: Any) -> None:
        ctx = RequestContext(request=make_request())
        with pytest.raises(PermissionDenied):
            await Authenticated().resolve(ctx)


class TestHasPermission:
    def test_category_is_permission(self) -> None:
        assert HasPermission("read").category == ComponentCategory.PERMISSION

    async def test_passes_when_permission_present_dict(
        self, make_request: Any, sample_user: dict[str, Any]
    ) -> None:
        ctx = RequestContext(request=make_request(), user=sample_user)
        await HasPermission("tickets.read").resolve(ctx)

    async def test_raises_when_permission_missing_dict(
        self, make_request: Any, sample_user: dict[str, Any]
    ) -> None:
        ctx = RequestContext(request=make_request(), user=sample_user)
        with pytest.raises(PermissionDenied):
            await HasPermission("admin.nuke").resolve(ctx)

    async def test_passes_when_permission_present_attr(self, make_request: Any) -> None:
        class User:
            permissions: ClassVar[list[str]] = ["read", "write"]

        ctx = RequestContext(request=make_request(), user=User())
        await HasPermission("read").resolve(ctx)

    async def test_raises_when_permission_missing_attr(self, make_request: Any) -> None:
        class User:
            permissions: ClassVar[list[str]] = ["read"]

        ctx = RequestContext(request=make_request(), user=User())
        with pytest.raises(PermissionDenied):
            await HasPermission("delete").resolve(ctx)

    async def test_raises_when_no_permissions_attr(self, make_request: Any) -> None:
        ctx = RequestContext(request=make_request(), user={"name": "user"})
        with pytest.raises(PermissionDenied):
            await HasPermission("read").resolve(ctx)


class TestHasRole:
    def test_category_is_permission(self) -> None:
        assert HasRole("admin").category == ComponentCategory.PERMISSION

    async def test_passes_when_role_present_dict(
        self, make_request: Any, sample_user: dict[str, Any]
    ) -> None:
        ctx = RequestContext(request=make_request(), user=sample_user)
        await HasRole("admin").resolve(ctx)

    async def test_raises_when_role_missing_dict(
        self, make_request: Any, sample_user: dict[str, Any]
    ) -> None:
        ctx = RequestContext(request=make_request(), user=sample_user)
        with pytest.raises(PermissionDenied):
            await HasRole("superadmin").resolve(ctx)

    async def test_passes_when_role_present_attr(self, make_request: Any) -> None:
        class User:
            roles: ClassVar[list[str]] = ["admin", "moderator"]

        ctx = RequestContext(request=make_request(), user=User())
        await HasRole("moderator").resolve(ctx)

    async def test_raises_when_role_missing_attr(self, make_request: Any) -> None:
        class User:
            roles: ClassVar[list[str]] = ["user"]

        ctx = RequestContext(request=make_request(), user=User())
        with pytest.raises(PermissionDenied):
            await HasRole("admin").resolve(ctx)
