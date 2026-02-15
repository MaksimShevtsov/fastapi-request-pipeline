# Documentation

Complete documentation for `fastapi-request-pipeline`.

## Getting Started

- **[Quick Start Guide](quickstart.md)** - Get up and running in 5 minutes
- **[User Guide](user-guide.md)** - Comprehensive guide covering all features
- **[API Reference](api-reference.md)** - Complete API documentation

## Examples

See the [examples/](../examples/) directory for working code examples:

1. **[Basic Usage](../examples/01_basic_usage.py)** - Simple authentication flow
2. **[Authentication](../examples/02_authentication.py)** - Different auth strategies (JWT, API Key, Cookie)
3. **[Permissions](../examples/03_permissions.py)** - RBAC and permission-based access control
4. **[Rate Limiting](../examples/04_rate_limiting.py)** - Various rate limiting patterns
5. **[Flow Composition](../examples/05_flow_composition.py)** - Composing flows at different levels
6. **[Custom Components](../examples/06_custom_components.py)** - Building custom components
7. **[Real-World App](../examples/07_real_world_app.py)** - Complete blog API application

## Deployment

- **[CI/CD and Deployment](deployment.md)** - GitHub Actions, PyPI publishing

## Core Concepts

### Flow

A `Flow` is an ordered container of processing components. Components are automatically sorted by category to ensure correct execution order.

```python
flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    HasRole("admin"),
    RateLimit(rate=100, window_seconds=60),
)
```

### Components

Components implement the `FlowComponent` interface and belong to a category:

- **AUTHENTICATION** (order: 1) - Identity verification
- **PERMISSION** (order: 2) - Authorization checks
- **FEATURE** (order: 3) - Feature flags
- **THROTTLING** (order: 4) - Rate limiting
- **FILTERS** (order: 5) - Query filtering
- **PAGINATION** (order: 6) - Result pagination
- **CUSTOM** (order: 7) - Custom logic

### RequestContext

The context object passed through the pipeline:

```python
@dataclass
class RequestContext:
    request: Request           # Starlette request
    user: Any | None = None   # Set by authentication
    state: dict[str, Any]     # Arbitrary storage
```

### Flow Dependency

Convert a flow to a FastAPI dependency:

```python
@app.get("/endpoint")
async def endpoint(
    ctx: RequestContext = Depends(flow_dependency(flow))
):
    return {"user": ctx.user}
```

## Component Categories

### Built-in Authentication Components

- `JWTAuthentication` - Bearer token authentication
- `APIKeyAuthentication` - API key in headers
- `CookieAuthentication` - Session cookies
- `AllowAnonymous` - Skip authentication

### Built-in Permission Components

- `Authenticated` - Require non-null user
- `HasRole` - Check user role
- `HasPermission` - Check user permissions

### Built-in Throttling Components

- `RateLimit` - Configurable rate limiting
- `InMemoryThrottleBackend` - Default backend
- `ThrottleBackend` - Protocol for custom backends

### Built-in Filter/Pagination Components

- `QueryFilter` - Parse query string filters
- `LimitOffset` - Offset-based pagination

## Advanced Topics

### Flow Composition

Merge flows from different levels:

```python
final_flow = merge_flows(
    app_flow,      # Application-level defaults
    router_flow,   # Router-level additions
    route_flow     # Route-specific overrides
)
```

### Override and Disable

- `OverrideFlow(component)` - Replace all components of a category
- `DisableFlow(category)` - Remove all components of a category

### Hooks

Observe flow execution:

```python
class MetricsHook(FlowHook):
    async def on_flow_start(self, ctx: RequestContext) -> None:
        pass

    async def on_component(
        self, ctx: RequestContext, component: FlowComponent, error: Exception | None
    ) -> None:
        pass

    async def on_flow_end(self, ctx: RequestContext) -> None:
        pass

flow.add_hook(MetricsHook())
```

### Debug Mode

Enable detailed traces:

```python
flow = Flow(..., debug=True)

# Access trace in endpoint
trace = ctx.state.get("trace")
# trace.entries, trace.total_duration_ms, trace.outcome
```

### OpenAPI Integration

Automatically enrich OpenAPI schema:

```python
enrich_openapi(app)  # Call after defining all routes
```

This adds:
- Security schemes
- Security requirements per endpoint
- Error responses (401, 403, 429, etc.)
- Rate limit headers
- Query parameters

## Best Practices

1. **Define flows at module level** - Create once, reuse everywhere
2. **Use composition** - Layer flows from app → router → route
3. **Keep components focused** - Single responsibility principle
4. **Use debug mode in development** - Understand execution flow
5. **Call enrich_openapi()** - Auto-document security requirements
6. **Use Redis for production** - Replace InMemoryThrottleBackend
7. **Test components in isolation** - Easy unit testing

## Common Patterns

### Multi-tenant Applications

```python
class TenantIsolation(FlowComponent):
    category = ComponentCategory.CUSTOM

    async def resolve(self, ctx: RequestContext) -> None:
        tenant_id = ctx.request.headers.get("X-Tenant-ID")
        if ctx.user.tenant_id != tenant_id:
            raise PermissionDenied()
        ctx.state["tenant_id"] = tenant_id
```

### Request ID Tracking

```python
class RequestID(FlowComponent):
    category = ComponentCategory.CUSTOM

    async def resolve(self, ctx: RequestContext) -> None:
        request_id = ctx.request.headers.get("X-Request-ID")
        if not request_id:
            request_id = f"req_{int(time.time() * 1000)}"
        ctx.state["request_id"] = request_id
```

### Audit Logging

```python
class AuditLog(FlowComponent):
    category = ComponentCategory.CUSTOM

    async def resolve(self, ctx: RequestContext) -> None:
        await logger.log({
            "user": ctx.user,
            "path": ctx.request.url.path,
            "method": ctx.request.method,
        })
```

### IP Whitelisting

```python
class IPWhitelist(FlowComponent):
    category = ComponentCategory.CUSTOM

    def __init__(self, allowed_ips: set[str]):
        self.allowed_ips = allowed_ips

    async def resolve(self, ctx: RequestContext) -> None:
        if ctx.request.client.host not in self.allowed_ips:
            raise PermissionDenied()
```

## Testing

### Unit Testing Components

```python
from starlette.requests import Request

async def test_jwt_auth():
    auth = JWTAuthentication(decode=decode_jwt)
    scope = {"type": "http", "headers": [(b"authorization", b"Bearer token")]}
    request = Request(scope)
    ctx = RequestContext(request=request)
    await auth.resolve(ctx)
    assert ctx.user == expected_user
```

### Integration Testing

```python
from httpx import AsyncClient, ASGITransport

async def test_endpoint():
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/endpoint", headers={"Authorization": "Bearer token"})
        assert resp.status_code == 200
```

## Migration Guide

### From Middleware

**Before:**

```python
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    token = request.headers.get("Authorization")
    if not token:
        return JSONResponse(status_code=401)
    request.state.user = decode_jwt(token)
    return await call_next(request)
```

**After:**

```python
auth_flow = Flow(JWTAuthentication(decode=decode_jwt))

@app.get("/endpoint")
async def endpoint(ctx: RequestContext = Depends(flow_dependency(auth_flow))):
    return {"user": ctx.user}
```

### From Dependencies

**Before:**

```python
async def require_admin(request: Request):
    user = await get_current_user(request)
    if user.role != "admin":
        raise HTTPException(403)
    return user

@app.get("/admin")
async def admin_endpoint(user: User = Depends(require_admin)):
    return {"admin": user}
```

**After:**

```python
admin_flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    HasRole("admin")
)

@app.get("/admin")
async def admin_endpoint(ctx: RequestContext = Depends(flow_dependency(admin_flow))):
    return {"admin": ctx.user}
```

## FAQ

**Q: When should I use flows vs regular dependencies?**

A: Use flows for cross-cutting concerns (auth, permissions, rate limiting). Use regular dependencies for business logic.

**Q: Can I use flows with other FastAPI features?**

A: Yes! Flows work alongside regular dependencies, middleware, exception handlers, etc.

**Q: How do I handle multiple authentication methods?**

A: Create separate flows and use them on different endpoints, or create a custom component that tries multiple methods.

**Q: Can I modify the request in a component?**

A: Components shouldn't modify the request itself, but can store data in `ctx.state` for later use.

**Q: How do I pass configuration to components?**

A: Pass configuration via component constructor parameters.

## Contributing

Contributions welcome! Please:

1. Add tests for new features
2. Update documentation
3. Follow existing code style (ruff)
4. Ensure mypy --strict passes
5. Add examples for new components

## License

MIT License - see LICENSE file for details.
