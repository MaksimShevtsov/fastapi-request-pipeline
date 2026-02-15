"""
Basic usage example of fastapi-request-pipeline.

Demonstrates:
- Creating a simple flow with JWT authentication
- Using flow as a FastAPI dependency
- Accessing user context in endpoints
"""

from fastapi import Depends, FastAPI

from fastapi_request_pipeline import (
    Flow,
    JWTAuthentication,
    RequestContext,
    enrich_openapi,
    flow_dependency,
)

app = FastAPI(title="Basic Pipeline Example")


# Mock JWT decoder (replace with real implementation)
async def decode_jwt(token: str) -> dict:
    """Decode JWT token and return user data."""
    # In production, use a library like python-jose or PyJWT
    if token == "valid-token":
        return {"sub": "user123", "email": "user@example.com"}
    raise ValueError("Invalid token")


# Create a simple authenticated flow
auth_flow = Flow(JWTAuthentication(decode=decode_jwt))


@app.get("/")
async def public_endpoint():
    """Public endpoint - no authentication required."""
    return {"message": "Hello, World!"}


@app.get("/protected")
async def protected_endpoint(ctx: RequestContext = Depends(flow_dependency(auth_flow))):
    """Protected endpoint - requires JWT authentication."""
    return {"message": f"Hello, {ctx.user['email']}!", "user": ctx.user}


@app.get("/me")
async def get_current_user(ctx: RequestContext = Depends(flow_dependency(auth_flow))):
    """Get current user information."""
    return ctx.user


# Enrich OpenAPI schema with authentication requirements
enrich_openapi(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

    # Test with:
    # curl http://localhost:8000/
    # curl -H "Authorization: Bearer valid-token" http://localhost:8000/protected
    # curl -H "Authorization: Bearer valid-token" http://localhost:8000/me
