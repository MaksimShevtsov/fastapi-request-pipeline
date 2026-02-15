"""
Flow composition examples.

Demonstrates:
- Merging flows at different levels (app, router, route)
- Overriding components with OverrideFlow
- Disabling components with DisableFlow
- Layered composition patterns
"""

from fastapi import APIRouter, Depends, FastAPI

from fastapi_request_pipeline import (
    AllowAnonymous,
    ComponentCategory,
    DisableFlow,
    Flow,
    HasRole,
    JWTAuthentication,
    OverrideFlow,
    RateLimit,
    RequestContext,
    enrich_openapi,
    flow_dependency,
    merge_flows,
)

app = FastAPI(title="Flow Composition Examples")


async def decode_jwt(token: str) -> dict:
    """Mock JWT decoder."""
    if token == "admin-token":
        return {"sub": "admin", "role": "admin"}
    if token == "user-token":
        return {"sub": "user", "role": "user"}
    raise ValueError("Invalid token")


# ========== Application-level flow ==========
# Base security for entire application
app_flow = Flow(
    JWTAuthentication(decode=decode_jwt), RateLimit(rate=1000, window_seconds=3600)
)


# ========== Router-level flows ==========

# Admin router - requires admin role
admin_router = APIRouter(prefix="/admin")
admin_router_flow = Flow(HasRole("admin"))


@admin_router.get("/dashboard")
async def admin_dashboard(
    ctx: RequestContext = Depends(
        flow_dependency(merge_flows(app_flow, admin_router_flow))
    ),
):
    """Admin dashboard - requires admin role."""
    return {
        "message": "Admin Dashboard",
        "user": ctx.user["sub"],
        "role": ctx.user["role"],
    }


@admin_router.get("/users")
async def admin_users(
    ctx: RequestContext = Depends(
        flow_dependency(merge_flows(app_flow, admin_router_flow))
    ),
):
    """Admin user management."""
    return {"message": "User Management", "admin": ctx.user["sub"]}


app.include_router(admin_router)


# Public router - no authentication required
public_router = APIRouter(prefix="/public")
# Override authentication requirement
public_router_flow = Flow(OverrideFlow(AllowAnonymous()))


@public_router.get("/health")
async def health_check(
    ctx: RequestContext = Depends(
        flow_dependency(merge_flows(app_flow, public_router_flow))
    ),
):
    """Health check - no auth required, but still rate limited."""
    return {"status": "healthy", "authenticated": ctx.user is not None}


@public_router.get("/status")
async def status(
    ctx: RequestContext = Depends(
        flow_dependency(merge_flows(app_flow, public_router_flow))
    ),
):
    """Status endpoint."""
    return {"status": "operational"}


app.include_router(public_router)


# ========== Route-level customization ==========


# Regular authenticated endpoint with app-level defaults
@app.get("/profile")
async def profile(ctx: RequestContext = Depends(flow_dependency(app_flow))):
    """User profile - uses app-level flow (auth + rate limit)."""
    return {"user": ctx.user}


# Endpoint with custom rate limit
route_strict_limit = Flow(
    RateLimit(rate=10, window_seconds=60)  # Overrides app-level limit
)


@app.post("/upload")
async def upload(
    ctx: RequestContext = Depends(
        flow_dependency(merge_flows(app_flow, route_strict_limit))
    ),
):
    """Upload endpoint with stricter rate limit: 10 req/min."""
    return {"message": "Upload started", "user": ctx.user["sub"]}


# Endpoint without rate limiting
no_throttle = Flow(DisableFlow(ComponentCategory.THROTTLING))


@app.get("/stream")
async def stream(
    ctx: RequestContext = Depends(flow_dependency(merge_flows(app_flow, no_throttle))),
):
    """Streaming endpoint - authenticated but not rate limited."""
    return {"message": "Streaming data", "user": ctx.user["sub"]}


# ========== Complex composition ==========

# Multiple layers: app -> router -> route
api_router = APIRouter(prefix="/api/v1")

# API router requires authentication (inherits from app)
# but adds custom rate limiting
api_router_flow = Flow(
    RateLimit(rate=100, window_seconds=60)  # API-specific limit
)


@api_router.get("/data")
async def get_data(
    ctx: RequestContext = Depends(
        flow_dependency(merge_flows(app_flow, api_router_flow))
    ),
):
    """API endpoint: auth + 100 req/min."""
    return {"data": "sample", "user": ctx.user["sub"]}


# Specific route in API needs no rate limit (e.g., webhooks)
webhook_flow = Flow(DisableFlow(ComponentCategory.THROTTLING))


@api_router.post("/webhook")
async def webhook(
    ctx: RequestContext = Depends(
        flow_dependency(merge_flows(app_flow, api_router_flow, webhook_flow))
    ),
):
    """Webhook endpoint: auth but no rate limit."""
    return {"message": "Webhook received", "user": ctx.user["sub"]}


app.include_router(api_router)


enrich_openapi(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

    # Test commands:
    # Admin endpoints (requires admin role):
    #   curl -H "Authorization: Bearer admin-token" \
    #     http://localhost:8000/admin/dashboard
    #   curl -H "Authorization: Bearer user-token" \
    #     http://localhost:8000/admin/dashboard  # 403
    #
    # Public endpoints (no auth):
    #   curl http://localhost:8000/public/health
    #   curl http://localhost:8000/public/status
    #
    # Regular endpoint:
    #   curl -H "Authorization: Bearer user-token" http://localhost:8000/profile
    #
    # Custom rate limit:
    #   for i in {1..15}; do curl -X POST -H "Authorization: Bearer user-token" \
    #     http://localhost:8000/upload; done
    #
    # No rate limit:
    #   curl -H "Authorization: Bearer user-token" http://localhost:8000/stream
    #
    # API endpoints:
    #   curl -H "Authorization: Bearer user-token" http://localhost:8000/api/v1/data
    #   curl -X POST -H "Authorization: Bearer user-token" \
    #     http://localhost:8000/api/v1/webhook
