"""Integration tests for flow_dependency with FastAPI TestClient."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent
from fastapi_request_pipeline.components.authentication import JWTAuthentication
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.dependency import flow_dependency
from fastapi_request_pipeline.flow import Flow


class _OrderTracker(FlowComponent):
    category = ComponentCategory.CUSTOM

    def __init__(self, name: str) -> None:
        self._name = name

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.state.setdefault("order", []).append(self._name)


class _PermStub(FlowComponent):
    category = ComponentCategory.PERMISSION

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.state.setdefault("order", []).append("perm")


def _make_app(flow: Flow) -> FastAPI:
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(
        ctx: RequestContext = Depends(flow_dependency(flow)),  # noqa: B008
    ) -> dict[str, Any]:
        return {"user": ctx.user, "state": ctx.state}

    return app


async def _get(app: FastAPI, path: str = "/test", **kwargs: Any) -> Any:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, **kwargs)


class TestFlowDependencyIntegration:
    async def test_valid_request_returns_populated_ctx(self) -> None:
        decode = AsyncMock(return_value={"sub": "user-1"})
        flow = Flow(JWTAuthentication(decode=decode))
        app = _make_app(flow)
        resp = await _get(app, headers={"Authorization": "Bearer valid"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"] == {"sub": "user-1"}

    async def test_invalid_credentials_return_401(self) -> None:
        decode = AsyncMock(side_effect=Exception("bad"))
        flow = Flow(JWTAuthentication(decode=decode))
        app = _make_app(flow)
        resp = await _get(app, headers={"Authorization": "Bearer bad"})
        assert resp.status_code == 401

    async def test_missing_credentials_return_401(self) -> None:
        flow = Flow(JWTAuthentication(decode=AsyncMock()))
        app = _make_app(flow)
        resp = await _get(app)
        assert resp.status_code == 401

    async def test_multiple_components_execute_in_category_order(self) -> None:
        class AuthTracker(FlowComponent):
            category = ComponentCategory.AUTHENTICATION

            async def resolve(self, ctx: RequestContext) -> None:
                ctx.user = {"sub": "user-1"}
                ctx.state.setdefault("order", []).append("auth")

        flow = Flow(
            _OrderTracker("custom"),
            _PermStub(),
            AuthTracker(),
        )
        app = _make_app(flow)
        resp = await _get(app)
        assert resp.status_code == 200
        assert resp.json()["state"]["order"] == ["auth", "perm", "custom"]

    async def test_flow_coexists_with_other_depends(self) -> None:
        decode = AsyncMock(return_value={"sub": "user-1"})
        flow = Flow(JWTAuthentication(decode=decode))
        app = FastAPI()

        async def other_dep() -> str:
            return "other"

        @app.get("/test")
        async def endpoint(
            ctx: RequestContext = Depends(flow_dependency(flow)),  # noqa: B008
            other: str = Depends(other_dep),
        ) -> dict[str, Any]:
            return {"user": ctx.user, "other": other}

        resp = await _get(app, headers={"Authorization": "Bearer valid"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"] == {"sub": "user-1"}
        assert data["other"] == "other"

    async def test_unexpected_exception_returns_500(self) -> None:
        class Broken(FlowComponent):
            category = ComponentCategory.CUSTOM

            async def resolve(self, ctx: RequestContext) -> None:
                raise RuntimeError("unexpected")

        flow = Flow(Broken())
        app = _make_app(flow)
        resp = await _get(app)
        assert resp.status_code == 500

    async def test_empty_flow_returns_ctx(self) -> None:
        flow = Flow()
        app = _make_app(flow)
        resp = await _get(app)
        assert resp.status_code == 200
        assert resp.json()["user"] is None
