"""
Authentication examples showing different auth strategies.

Demonstrates:
- JWT authentication
- API Key authentication
- Cookie authentication
- Anonymous access with OverrideFlow
"""

from fastapi import Depends, FastAPI
from fastapi_request_pipeline import (
    AllowAnonymous,
    APIKeyAuthentication,
    CookieAuthentication,
    Flow,
    JWTAuthentication,
    OverrideFlow,
    RequestContext,
    enrich_openapi,
    flow_dependency,
    merge_flows,
)

app = FastAPI(title="Authentication Examples")


# JWT Authentication
async def decode_jwt(token: str) -> dict:
    """Decode JWT token."""
    # Mock implementation
    if token == "jwt-token":
        return {"sub": "jwt-user", "auth_method": "jwt"}
    raise ValueError("Invalid JWT")


jwt_flow = Flow(JWTAuthentication(decode=decode_jwt))


@app.get("/jwt")
async def jwt_endpoint(ctx: RequestContext = Depends(flow_dependency(jwt_flow))):
    """Endpoint protected with JWT authentication."""
    return {"message": "JWT authenticated", "user": ctx.user}


# API Key Authentication
async def validate_api_key(key: str) -> dict:
    """Validate API key and return user."""
    # Mock implementation
    if key == "secret-api-key":
        return {"sub": "api-user", "auth_method": "api_key"}
    raise ValueError("Invalid API key")


api_key_flow = Flow(
    APIKeyAuthentication(
        validate=validate_api_key,
        header="X-API-Key"
    )
)


@app.get("/api-key")
async def api_key_endpoint(ctx: RequestContext = Depends(flow_dependency(api_key_flow))):
    """Endpoint protected with API Key authentication."""
    return {"message": "API Key authenticated", "user": ctx.user}


# Cookie Authentication
async def lookup_session(session_id: str) -> dict:
    """Look up user by session ID."""
    # Mock implementation
    if session_id == "valid-session":
        return {"sub": "cookie-user", "auth_method": "cookie"}
    raise ValueError("Invalid session")


cookie_flow = Flow(
    CookieAuthentication(
        lookup=lookup_session,
        cookie_name="session_id"
    )
)


@app.get("/cookie")
async def cookie_endpoint(ctx: RequestContext = Depends(flow_dependency(cookie_flow))):
    """Endpoint protected with cookie authentication."""
    return {"message": "Cookie authenticated", "user": ctx.user}


# Mixed: Default JWT but allow anonymous for specific endpoint
base_flow = Flow(JWTAuthentication(decode=decode_jwt))
public_override = Flow(OverrideFlow(AllowAnonymous()))
public_flow = merge_flows(base_flow, public_override)


@app.get("/public")
async def public_with_override(
    ctx: RequestContext = Depends(flow_dependency(public_flow))
):
    """Public endpoint using flow override."""
    if ctx.user:
        return {"message": "Authenticated", "user": ctx.user}
    return {"message": "Anonymous access allowed"}


# Custom header and scheme
custom_jwt_flow = Flow(
    JWTAuthentication(
        decode=decode_jwt,
        header="X-Auth-Token",
        scheme="Token"
    )
)


@app.get("/custom-header")
async def custom_header_endpoint(
    ctx: RequestContext = Depends(flow_dependency(custom_jwt_flow))
):
    """JWT auth with custom header and scheme."""
    return {"message": "Custom auth header", "user": ctx.user}


enrich_openapi(app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

    # Test commands:
    # JWT:
    #   curl -H "Authorization: Bearer jwt-token" http://localhost:8000/jwt
    #
    # API Key:
    #   curl -H "X-API-Key: secret-api-key" http://localhost:8000/api-key
    #
    # Cookie:
    #   curl -H "Cookie: session_id=valid-session" http://localhost:8000/cookie
    #
    # Public:
    #   curl http://localhost:8000/public
    #   curl -H "Authorization: Bearer jwt-token" http://localhost:8000/public
    #
    # Custom Header:
    #   curl -H "X-Auth-Token: Token jwt-token" http://localhost:8000/custom-header
