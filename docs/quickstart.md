# Quick Start Guide

Get started with `fastapi-request-pipeline` in 5 minutes.

## Installation

```bash
pip install fastapi-request-pipeline
```

## Your First Flow

Create a simple FastAPI app with JWT authentication:

```python
from fastapi import FastAPI, Depends
from fastapi_request_pipeline import (
    Flow,
    JWTAuthentication,
    RequestContext,
    flow_dependency,
    enrich_openapi,
)

app = FastAPI()

# Step 1: Create a JWT decoder
async def decode_jwt(token: str) -> dict:
    # For production, use python-jose or PyJWT
    # This is a mock implementation
    if token == "valid-token":
        return {"sub": "user123", "email": "user@example.com", "roles": ["user"]}
    raise ValueError("Invalid token")

# Step 2: Create a flow
auth_flow = Flow(
    JWTAuthentication(decode=decode_jwt)
)

# Step 3: Use as dependency
@app.get("/protected")
async def protected_endpoint(
    ctx: RequestContext = Depends(flow_dependency(auth_flow))
):
    return {
        "message": f"Hello, {ctx.user['email']}!",
        "user": ctx.user
    }

# Step 4: Enrich OpenAPI
enrich_openapi(app)

# Run: uvicorn main:app --reload
```

Test it:

```bash
# This will fail with 401
curl http://localhost:8000/protected

# This will succeed
curl -H "Authorization: Bearer valid-token" http://localhost:8000/protected
```

## Adding Rate Limiting

Add rate limiting to prevent abuse:

```python
from fastapi_request_pipeline import RateLimit

# Create flow with authentication and rate limiting
protected_flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    RateLimit(rate=10, window_seconds=60)  # 10 requests per minute
)

@app.get("/api/data")
async def get_data(
    ctx: RequestContext = Depends(flow_dependency(protected_flow))
):
    return {"data": "some data", "user": ctx.user["sub"]}
```

Test it:

```bash
# First 10 requests succeed, 11th fails with 429
for i in {1..11}; do
    curl -H "Authorization: Bearer valid-token" http://localhost:8000/api/data
done
```

## Adding Permissions

Add role-based or permission-based access control:

```python
from fastapi_request_pipeline import HasRole, HasPermission

# Update decoder to include roles
async def decode_jwt(token: str) -> dict:
    if token == "admin-token":
        return {
            "sub": "admin",
            "roles": ["admin"],
            "permissions": ["read", "write", "delete"],
        }
    if token == "user-token":
        return {"sub": "user", "roles": ["user"], "permissions": ["read", "write"]}
    raise ValueError("Invalid token")

# Admin-only endpoint
admin_flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    HasRole("admin")
)

@app.get("/admin/dashboard")
async def admin_dashboard(
    ctx: RequestContext = Depends(flow_dependency(admin_flow))
):
    return {"message": "Admin Dashboard"}

# Permission-based endpoint
write_flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    HasPermission("write")
)

@app.post("/posts")
async def create_post(
    ctx: RequestContext = Depends(flow_dependency(write_flow))
):
    return {"message": "Post created", "author": ctx.user["sub"]}
```

Test it:

```bash
# Admin endpoint
curl -H "Authorization: Bearer admin-token" http://localhost:8000/admin/dashboard  # Success
curl -H "Authorization: Bearer user-token" http://localhost:8000/admin/dashboard   # 403 Forbidden

# Permission-based endpoint
curl -X POST -H "Authorization: Bearer user-token" http://localhost:8000/posts  # Success
```

## Flow Composition

Compose flows at different levels:

```python
from fastapi import APIRouter
from fastapi_request_pipeline import merge_flows

# Update decoder to support roles for admin checks
async def decode_jwt(token: str) -> dict:
    if token == "admin-token":
        return {"sub": "admin", "roles": ["admin"]}
    if token == "user-token":
        return {"sub": "user", "roles": ["user"]}
    raise ValueError("Invalid token")

# Application-level: All endpoints require auth and basic rate limiting
app_flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    RateLimit(rate=1000, window_seconds=3600)
)

# Admin router: Additional admin role requirement
admin_router = APIRouter(prefix="/admin")
admin_router_flow = Flow(HasRole("admin"))

@admin_router.get("/users")
async def list_users(
    ctx: RequestContext = Depends(
        flow_dependency(merge_flows(app_flow, admin_router_flow))
    )
):
    return {"users": ["user1", "user2"]}

app.include_router(admin_router)

# Route-level: Stricter rate limit for expensive operations
strict_limit = Flow(RateLimit(rate=5, window_seconds=60))

@app.post("/process")
async def process_data(
    ctx: RequestContext = Depends(
        flow_dependency(merge_flows(app_flow, strict_limit))
    )
):
    return {"message": "Processing started"}
```

## Public Endpoints

Allow public access by overriding authentication:

```python
from fastapi_request_pipeline import AllowAnonymous, OverrideFlow

# Base flow requires authentication
base_flow = Flow(JWTAuthentication(decode=decode_jwt))

# Override for public endpoint
public_flow = Flow(OverrideFlow(AllowAnonymous()))

@app.get("/public")
async def public_endpoint(
    ctx: RequestContext = Depends(
        flow_dependency(merge_flows(base_flow, public_flow))
    )
):
    if ctx.user:
        return {"message": "Authenticated access", "user": ctx.user}
    return {"message": "Anonymous access"}
```

## Pagination and Filters

Add query parameters for pagination and filtering:

```python
from fastapi_request_pipeline import LimitOffset, QueryFilter

list_flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    QueryFilter("status", "priority"),
    LimitOffset(default_limit=20, max_limit=100)
)

@app.get("/tasks")
async def list_tasks(
    ctx: RequestContext = Depends(flow_dependency(list_flow))
):
    # ctx.state contains parsed pagination and filters
    pagination = ctx.state["pagination"]
    limit = pagination["limit"]
    offset = pagination["offset"]
    filters = ctx.state.get("filters", {})

    # Use these to query your database
    # tasks = db.query(Task).filter(...).limit(limit).offset(offset)

    return {
        "tasks": [],  # Your actual tasks
        "limit": limit,
        "offset": offset,
        "filters": filters
    }
```

Test it:

```bash
# With pagination
curl -H "Authorization: Bearer valid-token" \
  "http://localhost:8000/tasks?limit=50&offset=100"

# With filters
curl -H "Authorization: Bearer valid-token" \
    "http://localhost:8000/tasks?status=open&priority=high"
```

## Debug Mode

Enable debug mode to see detailed execution traces:

```python
# Create flow with debug enabled
debug_flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    RateLimit(rate=100, window_seconds=60),
    debug=True
)

@app.get("/debug")
async def debug_endpoint(
    ctx: RequestContext = Depends(flow_dependency(debug_flow))
):
    trace = ctx.state.get("trace")
    return {
        "data": "some data",
        "trace": {
            "total_duration_ms": trace.total_duration_ms,
            "outcome": trace.outcome,
            "components": [
                {
                    "name": entry.component_name,
                    "duration_ms": entry.duration_ms,
                    "outcome": entry.outcome
                }
                for entry in trace.entries
            ]
        }
    }
```

## Next Steps

- **[User Guide](user-guide.md)** - Comprehensive guide with all features
- **[API Reference](api-reference.md)** - Complete API documentation
- **[Examples](../examples/)** - Working code examples for various use cases
- **[Custom Components](user-guide.md#custom-components)** - Learn to create your own components

## Common Patterns

### Multi-tier Rate Limiting

```python
def tier_key(ctx: RequestContext) -> str:
    if ctx.user and ctx.user.get("tier") == "premium":
        return f"premium:{ctx.user['sub']}"
    if ctx.user:
        return f"free:{ctx.user['sub']}"
    return f"ip:{ctx.request.client.host}"

flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    RateLimit(rate=1000, window_seconds=3600, key_func=tier_key)
)
```

### Conditional Authentication

```python
# Require auth but allow anonymous with limited access
@app.get("/posts")
async def list_posts(
    ctx: RequestContext = Depends(flow_dependency(public_flow))
):
    if ctx.user:
        # Authenticated: show all posts
        return {"posts": all_posts}
    else:
        # Anonymous: show only published posts
        return {"posts": published_posts}
```

### Custom Error Messages

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi_request_pipeline import AuthenticationFailed

@app.exception_handler(AuthenticationFailed)
async def auth_handler(request: Request, exc: AuthenticationFailed):
    return JSONResponse(
        status_code=401,
        content={"error": "Please log in to access this resource"}
    )
```

## Production Checklist

When deploying to production:

- [ ] Use proper JWT library (python-jose, PyJWT)
- [ ] Use Redis-backed rate limiting for multi-process deployments
- [ ] Store secrets in environment variables
- [ ] Add proper error handlers
- [ ] Enable HTTPS
- [ ] Set up monitoring and logging
- [ ] Configure CORS properly
- [ ] Use database connections properly
- [ ] Add request ID tracking
- [ ] Set up health check endpoints

## Troubleshooting

**Q: My flow components aren't executing in the order I specified**

A: Components are automatically sorted by category. Use `ctx.state["trace"]` in debug mode to see execution order.

**Q: Rate limiting doesn't work across multiple workers**

A: Use a Redis-backed `ThrottleBackend` instead of the default `InMemoryThrottleBackend`.

**Q: OpenAPI schema doesn't show my security requirements**

A: Make sure to call `enrich_openapi(app)` after defining all routes.

**Q: How do I test endpoints with flows?**

A: Use `httpx.AsyncClient` with `ASGITransport`. See examples in `tests/` directory.

## Need Help?

- Check the [examples](../examples/) for working code
- Read the [User Guide](user-guide.md) for detailed documentation
- Look at the [test suite](../tests/) for usage patterns
- Open an issue on GitHub for bugs or feature requests
