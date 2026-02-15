"""
Custom component examples.

Demonstrates:
- Creating custom components
- Using different component categories
- Accessing and modifying RequestContext
- Integrating with external services
"""

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI

from fastapi_request_pipeline import (
    ComponentCategory,
    Flow,
    FlowComponent,
    JWTAuthentication,
    RequestContext,
    enrich_openapi,
    flow_dependency,
)

app = FastAPI(title="Custom Components Examples")


# ========== Custom Audit Logging Component ==========


class AuditLogger(FlowComponent):
    """Logs all requests for audit purposes."""

    category = ComponentCategory.CUSTOM

    def __init__(self, app_name: str):
        self.app_name = app_name

    async def resolve(self, ctx: RequestContext) -> None:
        """Log request details."""
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "app": self.app_name,
            "method": ctx.request.method,
            "path": ctx.request.url.path,
            "user": ctx.user.get("sub") if ctx.user else None,
            "ip": ctx.request.client.host if ctx.request.client else None,
        }
        # In production, send to logging service
        print(f"[AUDIT] {log_entry}")

        # Store in context for later use
        ctx.state["audit_log"] = log_entry


# ========== Custom Request ID Component ==========


class RequestID(FlowComponent):
    """Generates unique request ID."""

    category = ComponentCategory.CUSTOM

    async def resolve(self, ctx: RequestContext) -> None:
        """Generate and store request ID."""
        # Check if already provided by client
        request_id = ctx.request.headers.get("X-Request-ID")

        if not request_id:
            # Generate new ID
            request_id = f"req_{int(time.time() * 1000)}"

        ctx.state["request_id"] = request_id

    def openapi_spec(self) -> dict[str, Any] | None:
        """Add request ID to OpenAPI spec."""
        return {
            "parameters": [
                {
                    "name": "X-Request-ID",
                    "in": "header",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": "Optional request ID for tracking",
                }
            ],
            "x-request-id": True,
        }


# ========== Custom Tenant Isolation Component ==========


class TenantIsolation(FlowComponent):
    """Enforces tenant isolation in multi-tenant applications."""

    category = ComponentCategory.CUSTOM

    async def resolve(self, ctx: RequestContext) -> None:
        """Extract and validate tenant ID."""
        # Get tenant from header or user context
        tenant_id = ctx.request.headers.get("X-Tenant-ID")

        if not tenant_id and ctx.user:
            # Fall back to user's tenant
            tenant_id = ctx.user.get("tenant_id")

        if not tenant_id:
            from fastapi_request_pipeline import PermissionDenied

            raise PermissionDenied("Tenant ID required")

        # Validate user has access to tenant
        if ctx.user and ctx.user.get("tenant_id") != tenant_id:
            from fastapi_request_pipeline import PermissionDenied

            raise PermissionDenied("Access to this tenant denied")

        ctx.state["tenant_id"] = tenant_id


# ========== Custom Response Time Component ==========


class ResponseTimer(FlowComponent):
    """Tracks response time."""

    category = ComponentCategory.CUSTOM

    async def resolve(self, ctx: RequestContext) -> None:
        """Record start time."""
        ctx.state["start_time"] = time.perf_counter()


# ========== Custom IP Whitelist Component ==========


class IPWhitelist(FlowComponent):
    """Restricts access to whitelisted IPs."""

    category = ComponentCategory.CUSTOM

    def __init__(self, allowed_ips: set[str]):
        self.allowed_ips = allowed_ips

    async def resolve(self, ctx: RequestContext) -> None:
        """Check if IP is whitelisted."""
        client_ip = None

        if ctx.request.client:
            client_ip = ctx.request.client.host
        else:
            # Check X-Forwarded-For
            forwarded = ctx.request.headers.get("X-Forwarded-For")
            if forwarded:
                client_ip = forwarded.split(",")[0].strip()

        if client_ip not in self.allowed_ips:
            from fastapi_request_pipeline import PermissionDenied

            raise PermissionDenied(f"IP {client_ip} not whitelisted")


# ========== Custom Usage Tracking Component ==========


class UsageTracker(FlowComponent):
    """Tracks API usage metrics."""

    category = ComponentCategory.CUSTOM

    async def resolve(self, ctx: RequestContext) -> None:
        """Track usage."""
        user_id = ctx.user.get("sub") if ctx.user else "anonymous"
        endpoint = ctx.request.url.path

        # In production, send to metrics service
        print(f"[METRICS] user={user_id} endpoint={endpoint}")

        # Could also check quota here
        ctx.state["usage_tracked"] = True


# ========== Setup mock auth ==========


async def decode_jwt(token: str) -> dict:
    """Mock JWT decoder."""
    if token == "valid-token":
        return {"sub": "user123", "tenant_id": "tenant-a"}
    if token == "tenant-b-token":
        return {"sub": "user456", "tenant_id": "tenant-b"}
    raise ValueError("Invalid token")


# ========== Example endpoints ==========

# Basic flow with audit logging
audit_flow = Flow(
    JWTAuthentication(decode=decode_jwt), AuditLogger(app_name="example-api")
)


@app.get("/audit-example")
async def audit_example(ctx: RequestContext = Depends(flow_dependency(audit_flow))):
    """Endpoint with audit logging."""
    return {"message": "Request logged", "audit": ctx.state.get("audit_log")}


# Flow with request ID
request_id_flow = Flow(RequestID(), JWTAuthentication(decode=decode_jwt))


@app.get("/with-request-id")
async def with_request_id(
    ctx: RequestContext = Depends(flow_dependency(request_id_flow)),
):
    """Endpoint with request ID tracking."""
    return {"message": "Success", "request_id": ctx.state["request_id"]}


# Multi-tenant flow
tenant_flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    TenantIsolation(),
    AuditLogger(app_name="multi-tenant-api"),
)


@app.get("/tenant-data")
async def tenant_data(ctx: RequestContext = Depends(flow_dependency(tenant_flow))):
    """Tenant-isolated endpoint."""
    return {
        "message": "Tenant data",
        "tenant_id": ctx.state["tenant_id"],
        "user": ctx.user["sub"],
    }


# IP whitelist flow
whitelist_flow = Flow(
    IPWhitelist(allowed_ips={"127.0.0.1", "::1", "192.168.1.100"}),
    JWTAuthentication(decode=decode_jwt),
)


@app.get("/admin-only")
async def admin_only(ctx: RequestContext = Depends(flow_dependency(whitelist_flow))):
    """IP-restricted endpoint."""
    return {"message": "Admin access", "user": ctx.user["sub"]}


# Combined flow with multiple custom components
full_flow = Flow(
    RequestID(),
    JWTAuthentication(decode=decode_jwt),
    TenantIsolation(),
    ResponseTimer(),
    UsageTracker(),
    AuditLogger(app_name="full-example"),
)


@app.get("/full-example")
async def full_example(ctx: RequestContext = Depends(flow_dependency(full_flow))):
    """Endpoint with all custom components."""
    elapsed = time.perf_counter() - ctx.state["start_time"]

    return {
        "message": "Success",
        "request_id": ctx.state["request_id"],
        "tenant_id": ctx.state["tenant_id"],
        "user": ctx.user["sub"],
        "response_time_ms": f"{elapsed * 1000:.2f}",
        "usage_tracked": ctx.state.get("usage_tracked"),
    }


enrich_openapi(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

    # Test commands:
    # Audit logging:
    #   curl -H "Authorization: Bearer valid-token" http://localhost:8000/audit-example
    #
    # Request ID:
    #   curl -H "Authorization: Bearer valid-token" http://localhost:8000/with-request-id
    #   curl -H "Authorization: Bearer valid-token" -H "X-Request-ID: custom-123" \
    #     http://localhost:8000/with-request-id
    #
    # Tenant isolation:
    #   curl -H "Authorization: Bearer valid-token" http://localhost:8000/tenant-data
    #   curl -H "Authorization: Bearer tenant-b-token" -H "X-Tenant-ID: tenant-a" \
    #     http://localhost:8000/tenant-data  # 403
    #
    # IP whitelist:
    #   curl -H "Authorization: Bearer valid-token" http://localhost:8000/admin-only
    #
    # Full example:
    #   curl -H "Authorization: Bearer valid-token" http://localhost:8000/full-example
