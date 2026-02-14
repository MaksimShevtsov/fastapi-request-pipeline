"""Integration tests for multi-level flow composition."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent
from fastapi_request_pipeline.components.authentication import (
    CookieAuthentication,
    JWTAuthentication,
)
from fastapi_request_pipeline.composition import DisableFlow, OverrideFlow, merge_flows
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.dependency import flow_dependency
from fastapi_request_pipeline.flow import Flow


class _ThrottleStub(FlowComponent):
    category = ComponentCategory.THROTTLING

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.state["throttled"] = True


async def _get(app: FastAPI, path: str = "/test", **kwargs: Any) -> Any:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, **kwargs)


class TestFlowCompositionIntegration:
    async def test_app_router_route_merge(self) -> None:
        decode = AsyncMock(return_value={"sub": "jwt-user"})
        lookup = AsyncMock(return_value={"sub": "cookie-user"})

        app_flow = Flow(JWTAuthentication(decode=decode), _ThrottleStub())
        router_flow = Flow(OverrideFlow(CookieAuthentication(lookup=lookup)))
        route_flow = Flow(DisableFlow(ComponentCategory.THROTTLING))

        merged = merge_flows(app_flow, router_flow, route_flow)
        app = FastAPI()

        @app.get("/test")
        async def endpoint(
            ctx: RequestContext = Depends(flow_dependency(merged)),  # noqa: B008
        ) -> dict[str, Any]:
            return {"user": ctx.user, "state": ctx.state}

        resp = await _get(app, headers={"cookie": "session=abc123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"] == {"sub": "cookie-user"}
        assert "throttled" not in data["state"]

    async def test_composition_is_deterministic(self) -> None:
        decode = AsyncMock(return_value={"sub": "user"})
        app_flow = Flow(JWTAuthentication(decode=decode))
        router_flow = Flow(_ThrottleStub())

        m1 = merge_flows(app_flow, router_flow)
        m2 = merge_flows(app_flow, router_flow)
        r1 = m1.resolve()
        r2 = m2.resolve()
        assert len(r1.components) == len(r2.components)
        for c1, c2 in zip(r1.components, r2.components, strict=True):
            assert type(c1) is type(c2)
            assert c1.category == c2.category

    async def test_effective_flow_inspection(self) -> None:
        decode = AsyncMock(return_value={"sub": "user"})
        app_flow = Flow(JWTAuthentication(decode=decode), _ThrottleStub())
        route_flow = Flow(DisableFlow(ComponentCategory.THROTTLING))
        merged = merge_flows(app_flow, route_flow)
        resolved = merged.resolve()
        categories = [c.category for c in resolved.components]
        assert ComponentCategory.AUTHENTICATION in categories
        assert ComponentCategory.THROTTLING not in categories

    async def test_merge_result_works_with_flow_dependency(self) -> None:
        decode = AsyncMock(return_value={"sub": "user"})
        merged = merge_flows(
            Flow(JWTAuthentication(decode=decode)),
            Flow(_ThrottleStub()),
        )
        app = FastAPI()

        @app.get("/test")
        async def endpoint(
            ctx: RequestContext = Depends(flow_dependency(merged)),  # noqa: B008
        ) -> dict[str, Any]:
            return {"user": ctx.user, "throttled": ctx.state.get("throttled")}

        resp = await _get(app, headers={"Authorization": "Bearer token"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"] == {"sub": "user"}
        assert data["throttled"] is True
