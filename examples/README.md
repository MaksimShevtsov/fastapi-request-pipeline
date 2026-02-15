# Examples

This directory contains practical examples demonstrating various features of `fastapi-request-pipeline`.

## Running Examples

Each example is a standalone FastAPI application. To run:

```bash
# Install the library with dev dependencies
uv sync --extra dev

# Run an example
uv run python examples/01_basic_usage.py
```

> **Note:** These examples cannot be run with `uvicorn examples.01_basic_usage:app` because Python module names cannot start with digits. Each example includes a `__main__` block that runs uvicorn with appropriate settings when executed directly.

## Example Files

### 01_basic_usage.py

**Basic usage pattern**

- Creating a simple flow with JWT authentication
- Using flow as a FastAPI dependency
- Accessing user context in endpoints
- Public vs protected endpoints

**Run:**
```bash
python examples/01_basic_usage.py
```

**Test:**
```bash
curl http://localhost:8000/
curl -H "Authorization: Bearer valid-token" http://localhost:8000/protected
```

---

### 02_authentication.py

**Different authentication strategies**

- JWT authentication with Bearer tokens
- API Key authentication
- Cookie-based authentication
- Anonymous access with `OverrideFlow`
- Custom authentication headers

**Run:**
```bash
python examples/02_authentication.py
```

**Test:**
```bash
# JWT
curl -H "Authorization: Bearer jwt-token" http://localhost:8000/jwt

# API Key
curl -H "X-API-Key: secret-api-key" http://localhost:8000/api-key

# Cookie
curl -H "Cookie: session_id=valid-session" http://localhost:8000/cookie

# Public with override
curl http://localhost:8000/public
```

---

### 03_permissions.py

**Authorization and permissions**

- Requiring authenticated users
- Role-based access control (RBAC)
- Permission-based access control
- Combining authentication with authorization

**Run:**
```bash
python examples/03_permissions.py
```

**Test:**
```bash
# Admin-only endpoint
curl -H "Authorization: Bearer admin-token" http://localhost:8000/admin

# Permission-based
curl -X POST -H "Authorization: Bearer user-token" http://localhost:8000/posts
curl -X DELETE -H "Authorization: Bearer admin-token" http://localhost:8000/posts/1
```

---

### 04_rate_limiting.py

**Rate limiting patterns**

- Basic IP-based rate limiting
- Per-user rate limiting
- Custom rate limit keys
- Different limits for different endpoints
- Tier-based rate limiting

**Run:**
```bash
python examples/04_rate_limiting.py
```

**Test:**
```bash
# Hit rate limit
for i in {1..15}; do curl http://localhost:8000/public; done

# Authenticated rate limit
for i in {1..105}; do
  curl -H "Authorization: Bearer free-token" http://localhost:8000/api/data
done
```

---

### 05_flow_composition.py

**Composing flows at different levels**

- Application-level base flows
- Router-level flow customization
- Route-level flow overrides
- Using `merge_flows()` for composition
- `OverrideFlow` and `DisableFlow` directives

**Run:**
```bash
python examples/05_flow_composition.py
```

**Test:**
```bash
# Admin endpoints
curl -H "Authorization: Bearer admin-token" http://localhost:8000/admin/dashboard

# Public override
curl http://localhost:8000/public/health

# Custom rate limit
curl -X POST -H "Authorization: Bearer user-token" http://localhost:8000/upload
```

---

### 06_custom_components.py

**Creating custom components**

- Audit logging component
- Request ID tracking
- Tenant isolation for multi-tenant apps
- IP whitelisting
- Usage tracking and metrics
- Implementing the `FlowComponent` interface

**Run:**
```bash
python examples/06_custom_components.py
```

**Test:**
```bash
# Request ID
curl -H "Authorization: Bearer valid-token" http://localhost:8000/with-request-id
curl -H "Authorization: Bearer valid-token" -H "X-Request-ID: custom-123" \
  http://localhost:8000/with-request-id

# Tenant isolation
curl -H "Authorization: Bearer valid-token" http://localhost:8000/tenant-data
```

---

### 07_real_world_app.py

**Complete blog API application**

Demonstrates a real-world application with:
- Multiple routers (public, authenticated, admin)
- Different authentication requirements per router
- Pagination and filtering
- RBAC and permission checks
- Rate limiting at multiple levels
- Custom components for caching

**Run:**
```bash
python examples/07_real_world_app.py
```

**Test:**
```bash
# Public posts (no auth)
curl http://localhost:8000/public/posts
curl http://localhost:8000/public/posts?limit=5

# Authenticated posts (with drafts)
curl -H "Authorization: Bearer author" http://localhost:8000/posts/
curl -H "Authorization: Bearer author" "http://localhost:8000/posts/?status=draft"

# Create post
curl -X POST -H "Authorization: Bearer author" \
  "http://localhost:8000/posts/?title=New Post&content=Great content"

# Admin stats
curl -H "Authorization: Bearer admin" http://localhost:8000/admin/stats

# User profile
curl -H "Authorization: Bearer author" http://localhost:8000/me/
```

---

## Common Test Tokens

Most examples use these mock tokens:

- `admin-token` - Admin user with full permissions
- `user-token` - Regular user with read/write permissions
- `readonly-token` - User with read-only permissions
- `valid-token` - Generic valid authentication token
- `jwt-token` - JWT authentication example
- `secret-api-key` - API key example
- `valid-session` - Cookie session example

## OpenAPI Documentation

All examples include OpenAPI documentation. After starting an example, visit:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

The `enrich_openapi()` function automatically adds security schemes, required permissions, rate limits, and other flow metadata to the documentation.

## Production Considerations

These examples use simplified mock implementations for clarity. In production:

1. **JWT Decoding**: Use libraries like `python-jose` or `PyJWT`
2. **Rate Limiting**: Use Redis-backed throttle backend for distributed systems
3. **Database**: Replace mock data with real database queries
4. **Secrets**: Use environment variables for secrets
5. **Error Handling**: Add proper error handlers
6. **Logging**: Use structured logging services
7. **Monitoring**: Add metrics and tracing

## Next Steps

After exploring the examples:

1. Read the [User Guide](../docs/user-guide.md) for comprehensive documentation
2. Check the [API Reference](../docs/api-reference.md) for detailed API docs
3. Look at the test suite in `tests/` for more usage patterns
4. Build your own custom components for your specific use cases
