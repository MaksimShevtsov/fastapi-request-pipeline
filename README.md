# fastapi-request-pipeline

[![CI](https://github.com/MaksimShevtsov/fastapi-request-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/MaksimShevtsov/fastapi-request-pipeline/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/MaksimShevtsov/fastapi-request-pipeline/branch/main/graph/badge.svg)](https://codecov.io/gh/MaksimShevtsov/fastapi-request-pipeline)
[![PyPI Version](https://img.shields.io/pypi/v/fastapi-request-pipeline)](https://pypi.org/project/fastapi-request-pipeline/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB.svg?logo=python&logoColor=white)](https://pypi.org/project/fastapi-request-pipeline/)
[![License](https://img.shields.io/github/license/MaksimShevtsov/fastapi-request-pipeline)](https://github.com/MaksimShevtsov/fastapi-request-pipeline/blob/main/LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

A composable, type-safe request processing pipeline for FastAPI. Build clean, maintainable APIs with reusable components for authentication, permissions, rate limiting, and more.

## Features

- **Composable Architecture** - Build complex request flows from simple, reusable FlowComponent instances
- **Type-Safe** - Full type hints with strict mypy checking
- **Built-in Components** - Authentication (JWT, API Key, Cookie), permissions, rate limiting, pagination, filters
- **Flow Composition** - Layer and merge flows at app, router, and route levels
- **OpenAPI Integration** - Automatic OpenAPI schema enrichment with security requirements
- **Debug Mode** - Detailed execution traces for development
- **Extensible** - Easy to create custom FlowComponent subclasses

## Quick Start

```bash
pip install fastapi-request-pipeline
```

```python
from fastapi import FastAPI, Depends
from fastapi_request_pipeline import (
    Flow,
    JWTAuthentication,
    HasRole,
    RateLimit,
    RequestContext,
    flow_dependency,
    enrich_openapi,
)

app = FastAPI()

# Define your flow
async def decode_jwt(token: str) -> dict:
    # Your JWT decoding logic
    return {"sub": "user123", "roles": ["admin"]}

admin_flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    HasRole("admin"),
    RateLimit(rate=100, window_seconds=60),
)

# Use as dependency
@app.get("/admin/dashboard")
async def admin_dashboard(
    ctx: RequestContext = Depends(flow_dependency(admin_flow))
):
    return {"user": ctx.user, "message": "Welcome, admin!"}

# Enrich OpenAPI schema
enrich_openapi(app)
```

## Core Concepts

### Flow

A `Flow` is an ordered container of FlowComponent instances that process requests sequentially. FlowComponent instances are automatically sorted by ComponentCategory to ensure proper execution order (pre-auth → authentication → permissions → feature flags → throttling → filters → pagination → custom).

```python
flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    HasPermission("posts:write"),
    RateLimit(rate=100, window_seconds=60),
)
```

### Built-in FlowComponent Classes

Built-in FlowComponent classes:

**Authentication**
- `JWTAuthentication` - Bearer token authentication
- `APIKeyAuthentication` - API key in headers
- `CookieAuthentication` - Session cookies
- `AllowAnonymous` - Skip authentication

**Permissions**
- `Authenticated` - Require authenticated user
- `HasRole` - Role-based access control
- `HasPermission` - Permission-based access control

`HasRole` and `HasPermission` read `roles` / `permissions` from `ctx.user` (dict key or attribute). The value must be a list, tuple, set or frozenset; any other type, including a plain string, is denied.

**Feature Flags**
- `FeatureEnabled` - Require a feature flag to be on, via an async `checker` callback or `ctx.state["features"]`

**Rate Limiting**
- `RateLimit` - Configurable rate limiting with pluggable backends. Keyed by the user's `sub` / `id` when authenticated, otherwise by client IP
- `PreAuthRateLimit` - IP-keyed rate limit that runs *before* authentication, so requests with invalid credentials are counted too (limits credential guessing)
- `InMemoryThrottleBackend` - Default in-memory fixed-window backend (single process; expired keys are evicted periodically)
- Custom backends (e.g., Redis) via `ThrottleBackend` protocol

Throttled requests get a `429` response with a `Retry-After` header.

```python
flow = Flow(
    PreAuthRateLimit(rate=20, window_seconds=60),   # per IP, before auth
    JWTAuthentication(decode=decode_jwt),
    RateLimit(rate=100, window_seconds=60),          # per user, after auth
)
```

**Filters & Pagination**
- `QueryFilter` - Extract selected query parameters into RequestContext.state
- `LimitOffset` - Offset-based pagination

### Flow Composition

Compose flows at different levels with `merge_flows()`:

```python
from fastapi_request_pipeline import merge_flows, OverrideFlow, DisableFlow

# Application-wide defaults
app_flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    RateLimit(rate=1000, window_seconds=3600)
)

# Router-specific additions
admin_flow = Flow(HasRole("admin"))

# Route-specific overrides
public_flow = Flow(OverrideFlow(AllowAnonymous()))

final_flow = merge_flows(app_flow, admin_flow, public_flow)
```

Merge rules:

- **PERMISSION components accumulate.** Checks from every merged flow all apply, so a router flow can never silently drop an app-level `HasRole`.
- **Every other category is last-writer-wins.** A later flow's components for a category replace the earlier flow's components for that category.
- `OverrideFlow(component)` replaces a category (including PERMISSION) and `DisableFlow(category)` removes it.
- Hooks from all merged flows are kept.

`OverrideFlow` and `DisableFlow` are only valid as top-level items of a flow passed to `merge_flows()`. Anywhere else (a plain `Flow` given to `flow_dependency`, or a nested `Flow`) they raise `ValueError`.

### Custom FlowComponent Subclasses

Create custom FlowComponent subclasses by extending the base class:

```python
from fastapi_request_pipeline import FlowComponent, ComponentCategory

class AuditLog(FlowComponent):
    category = ComponentCategory.CUSTOM

    async def resolve(self, ctx: RequestContext) -> None:
        await log_request(ctx.user, ctx.request.url.path)
```

### Logging

The library logs under the `fastapi_request_pipeline` logger. Unexpected errors in components or hooks, which become a generic `500`, are logged at `ERROR` with a traceback. Flow aborts, and exceptions raised by authentication callbacks (`decode`, `lookup`, `validate`), are logged at `DEBUG`.

## Documentation

- **[User Guide](docs/user-guide.md)** - Comprehensive guide with examples
- **[API Reference](docs/api-reference.md)** - Complete API documentation
- **[CI/CD and Release Guide](docs/deployment.md)** - Versioning rules, GitHub Releases, TestPyPI/PyPI publish pipeline
- **[Examples](examples/)** - Working code examples
  - [Basic Usage](examples/01_basic_usage.py)
  - [Authentication](examples/02_authentication.py)
  - [Permissions](examples/03_permissions.py)
  - [Rate Limiting](examples/04_rate_limiting.py)
  - [Flow Composition](examples/05_flow_composition.py)
  - [Custom FlowComponent Subclasses](examples/06_custom_components.py)
  - [Real-World App](examples/07_real_world_app.py)

## Requirements

- Python 3.11+
- FastAPI 0.100+

## Development

```bash
# Install with dev dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run mypy --strict src/
```

## Why Use This Library?

**Instead of this:**

```python
@app.get("/posts")
async def get_posts(request: Request):
    # Authentication
    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        raise HTTPException(401)
    user = decode_jwt(token[7:])

    # Permission check
    if "posts:read" not in user.permissions:
        raise HTTPException(403)

    # Rate limiting
    if not check_rate_limit(user.id):
        raise HTTPException(429)

    # Pagination
    limit = int(request.query_params.get("limit", 20))
    offset = int(request.query_params.get("offset", 0))

    # Business logic
    return get_posts_from_db(limit, offset)
```

**Write this:**

```python
posts_flow = Flow(
    JWTAuthentication(decode=decode_jwt),
    HasPermission("posts:read"),
    RateLimit(rate=100, window_seconds=60),
    LimitOffset(default_limit=20),
)

@app.get("/posts")
async def get_posts(ctx: RequestContext = Depends(flow_dependency(posts_flow))):
    pagination = ctx.state["pagination"]
    return get_posts_from_db(pagination["limit"], pagination["offset"])
```

**Benefits:**

- **Separation of concerns** - Security logic separated from business logic
- **Reusability** - Define flows once, use across multiple endpoints
- **Composability** - Mix and match FlowComponent instances, override at any level
- **Maintainability** - Changes to auth/permissions in one place
- **Type safety** - Full type hints and IDE support
- **Testability** - FlowComponent instances are easy to unit test
- **Documentation** - OpenAPI schema automatically reflects security requirements

## License

MIT
