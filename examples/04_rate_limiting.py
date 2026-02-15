"""
Rate limiting examples.

Demonstrates:
- Basic rate limiting
- Custom rate limit keys
- Different limits for different endpoints
- Per-user vs per-IP rate limiting
"""

from fastapi import Depends, FastAPI

from fastapi_request_pipeline import (
    Flow,
    JWTAuthentication,
    RateLimit,
    RequestContext,
    enrich_openapi,
    flow_dependency,
)

app = FastAPI(title="Rate Limiting Examples")


async def decode_jwt(token: str) -> dict:
    """Mock JWT decoder."""
    if token == "premium-token":
        return {"sub": "premium-user", "tier": "premium"}
    if token == "free-token":
        return {"sub": "free-user", "tier": "free"}
    raise ValueError("Invalid token")


# Basic rate limiting - 10 requests per minute
basic_flow = Flow(RateLimit(rate=10, window_seconds=60))


@app.get("/public")
async def public_endpoint(ctx: RequestContext = Depends(flow_dependency(basic_flow))):
    """Public endpoint with IP-based rate limiting: 10 req/min."""
    return {"message": "Public endpoint", "client": ctx.request.client}


# Authenticated rate limiting - per user
auth_flow = Flow(
    JWTAuthentication(decode=decode_jwt), RateLimit(rate=100, window_seconds=60)
)


@app.get("/api/data")
async def authenticated_endpoint(
    ctx: RequestContext = Depends(flow_dependency(auth_flow)),
):
    """Authenticated endpoint: 100 req/min per user."""
    return {
        "message": "Data endpoint",
        "user": ctx.user["sub"],
        "tier": ctx.user["tier"],
    }


# Custom rate limit based on user tier
def tier_based_key(ctx: RequestContext) -> str:
    """Generate rate limit key based on user tier."""
    if ctx.user and ctx.user.get("tier") == "premium":
        # Premium users get separate higher limit
        return f"premium:{ctx.user['sub']}"
    if ctx.user:
        return f"free:{ctx.user['sub']}"
    # Anonymous users share IP-based limit
    if ctx.request.client:
        return f"ip:{ctx.request.client.host}"
    return "ip:unknown"


premium_flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    RateLimit(rate=1000, window_seconds=3600, key_func=tier_based_key),
)


@app.get("/api/premium")
async def premium_endpoint(
    ctx: RequestContext = Depends(flow_dependency(premium_flow)),
):
    """Premium endpoint with tier-based limiting: 1000 req/hour for premium."""
    return {
        "message": "Premium data",
        "user": ctx.user["sub"],
        "tier": ctx.user["tier"],
    }


# Strict rate limiting for expensive operations
strict_flow = Flow(
    JWTAuthentication(decode=decode_jwt), RateLimit(rate=5, window_seconds=60)
)


@app.post("/api/process")
async def process_endpoint(ctx: RequestContext = Depends(flow_dependency(strict_flow))):
    """Expensive operation: 5 req/min per user."""
    return {"message": "Processing started", "user": ctx.user["sub"]}


# API key-based rate limiting
def api_key_limiter(ctx: RequestContext) -> str:
    """Rate limit by API key."""
    api_key = ctx.request.headers.get("X-API-Key")
    if api_key:
        return f"apikey:{api_key}"
    return "apikey:unknown"


api_flow = Flow(RateLimit(rate=50, window_seconds=60, key_func=api_key_limiter))


@app.get("/api/external")
async def external_api_endpoint(
    ctx: RequestContext = Depends(flow_dependency(api_flow)),
):
    """External API endpoint: 50 req/min per API key."""
    api_key = ctx.request.headers.get("X-API-Key", "none")
    return {
        "message": "External API",
        "api_key": api_key[:8] + "..." if len(api_key) > 8 else api_key,
    }


enrich_openapi(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

    # Test commands:
    # Public (10 req/min per IP):
    #   for i in {1..15}; do curl http://localhost:8000/public; done
    #
    # Authenticated (100 req/min per user):
    #   for i in {1..105}; do curl -H "Authorization: Bearer free-token" \
    #     http://localhost:8000/api/data; done
    #
    # Premium (1000 req/hour):
    #   curl -H "Authorization: Bearer premium-token" http://localhost:8000/api/premium
    #
    # Expensive operation (5 req/min):
    #   for i in {1..10}; do curl -X POST -H "Authorization: Bearer free-token" \
    #     http://localhost:8000/api/process; done
    #
    # API Key (50 req/min):
    #   for i in {1..60}; do curl -H "X-API-Key: my-api-key" \
    #     http://localhost:8000/api/external; done
