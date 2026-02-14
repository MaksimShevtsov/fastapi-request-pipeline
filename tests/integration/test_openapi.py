"""Integration tests for OpenAPI enrichment."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from fastapi_request_pipeline.components.authentication import JWTAuthentication
from fastapi_request_pipeline.components.pagination import LimitOffset
from fastapi_request_pipeline.components.permissions import HasPermission, HasRole
from fastapi_request_pipeline.components.throttling import RateLimit
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.dependency import enrich_openapi, flow_dependency
from fastapi_request_pipeline.flow import Flow


async def _get_schema(app: FastAPI) -> dict[str, Any]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/openapi.json")
        return resp.json()


def _make_app_with_flow(flow: Flow) -> FastAPI:
    app = FastAPI()

    @app.get("/test")
    async def endpoint(
        ctx: RequestContext = Depends(flow_dependency(flow)),  # noqa: B008
    ) -> dict[str, Any]:
        return {"ok": True}

    enrich_openapi(app)
    return app


class TestOpenAPIEnrichment:
    async def test_jwt_adds_bearer_security_scheme(self) -> None:
        decode = AsyncMock(return_value={"sub": "user"})
        flow = Flow(JWTAuthentication(decode=decode))
        app = _make_app_with_flow(flow)
        schema = await _get_schema(app)
        path = schema["paths"]["/test"]["get"]
        assert "security" in path
        assert {"Bearer": []} in path["security"]
        assert "Bearer" in schema.get("components", {}).get("securitySchemes", {})

    async def test_has_permission_adds_403_response(self) -> None:
        decode = AsyncMock(return_value={"sub": "user"})
        flow = Flow(JWTAuthentication(decode=decode), HasPermission("read"))
        app = _make_app_with_flow(flow)
        schema = await _get_schema(app)
        path = schema["paths"]["/test"]["get"]
        assert "403" in path.get("responses", {})

    async def test_has_permission_adds_x_permissions(self) -> None:
        decode = AsyncMock(return_value={"sub": "user"})
        flow = Flow(JWTAuthentication(decode=decode), HasPermission("tickets.read"))
        app = _make_app_with_flow(flow)
        schema = await _get_schema(app)
        path = schema["paths"]["/test"]["get"]
        assert "x-permissions" in path
        assert "tickets.read" in path["x-permissions"]

    async def test_rate_limit_adds_429_response(self) -> None:
        flow = Flow(RateLimit(rate=10, window_seconds=60))
        app = _make_app_with_flow(flow)
        schema = await _get_schema(app)
        path = schema["paths"]["/test"]["get"]
        assert "429" in path.get("responses", {})

    async def test_limit_offset_adds_query_parameters(self) -> None:
        flow = Flow(LimitOffset())
        app = _make_app_with_flow(flow)
        schema = await _get_schema(app)
        path = schema["paths"]["/test"]["get"]
        params = path.get("parameters", [])
        param_names = [p["name"] for p in params]
        assert "limit" in param_names
        assert "offset" in param_names

    async def test_multiple_components_merge(self) -> None:
        decode = AsyncMock(return_value={"sub": "user"})
        flow = Flow(
            JWTAuthentication(decode=decode),
            HasPermission("read"),
            RateLimit(rate=10),
            LimitOffset(),
        )
        app = _make_app_with_flow(flow)
        schema = await _get_schema(app)
        path = schema["paths"]["/test"]["get"]
        assert "security" in path
        assert "403" in path.get("responses", {})
        assert "429" in path.get("responses", {})

    async def test_flow_with_no_openapi_components(self) -> None:
        from fastapi_request_pipeline.component import ComponentCategory, FlowComponent

        class NoOp(FlowComponent):
            category = ComponentCategory.CUSTOM

            async def resolve(self, ctx: RequestContext) -> None:
                pass

        flow = Flow(NoOp())
        app = _make_app_with_flow(flow)
        schema = await _get_schema(app)
        path = schema["paths"]["/test"]["get"]
        assert "security" not in path
        assert "x-permissions" not in path

    async def test_has_role_adds_x_roles(self) -> None:
        decode = AsyncMock(return_value={"sub": "user"})
        flow = Flow(JWTAuthentication(decode=decode), HasRole("admin"))
        app = _make_app_with_flow(flow)
        schema = await _get_schema(app)
        path = schema["paths"]["/test"]["get"]
        assert "x-roles" in path
        assert "admin" in path["x-roles"]
