# API Reference

## Core Classes

### Flow

```python
class Flow:
    def __init__(
        self,
        *components: FlowComponent | Flow | OverrideFlow | DisableFlow,
        debug: bool = False,
    ) -> None
```

An ordered container of `FlowComponent` instances that processes requests sequentially.

**Parameters:**
- `*components`: Variable number of components, flows, or composition directives
- `debug`: Enable debug mode with detailed execution traces

**Methods:**

#### add

```python
def add(
    self, *components: FlowComponent | Flow | OverrideFlow | DisableFlow
) -> Flow
```

Add components to the Flow. Returns self for chaining.

#### add_hook

```python
def add_hook(self, hook: FlowHook) -> Flow
```

Add a FlowHook to observe Flow execution. Returns self for chaining.

#### resolve

```python
def resolve(self) -> ResolvedFlow
```

Resolve the Flow into an immutable execution plan (ResolvedFlow). Called automatically by `flow_dependency()`.

---

### FlowComponent

```python
class FlowComponent(ABC):
    category: ClassVar[ComponentCategory]

    @abstractmethod
    async def resolve(self, ctx: RequestContext) -> None: ...

    def openapi_spec(self) -> dict[str, Any] | None:
        return None
```

Base class for all processing units in a Flow.

**Class Attributes:**
- `category`: The component category (determines execution order)

**Methods:**

#### resolve

```python
async def resolve(self, ctx: RequestContext) -> None
```

Process the RequestContext. The `resolve` method can modify `ctx.user` or `ctx.state`, or raise exceptions to abort the Flow.

#### openapi_spec

```python
def openapi_spec(self) -> dict[str, Any] | None
```

Return OpenAPI metadata for the FlowComponent (security schemes, responses, etc.).

---

### RequestContext

```python
@dataclass
class RequestContext:
    request: Request
    user: Any | None = None
    state: dict[str, Any] = field(default_factory=dict)
```

Per-request data container passed through the Flow.

**Attributes:**
- `request`: Starlette `Request` object
- `user`: User object populated by authentication components
- `state`: Dictionary for arbitrary data storage between components

---

### ComponentCategory

```python
class ComponentCategory(Enum):
    AUTHENTICATION = "authentication"  # order: 1
    PERMISSION = "permission"          # order: 2
    FEATURE = "feature"                # order: 3
    THROTTLING = "throttling"          # order: 4
    FILTERS = "filters"                # order: 5
    PAGINATION = "pagination"          # order: 6
    CUSTOM = "custom"                  # order: 7
```

Enumeration that defines the execution order of FlowComponent instances within a Flow.

---

## Authentication Components

### JWTAuthentication

```python
class JWTAuthentication(FlowComponent):
    def __init__(
        self,
        decode: Callable[[str], Awaitable[Any]],
        *,
        scheme: str = "Bearer",
        header: str = "Authorization",
    ) -> None
```

Extracts Bearer token from Authorization header and decodes via callback.

**Parameters:**
- `decode`: Async function that decodes JWT token and returns user object
- `scheme`: Authentication scheme (default: "Bearer")
- `header`: Header name (default: "Authorization")

**Raises:**
- `AuthenticationFailed` (401) if header missing, malformed, or decode fails

---

### CookieAuthentication

```python
class CookieAuthentication(FlowComponent):
    def __init__(
        self,
        lookup: Callable[[str], Awaitable[Any]],
        *,
        cookie_name: str = "session",
    ) -> None
```

Extracts session cookie and looks up user via callback.

**Parameters:**
- `lookup`: Async function that looks up user by session ID
- `cookie_name`: Cookie name (default: "session")

**Raises:**
- `AuthenticationFailed` (401) if cookie missing or lookup fails

---

### APIKeyAuthentication

```python
class APIKeyAuthentication(FlowComponent):
    def __init__(
        self,
        validate: Callable[[str], Awaitable[Any]],
        *,
        header: str = "X-API-Key",
    ) -> None
```

Extracts API key from header and validates via callback.

**Parameters:**
- `validate`: Async function that validates API key and returns user object
- `header`: Header name (default: "X-API-Key")

**Raises:**
- `AuthenticationFailed` (401) if header missing or validation fails

---

### AllowAnonymous

```python
class AllowAnonymous(FlowComponent):
    async def resolve(self, ctx: RequestContext) -> None
```

No-op authentication component. Use with `OverrideFlow` to allow unauthenticated access.

---

## Permission Components

### Authenticated

```python
class Authenticated(FlowComponent):
    async def resolve(self, ctx: RequestContext) -> None
```

Requires `ctx.user` to be non-None.

**Raises:**
- `PermissionDenied` (403) if user is None

---

### HasRole

```python
class HasRole(FlowComponent):
    def __init__(self, role: str) -> None
```

Checks whether the authenticated user has a specific role.

Expects the user object (from `ctx.user`) to have a `roles` attribute or dict key containing a list/collection of role names.

**Parameters:**
- `role`: Role name to check

**Raises:**
- `PermissionDenied` (403) if user missing or role not in user `roles`

**Example user object:**
```python
{"sub": "user123", "roles": ["admin", "user"]}
```

---

### HasPermission

```python
class HasPermission(FlowComponent):
    def __init__(self, permission: str) -> None
```

Checks whether the authenticated user has a specific permission.

Expects the user object (from `ctx.user`) to have a `permissions` attribute or dict key containing a list/collection of permission names.

**Parameters:**
- `permission`: Permission name to check

**Raises:**
- `PermissionDenied` (403) if user missing or permission not in collection

**Example user object:**
```python
{"sub": "user123", "permissions": ["read", "write", "delete"]}
```

---

## Throttling Components

### RateLimit

```python
class RateLimit(FlowComponent):
    def __init__(
        self,
        rate: int,
        window_seconds: int = 60,
        *,
        key_func: Callable[[RequestContext], str] | None = None,
        backend: ThrottleBackend | None = None,
    ) -> None
```

Enforces rate limits with pluggable backend.

**Parameters:**
- `rate`: Maximum requests allowed per window
- `window_seconds`: Time window in seconds (default: 60)
- `key_func`: Function to generate rate limit key (default: IP or user ID)
- `backend`: Storage backend (default: `InMemoryThrottleBackend`)

**Raises:**
- `Throttled` (429) if rate limit exceeded
- `ValueError` if rate or window_seconds <= 0

**Default key function:**
```python
def default_key_func(ctx: RequestContext) -> str:
    if ctx.user is not None:
        return f"user:{ctx.user}"
    if ctx.request.client:
        return f"ip:{ctx.request.client.host}"
    forwarded = ctx.request.headers.get("x-forwarded-for")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    return "ip:unknown"
```

---

### ThrottleBackend

```python
@runtime_checkable
class ThrottleBackend(Protocol):
    async def increment(self, key: str, window_seconds: int) -> tuple[int, int]: ...
    async def reset(self, key: str) -> None: ...
```

Protocol (interface) for rate limit storage backends.

**Methods:**

#### increment

```python
async def increment(self, key: str, window_seconds: int) -> tuple[int, int]
```

Increment counter for key. Returns `(current_count, remaining_ttl_seconds)`.

#### reset

```python
async def reset(self, key: str) -> None
```

Reset counter for key.

---

### InMemoryThrottleBackend

```python
class InMemoryThrottleBackend:
    async def increment(self, key: str, window_seconds: int) -> tuple[int, int]
    async def reset(self, key: str) -> None
```

Default in-memory ThrottleBackend implementation. Suitable for development and single-process deployments but not for multi-worker production environments.

---

## Feature Components

### FeatureEnabled

```python
class FeatureEnabled(FlowComponent):
    def __init__(
        self,
        feature: str,
        checker: Callable[[str], Awaitable[bool]] | None = None,
    ) -> None
```

Checks whether a named feature flag is enabled.

**Parameters:**
- `feature`: Feature flag name
- `checker`: Optional async callback to check feature by name; when omitted, reads `ctx.state["features"]`

**Raises:**
- `FeatureDisabled` (403) if feature is disabled

---

## Filter Components

### QueryFilter

```python
class QueryFilter(FlowComponent):
    def __init__(
        self,
        *fields: str,
        *,
        state_key: str = "filters",
    ) -> None
```

Extracts selected query string parameters into `ctx.state[state_key]`.

**Parameters:**
- `*fields`: Query parameter names to extract
- `state_key`: Context state key for extracted filters (default: `"filters"`)

**Query format:**
- `?status=open&priority=high`

**Result in ctx.state:**
```python
ctx.state["filters"] = {
    "status": "open",
    "priority": "high",
}
```

---

## Pagination Components

### LimitOffset

```python
class LimitOffset(FlowComponent):
    def __init__(
        self,
        *,
        max_limit: int = 100,
        default_limit: int = 20,
        state_key: str = "pagination",
    ) -> None
```

Parses limit/offset pagination parameters.

**Parameters:**
- `max_limit`: Maximum allowed limit (default: 100)
- `default_limit`: Default limit if not specified (default: 20)
- `state_key`: Context state key for parsed values (default: `"pagination"`)

**Query format:**
- `?limit=50&offset=100`

**Result in ctx.state:**
```python
ctx.state["pagination"] = {"limit": 50, "offset": 100}
```

---

## Composition Functions

### merge_flows

```python
def merge_flows(*flows: Flow) -> Flow
```

Merge multiple flows with last-writer-wins by category.

Later flows' component groups replace earlier flows' groups for the same `ComponentCategory`. `OverrideFlow` and `DisableFlow` directives are processed during merge.

**Parameters:**
- `*flows`: Variable number of flows to merge

**Returns:**
- New `Flow` instance with merged components

---

### OverrideFlow

```python
class OverrideFlow:
    def __init__(self, component: FlowComponent) -> None
```

Composition directive that replaces all components of a given category.

**Parameters:**
- `component`: Component to use as replacement

---

### DisableFlow

```python
class DisableFlow:
    def __init__(self, category: ComponentCategory) -> None
```

Composition directive that removes all components of a given category.

**Parameters:**
- `category`: Category to disable

---

## Dependency Functions

### flow_dependency

```python
def flow_dependency(flow: Flow) -> Callable[..., Awaitable[RequestContext]]
```

Return a FastAPI-compatible async dependency that executes the Flow.

**Parameters:**
- `flow`: Flow to execute

**Returns:**
- Async dependency function compatible with `Depends()`

**Usage:**
```python
@app.get("/endpoint")
async def endpoint(ctx: RequestContext = Depends(flow_dependency(flow))):
    return {"user": ctx.user}
```

---

### enrich_openapi

```python
def enrich_openapi(app: FastAPI) -> None
```

Enrich a FastAPI application's OpenAPI schema with metadata derived from Flow components.

Call this after all routes are registered to inject security schemes, responses, parameters, and extensions from flow components.

**Parameters:**
- `app`: FastAPI application instance

---

## Hooks

### FlowHook

```python
class FlowHook(ABC):
    async def on_flow_start(self, ctx: RequestContext) -> None: ...
    async def on_component(
        self,
        ctx: RequestContext,
        component: FlowComponent,
        error: Exception | None
    ) -> None: ...
    async def on_flow_end(self, ctx: RequestContext) -> None: ...
```

Base class for Flow execution observers.

**Methods:**

#### on_flow_start

```python
async def on_flow_start(self, ctx: RequestContext) -> None
```

Called before Flow execution starts.

#### on_component

```python
async def on_component(
    self,
    ctx: RequestContext,
    component: FlowComponent,
    error: Exception | None
) -> None
```

Called after each FlowComponent executes. The `error` parameter is None on success.

#### on_flow_end

```python
async def on_flow_end(self, ctx: RequestContext) -> None
```

Called after Flow execution completes (success or failure).

---

### BeforeFlow

```python
class BeforeFlow(FlowHook):
    def __init__(self, callback: Callable[[RequestContext], Awaitable[None]]) -> None
```

Convenience hook that only implements `on_flow_start`.

---

### AfterFlow

```python
class AfterFlow(FlowHook):
    def __init__(self, callback: Callable[[RequestContext], Awaitable[None]]) -> None
```

Convenience hook that only implements `on_flow_end`.

---

### AfterComponent

```python
class AfterComponent(FlowHook):
    def __init__(
        self,
        callback: Callable[[RequestContext, FlowComponent, Exception | None], Awaitable[None]]
    ) -> None
```

Convenience hook that only implements `on_component`.

---

## Exceptions

### FlowException

```python
class FlowException(Exception):
    pass
```

Base exception class for all Flow-related errors.

---

### FlowAbort

```python
class FlowAbort(FlowException):
    def __init__(self, detail: str, *, status_code: int = 400) -> None
```

Base class for exceptions that abort the Flow and return an HTTP error response.

**Attributes:**
- `status_code`: HTTP status code
- `detail`: Error message

---

### AuthenticationFailed

```python
class AuthenticationFailed(FlowAbort):
    def __init__(self, detail: str = "Authentication failed") -> None
```

Authentication failed (HTTP 401).

---

### PermissionDenied

```python
class PermissionDenied(FlowAbort):
    def __init__(self, detail: str = "Permission denied") -> None
```

Permission denied (HTTP 403).

---

### FeatureDisabled

```python
class FeatureDisabled(FlowAbort):
    def __init__(self, detail: str = "Feature disabled") -> None
```

Feature is disabled (HTTP 403).

---

### Throttled

```python
class Throttled(FlowAbort):
    def __init__(
        self,
        detail: str = "Rate limit exceeded",
        *,
        retry_after: int | None = None,
    ) -> None
```

Rate limit exceeded (HTTP 429).

**Attributes:**
- `retry_after`: Seconds until rate limit resets

---

### FlowInternalError

```python
class FlowInternalError(FlowException):
    def __init__(self, detail: str, cause: Exception | None = None) -> None
```

Internal Flow error (HTTP 500).

**Attributes:**
- `detail`: Error message
- `cause`: Original exception

---

## Tracing

### FlowTrace

```python
@dataclass
class FlowTrace:
    entries: list[TraceEntry] = field(default_factory=list)
    total_duration_ms: float = 0.0
    outcome: str = "OK"  # "OK" | "ABORTED" | "ERROR"
    error: Exception | None = None
```

Dataclass that records the execution trace of a Flow when debug mode is enabled.

**Access:**
```python
trace = ctx.state.get("trace")
```

---

### TraceEntry

```python
@dataclass
class TraceEntry:
    component_name: str
    category: ComponentCategory
    duration_ms: float
    outcome: str  # "OK" | "FAILED"
    reason: str | None = None
```

Dataclass that records an individual FlowComponent's execution within a FlowTrace.
