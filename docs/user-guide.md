# User Guide

## Overview

`fastapi-request-pipeline` provides a composable, type-safe approach to building request processing flows in FastAPI applications. Instead of scattering authentication, permissions, throttling, and other cross-cutting concerns across your codebase, you define reusable flows that compose cleanly.

## Core Concepts

### Flow

A `Flow` is an ordered container of components that process requests sequentially. Components are automatically sorted by their category to ensure proper execution order.

```python
from fastapi_request_pipeline import Flow, JWTAuthentication, RateLimit

flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    RateLimit(rate=100, window_seconds=60)
)
```

### Components

Components are processing units that implement specific functionality. Each component:

- Belongs to a category (authentication, permission, throttling, etc.)
- Implements `async def resolve(ctx: RequestContext) -> None`
- Can modify the `RequestContext` or raise exceptions to abort the flow

Built-in component categories (execution order):

1. **AUTHENTICATION** - Verify identity
2. **PERMISSION** - Check authorization
3. **FEATURE** - Feature flags
4. **THROTTLING** - Rate limiting
5. **FILTERS** - Query filtering
6. **PAGINATION** - Result pagination
7. **CUSTOM** - Custom logic

### RequestContext

The `RequestContext` is a lightweight container passed through the pipeline:

```python
@dataclass
class RequestContext:
    request: Request           # Starlette request object
    user: Any | None = None   # Populated by authentication
    state: dict[str, Any]     # Arbitrary key-value storage
```

Components can read from and write to the context, enabling data flow between stages.

## Basic Usage

### Step 1: Define a Flow

```python
from fastapi import FastAPI, Depends
from fastapi_request_pipeline import (
    Flow,
    JWTAuthentication,
    Authenticated,
    RateLimit,
    flow_dependency,
    enrich_openapi,
)

async def decode_jwt(token: str) -> dict:
    # Your JWT decoding logic
    return {"sub": "user123", "role": "admin"}

# Define your flow
protected_flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    Authenticated(),
    RateLimit(rate=100, window_seconds=60),
)
```

### Step 2: Use as Dependency

```python
app = FastAPI()

@app.get("/protected")
async def protected_endpoint(
    ctx: RequestContext = Depends(flow_dependency(protected_flow))
):
    return {
        "message": "Hello!",
        "user": ctx.user
    }

# Enrich OpenAPI schema with flow metadata
enrich_openapi(app)
```

### Step 3: Make Requests

```bash
curl -H "Authorization: Bearer <your-jwt>" http://localhost:8000/protected
```

## Authentication

### JWT Authentication

```python
from fastapi_request_pipeline import JWTAuthentication
import jwt

async def decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise AuthenticationFailed()

flow = Flow(JWTAuthentication(decode=decode_jwt))
```

Custom header and scheme:

```python
flow = Flow(
    JWTAuthentication(
        decode=decode_jwt,
        header="X-Auth-Token",
        scheme="Token"
    )
)
```

### Cookie Authentication

```python
from fastapi_request_pipeline import CookieAuthentication

async def lookup_session(session_id: str) -> dict:
    user = await db.get_user_by_session(session_id)
    if not user:
        raise AuthenticationFailed()
    return user

flow = Flow(
    CookieAuthentication(
        lookup=lookup_session,
        cookie_name="session_id"
    )
)
```

### API Key Authentication

```python
from fastapi_request_pipeline import APIKeyAuthentication

async def validate_api_key(key: str) -> dict:
    user = await db.get_user_by_api_key(key)
    if not user:
        raise AuthenticationFailed()
    return user

flow = Flow(
    APIKeyAuthentication(
        validate=validate_api_key,
        header="X-API-Key"
    )
)
```

### Allow Anonymous Access

```python
from fastapi_request_pipeline import AllowAnonymous, OverrideFlow

# Base flow requires authentication
protected_flow = Flow(JWTAuthentication(decode=decode_jwt))

# Override for public endpoint
public_flow = Flow(OverrideFlow(AllowAnonymous()))
final = merge_flows(protected_flow, public_flow)
```

## Permissions

### Require Authentication

```python
from fastapi_request_pipeline import Authenticated

flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    Authenticated()  # Fails if ctx.user is None
)
```

### Role-Based Access Control

```python
from fastapi_request_pipeline import HasRole

# User object must have 'role' attribute
flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    HasRole("admin")
)
```

Custom attribute:

```python
flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    HasRole("premium", attr="subscription_tier")
)
```

### Permission Checks

```python
from fastapi_request_pipeline import HasPermission

# User object must have 'permissions' iterable
flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    HasPermission("posts:write")
)
```

Custom attribute:

```python
flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    HasPermission("delete_users", attr="scopes")
)
```

## Rate Limiting

### Basic Rate Limiting

```python
from fastapi_request_pipeline import RateLimit

# 100 requests per 60 seconds per user/IP
flow = Flow(
    RateLimit(rate=100, window_seconds=60)
)
```

### Custom Rate Limit Keys

```python
def custom_key(ctx: RequestContext) -> str:
    # Rate limit by API key instead of user/IP
    return f"apikey:{ctx.request.headers.get('X-API-Key', 'unknown')}"

flow = Flow(
    RateLimit(
        rate=1000,
        window_seconds=3600,
        key_func=custom_key
    )
)
```

### Custom Throttle Backend

Implement the `ThrottleBackend` protocol for distributed rate limiting:

```python
from fastapi_request_pipeline import ThrottleBackend
import redis.asyncio as redis

class RedisThrottleBackend:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def increment(self, key: str, window_seconds: int) -> tuple[int, int]:
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()
        count = results[0]
        ttl = await self.redis.ttl(key)
        return count, max(ttl, 1)

    async def reset(self, key: str) -> None:
        await self.redis.delete(key)

# Use it
backend = RedisThrottleBackend(redis_client)
flow = Flow(
    RateLimit(rate=100, window_seconds=60, backend=backend)
)
```

## Feature Flags

```python
from fastapi_request_pipeline import FeatureEnabled

async def is_feature_enabled(name: str, ctx: RequestContext) -> bool:
    # Check your feature flag service
    return await feature_flags.is_enabled(name, ctx.user)

flow = Flow(
    FeatureEnabled(
        name="new_api",
        is_enabled=is_feature_enabled
    )
)
```

## Filters and Pagination

### Query Filters

```python
from fastapi_request_pipeline import QueryFilter

flow = Flow(
    QueryFilter(
        allowed_fields={"status", "priority", "assignee"},
        operators={"eq", "in", "gte", "lte"}
    )
)

# GET /tasks?status=eq:open&priority=in:high,urgent
# ctx.state["filters"] = [
#     {"field": "status", "operator": "eq", "value": "open"},
#     {"field": "priority", "operator": "in", "value": ["high", "urgent"]}
# ]
```

### Pagination

```python
from fastapi_request_pipeline import LimitOffset

flow = Flow(
    LimitOffset(default_limit=20, max_limit=100)
)

# GET /items?limit=50&offset=100
# ctx.state["limit"] = 50
# ctx.state["offset"] = 100
```

## Flow Composition

### Merging Flows

```python
from fastapi_request_pipeline import merge_flows

# Application-level flow
app_flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    RateLimit(rate=1000, window_seconds=60)
)

# Router-level flow
admin_router_flow = Flow(
    HasRole("admin")
)

# Route-level customization
specific_flow = Flow(
    RateLimit(rate=10, window_seconds=60)  # Stricter limit
)

# Merge with last-writer-wins per category
final_flow = merge_flows(app_flow, admin_router_flow, specific_flow)
```

### Override Components

```python
from fastapi_request_pipeline import OverrideFlow

# Replace all authentication components
public_flow = Flow(
    OverrideFlow(AllowAnonymous())
)

final = merge_flows(protected_flow, public_flow)
```

### Disable Components

```python
from fastapi_request_pipeline import DisableFlow, ComponentCategory

# Remove all throttling
no_throttle_flow = Flow(
    DisableFlow(ComponentCategory.THROTTLING)
)

final = merge_flows(app_flow, no_throttle_flow)
```

## Custom Components

Create custom components by subclassing `FlowComponent`:

```python
from fastapi_request_pipeline import FlowComponent, ComponentCategory, RequestContext

class AuditLog(FlowComponent):
    category = ComponentCategory.CUSTOM

    def __init__(self, logger):
        self.logger = logger

    async def resolve(self, ctx: RequestContext) -> None:
        await self.logger.log({
            "user": ctx.user,
            "path": ctx.request.url.path,
            "method": ctx.request.method
        })

flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    AuditLog(logger=my_logger)
)
```

## Hooks

Hooks allow you to observe and react to flow execution:

```python
from fastapi_request_pipeline import FlowHook, AfterFlow, BeforeFlow, AfterComponent

class MetricsHook(FlowHook):
    async def on_flow_start(self, ctx: RequestContext) -> None:
        ctx.state["start_time"] = time.time()

    async def on_component(
        self,
        ctx: RequestContext,
        component: FlowComponent,
        error: Exception | None
    ) -> None:
        if error:
            metrics.increment(f"component.{type(component).__name__}.error")

    async def on_flow_end(self, ctx: RequestContext) -> None:
        duration = time.time() - ctx.state["start_time"]
        metrics.histogram("flow.duration", duration)

flow = Flow(JWTAuthentication(decode=decode_jwt))
flow.add_hook(MetricsHook())
```

## Debug Mode

Enable debug mode for detailed execution traces:

```python
flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    RateLimit(rate=100, window_seconds=60),
    debug=True
)

@app.get("/endpoint")
async def endpoint(ctx: RequestContext = Depends(flow_dependency(flow))):
    trace = ctx.state.get("trace")
    # trace.entries contains timing and outcome for each component
    # trace.total_duration_ms
    # trace.outcome: "OK" | "ABORTED" | "ERROR"
    return {"trace": trace}
```

## OpenAPI Integration

The library automatically enriches your OpenAPI schema:

```python
from fastapi_request_pipeline import enrich_openapi

app = FastAPI()

# Define routes with flows...

# Call this AFTER all routes are registered
enrich_openapi(app)
```

This adds:
- Security schemes (JWT, API Key, Cookie)
- Security requirements per endpoint
- Error responses (401, 403, 429, etc.)
- Rate limit headers
- Query parameters (filters, pagination)

## Error Handling

The library provides specific exceptions:

```python
from fastapi_request_pipeline import (
    AuthenticationFailed,  # 401
    PermissionDenied,      # 403
    FeatureDisabled,       # 403
    Throttled,             # 429
)

# All inherit from FlowAbort, which becomes HTTPException
```

Custom error handling:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(AuthenticationFailed)
async def auth_failed_handler(request: Request, exc: AuthenticationFailed):
    return JSONResponse(
        status_code=401,
        content={"error": "Authentication required"}
    )
```

## Best Practices

1. **Define flows at module level** - Create them once, reuse across endpoints
2. **Use merge_flows for composition** - Layer app, router, and route flows
3. **Keep components focused** - One responsibility per component
4. **Use debug mode in development** - Enable tracing to understand flow execution
5. **Call enrich_openapi** - Automatically document your API security
6. **Use custom backends for production** - Replace `InMemoryThrottleBackend` with Redis
7. **Test flows in isolation** - Components are async functions, easy to unit test

## Testing

Test flows without FastAPI:

```python
from starlette.requests import Request
from fastapi_request_pipeline import RequestContext

async def test_jwt_auth():
    async def decode(token: str) -> dict:
        return {"sub": "test-user"}

    auth = JWTAuthentication(decode=decode)

    # Create mock request
    scope = {
        "type": "http",
        "headers": [(b"authorization", b"Bearer test-token")]
    }
    request = Request(scope)
    ctx = RequestContext(request=request)

    await auth.resolve(ctx)

    assert ctx.user == {"sub": "test-user"}
```

Integration testing with FastAPI:

```python
from httpx import AsyncClient, ASGITransport

async def test_protected_endpoint():
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/protected",
            headers={"Authorization": "Bearer valid-token"}
        )
        assert resp.status_code == 200
```
