"""Quickstart scenario validation — tests all 7 scenarios from quickstart.md."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from fastapi_request_pipeline import (
    AfterComponent,
    AllowAnonymous,
    Authenticated,
    ComponentCategory,
    CookieAuthentication,
    DisableFlow,
    FeatureEnabled,
    Flow,
    FlowAbort,
    FlowComponent,
    HasPermission,
    HasRole,
    JWTAuthentication,
    LimitOffset,
    OverrideFlow,
    QueryFilter,
    RateLimit,
    RequestContext,
    flow_dependency,
    merge_flows,
)


async def _request(
    app: FastAPI,
    method: str = "GET",
    path: str = "/test",
    **kwargs: Any,
) -> Any:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await getattr(client, method.lower())(path, **kwargs)


# -- Scenario 1: Basic Flow with Authentication --


class TestScenario1BasicAuth:
    async def test_valid_bearer_returns_user(self) -> None:
        decode = AsyncMock(return_value={"sub": "user-1"})
        app = FastAPI()
        auth_flow = Flow(JWTAuthentication(decode=decode))

        @app.get("/me")
        async def get_me(
            ctx: RequestContext = Depends(flow_dependency(auth_flow)),  # noqa: B008
        ) -> dict[str, Any]:
            return {"user": ctx.user}

        resp = await _request(
            app, path="/me", headers={"Authorization": "Bearer valid"}
        )
        assert resp.status_code == 200
        assert resp.json()["user"] == {"sub": "user-1"}

    async def test_missing_token_returns_401(self) -> None:
        decode = AsyncMock()
        app = FastAPI()
        auth_flow = Flow(JWTAuthentication(decode=decode))

        @app.get("/me")
        async def get_me(
            ctx: RequestContext = Depends(flow_dependency(auth_flow)),  # noqa: B008
        ) -> dict[str, Any]:
            return {"user": ctx.user}

        resp = await _request(app, path="/me")
        assert resp.status_code == 401

    async def test_invalid_token_returns_401(self) -> None:
        decode = AsyncMock(side_effect=Exception("bad token"))
        app = FastAPI()
        auth_flow = Flow(JWTAuthentication(decode=decode))

        @app.get("/me")
        async def get_me(
            ctx: RequestContext = Depends(flow_dependency(auth_flow)),  # noqa: B008
        ) -> dict[str, Any]:
            return {"user": ctx.user}

        resp = await _request(app, path="/me", headers={"Authorization": "Bearer bad"})
        assert resp.status_code == 401


# -- Scenario 2: Flow Composition with Override --


class TestScenario2Composition:
    async def test_override_replaces_auth_and_disable_removes_throttling(
        self,
    ) -> None:
        decode = AsyncMock(return_value={"sub": "jwt-user"})
        lookup = AsyncMock(return_value={"sub": "cookie-user"})

        app_flow = Flow(
            JWTAuthentication(decode=decode),
            RateLimit(rate=100, window_seconds=60),
        )
        router_flow = Flow(OverrideFlow(CookieAuthentication(lookup=lookup)))
        route_flow = Flow(DisableFlow(ComponentCategory.THROTTLING))

        merged = merge_flows(app_flow, router_flow, route_flow)
        resolved = merged.resolve()

        # Verify composition result
        categories = [c.category for c in resolved.components]
        assert ComponentCategory.AUTHENTICATION in categories
        assert ComponentCategory.THROTTLING not in categories

        # Verify the auth component is CookieAuthentication
        auth_comp = next(
            c
            for c in resolved.components
            if c.category == ComponentCategory.AUTHENTICATION
        )
        assert isinstance(auth_comp, CookieAuthentication)

    async def test_merge_resolves_at_startup_not_per_request(self) -> None:
        decode = AsyncMock(return_value={"sub": "user"})
        merged = merge_flows(
            Flow(JWTAuthentication(decode=decode)),
            Flow(AllowAnonymous()),
        )
        r1 = merged.resolve()
        r2 = merged.resolve()
        # Same cached object
        assert r1 is r2


# -- Scenario 3: Permission and Feature Policies --


class TestScenario3Permissions:
    async def test_unauthenticated_returns_401(self) -> None:
        decode = AsyncMock(side_effect=Exception("no auth"))
        flow = Flow(
            JWTAuthentication(decode=decode),
            Authenticated(),
            HasRole("admin"),
        )
        app = FastAPI()

        @app.delete("/users/{user_id}")
        async def delete_user(
            user_id: int,
            ctx: RequestContext = Depends(flow_dependency(flow)),  # noqa: B008
        ) -> dict[str, Any]:
            return {"deleted": user_id}

        resp = await _request(
            app,
            method="DELETE",
            path="/users/1",
            headers={"Authorization": "Bearer bad"},
        )
        assert resp.status_code == 401

    async def test_wrong_role_returns_403(self) -> None:
        decode = AsyncMock(return_value={"sub": "user", "roles": ["viewer"]})
        flow = Flow(
            JWTAuthentication(decode=decode),
            Authenticated(),
            HasRole("admin"),
        )
        app = FastAPI()

        @app.delete("/users/{user_id}")
        async def delete_user(
            user_id: int,
            ctx: RequestContext = Depends(flow_dependency(flow)),  # noqa: B008
        ) -> dict[str, Any]:
            return {"deleted": user_id}

        resp = await _request(
            app,
            method="DELETE",
            path="/users/1",
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 403

    async def test_missing_permission_returns_403(self) -> None:
        decode = AsyncMock(
            return_value={
                "sub": "admin",
                "roles": ["admin"],
                "permissions": ["users.read"],
            }
        )
        flow = Flow(
            JWTAuthentication(decode=decode),
            Authenticated(),
            HasRole("admin"),
            HasPermission("users.delete"),
        )
        app = FastAPI()

        @app.delete("/users/{user_id}")
        async def delete_user(
            user_id: int,
            ctx: RequestContext = Depends(flow_dependency(flow)),  # noqa: B008
        ) -> dict[str, Any]:
            return {"deleted": user_id}

        resp = await _request(
            app,
            method="DELETE",
            path="/users/1",
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 403

    async def test_feature_disabled_returns_403(self) -> None:
        decode = AsyncMock(
            return_value={
                "sub": "admin",
                "roles": ["admin"],
                "permissions": ["users.delete"],
            }
        )
        checker = AsyncMock(return_value=False)
        flow = Flow(
            JWTAuthentication(decode=decode),
            Authenticated(),
            HasRole("admin"),
            HasPermission("users.delete"),
            FeatureEnabled("admin_panel", checker=checker),
        )
        app = FastAPI()

        @app.delete("/users/{user_id}")
        async def delete_user(
            user_id: int,
            ctx: RequestContext = Depends(flow_dependency(flow)),  # noqa: B008
        ) -> dict[str, Any]:
            return {"deleted": user_id}

        resp = await _request(
            app,
            method="DELETE",
            path="/users/1",
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 403

    async def test_all_checks_pass(self) -> None:
        decode = AsyncMock(
            return_value={
                "sub": "admin",
                "roles": ["admin"],
                "permissions": ["users.delete"],
            }
        )
        checker = AsyncMock(return_value=True)
        flow = Flow(
            JWTAuthentication(decode=decode),
            Authenticated(),
            HasRole("admin"),
            HasPermission("users.delete"),
            FeatureEnabled("admin_panel", checker=checker),
        )
        app = FastAPI()

        @app.delete("/users/{user_id}")
        async def delete_user(
            user_id: int,
            ctx: RequestContext = Depends(flow_dependency(flow)),  # noqa: B008
        ) -> dict[str, Any]:
            return {"deleted": user_id, "by": ctx.user}

        resp = await _request(
            app,
            method="DELETE",
            path="/users/1",
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == 1
        assert data["by"]["sub"] == "admin"


# -- Scenario 4: Filtering and Pagination --


class TestScenario4FilterPagination:
    async def test_query_params_parsed(self) -> None:
        decode = AsyncMock(return_value={"sub": "user"})
        flow = Flow(
            JWTAuthentication(decode=decode),
            QueryFilter("status", "priority"),
            LimitOffset(max_limit=100, default_limit=20),
        )
        app = FastAPI()

        @app.get("/tickets")
        async def list_tickets(
            ctx: RequestContext = Depends(flow_dependency(flow)),  # noqa: B008
        ) -> dict[str, Any]:
            return {
                "filters": ctx.state["filters"],
                "pagination": ctx.state["pagination"],
            }

        resp = await _request(
            app,
            path="/tickets?status=open&priority=high&limit=50&offset=10",
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["filters"] == {"status": "open", "priority": "high"}
        assert data["pagination"] == {"limit": 50, "offset": 10}

    async def test_default_pagination(self) -> None:
        decode = AsyncMock(return_value={"sub": "user"})
        flow = Flow(
            JWTAuthentication(decode=decode),
            QueryFilter("status"),
            LimitOffset(max_limit=100, default_limit=20),
        )
        app = FastAPI()

        @app.get("/tickets")
        async def list_tickets(
            ctx: RequestContext = Depends(flow_dependency(flow)),  # noqa: B008
        ) -> dict[str, Any]:
            return {
                "filters": ctx.state["filters"],
                "pagination": ctx.state["pagination"],
            }

        resp = await _request(
            app,
            path="/tickets",
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["filters"] == {}
        assert data["pagination"] == {"limit": 20, "offset": 0}

    async def test_negative_limit_returns_error(self) -> None:
        decode = AsyncMock(return_value={"sub": "user"})
        flow = Flow(
            JWTAuthentication(decode=decode),
            LimitOffset(),
        )
        app = FastAPI()

        @app.get("/tickets")
        async def list_tickets(
            ctx: RequestContext = Depends(flow_dependency(flow)),  # noqa: B008
        ) -> dict[str, Any]:
            return {"pagination": ctx.state["pagination"]}

        resp = await _request(
            app,
            path="/tickets?limit=-1",
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 400


# -- Scenario 5: Rate Limiting --


class TestScenario5RateLimit:
    async def test_rate_limit_enforced(self) -> None:
        decode = AsyncMock(return_value={"sub": "user-1"})
        flow = Flow(
            JWTAuthentication(decode=decode),
            RateLimit(rate=3, window_seconds=60),
        )
        app = FastAPI()

        @app.post("/actions")
        async def create_action(
            ctx: RequestContext = Depends(flow_dependency(flow)),  # noqa: B008
        ) -> dict[str, Any]:
            return {"ok": True}

        # First 3 requests pass
        for _ in range(3):
            resp = await _request(
                app,
                method="POST",
                path="/actions",
                headers={"Authorization": "Bearer token"},
            )
            assert resp.status_code == 200

        # 4th request throttled
        resp = await _request(
            app,
            method="POST",
            path="/actions",
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 429


# -- Scenario 6: Debug Tracing --


class TestScenario6DebugTrace:
    async def test_debug_trace_present(self) -> None:
        decode = AsyncMock(
            return_value={
                "sub": "user",
                "permissions": ["read"],
            }
        )
        flow = Flow(
            JWTAuthentication(decode=decode),
            Authenticated(),
            HasPermission("read"),
            debug=True,
        )
        app = FastAPI()

        @app.get("/debug-example")
        async def debug_example(
            ctx: RequestContext = Depends(flow_dependency(flow)),  # noqa: B008
        ) -> dict[str, Any]:
            trace = ctx.state.get("trace")
            return {
                "user": ctx.user,
                "trace_count": len(trace.entries) if trace else 0,
                "trace_outcome": trace.outcome if trace else None,
            }

        resp = await _request(
            app,
            path="/debug-example",
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["trace_count"] == 3  # JWT + Authenticated + HasPermission
        assert data["trace_outcome"] == "OK"

    async def test_no_trace_when_debug_false(self) -> None:
        decode = AsyncMock(return_value={"sub": "user"})
        flow = Flow(
            JWTAuthentication(decode=decode),
            debug=False,
        )
        app = FastAPI()

        @app.get("/no-debug")
        async def no_debug(
            ctx: RequestContext = Depends(flow_dependency(flow)),  # noqa: B008
        ) -> dict[str, Any]:
            return {"has_trace": "trace" in ctx.state}

        resp = await _request(
            app,
            path="/no-debug",
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 200
        assert resp.json()["has_trace"] is False


# -- Scenario 7: Custom Components and Hooks --


class TestScenario7CustomHooks:
    async def test_custom_component_in_flow(self) -> None:
        decode = AsyncMock(return_value={"sub": "user"})

        class TenantResolver(FlowComponent):
            category = ComponentCategory.CUSTOM

            async def resolve(self, ctx: RequestContext) -> None:
                tenant_id = ctx.request.headers.get("x-tenant-id")
                if not tenant_id:
                    raise FlowAbort("Missing X-Tenant-ID header", status_code=400)
                ctx.state["tenant_id"] = tenant_id

        flow = Flow(
            JWTAuthentication(decode=decode),
            TenantResolver(),
        )
        app = FastAPI()

        @app.get("/tenant-data")
        async def get_tenant_data(
            ctx: RequestContext = Depends(flow_dependency(flow)),  # noqa: B008
        ) -> dict[str, Any]:
            return {
                "tenant": ctx.state["tenant_id"],
                "user": ctx.user,
            }

        # With tenant header
        resp = await _request(
            app,
            path="/tenant-data",
            headers={
                "Authorization": "Bearer token",
                "X-Tenant-ID": "acme",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant"] == "acme"
        assert data["user"]["sub"] == "user"

        # Missing tenant header
        resp = await _request(
            app,
            path="/tenant-data",
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 400

    async def test_after_component_hook_fires(self) -> None:
        decode = AsyncMock(return_value={"sub": "user"})
        hook_calls: list[str] = []

        async def log_component(
            ctx: RequestContext,
            component: FlowComponent,
            error: Any,
        ) -> None:
            outcome = "OK" if error is None else f"FAILED: {error}"
            hook_calls.append(f"{component.__class__.__name__}: {outcome}")

        flow = Flow(
            JWTAuthentication(decode=decode),
        ).add_hook(AfterComponent(log_component))

        app = FastAPI()

        @app.get("/hooked")
        async def hooked(
            ctx: RequestContext = Depends(flow_dependency(flow)),  # noqa: B008
        ) -> dict[str, Any]:
            return {"ok": True}

        resp = await _request(
            app,
            path="/hooked",
            headers={"Authorization": "Bearer token"},
        )
        assert resp.status_code == 200
        assert len(hook_calls) == 1
        assert "JWTAuthentication: OK" in hook_calls[0]
