# Glossary

Core concepts and canonical terms used throughout the fastapi-request-pipeline documentation. Each term has exactly one meaning; no synonyms are used.

## Core Abstractions

### Flow

An ordered container of FlowComponent instances that processes requests sequentially. Components within a Flow are automatically sorted by ComponentCategory to ensure a deterministic execution order: authentication, then permissions, then feature flags, then throttling, then filters, then pagination, then custom logic.

### FlowComponent

The base class for all processing units in a Flow. Each FlowComponent belongs to a ComponentCategory and implements an async `resolve` method that receives a RequestContext. FlowComponent instances can modify the RequestContext or raise exceptions to abort the Flow.

### RequestContext

A per-request data container passed through the Flow during execution. RequestContext holds the Starlette `Request` object, an optional `user` field populated by authentication components, and a `state` dictionary for arbitrary key-value storage between components.

### ComponentCategory

An enumeration that defines the execution order of FlowComponent instances within a Flow. The categories, in order, are: AUTHENTICATION, PERMISSION, FEATURE, THROTTLING, FILTERS, PAGINATION, and CUSTOM.

### ResolvedFlow

An immutable execution plan produced by calling `Flow.resolve()`. ResolvedFlow contains the final sorted list of components and hooks, ready for per-request execution. Created automatically by `flow_dependency()`.

## Authentication Components

### JWTAuthentication

A FlowComponent that extracts a Bearer token from the Authorization header and decodes the token using a caller-supplied async callback. Sets `RequestContext.user` to the decoded result.

### CookieAuthentication

A FlowComponent that extracts a session cookie and looks up the user via a caller-supplied async callback. Sets `RequestContext.user` to the lookup result.

### APIKeyAuthentication

A FlowComponent that extracts an API key from a request header and validates the key via a caller-supplied async callback. Sets `RequestContext.user` to the validation result.

### AllowAnonymous

A no-op authentication FlowComponent. Use AllowAnonymous with OverrideFlow to replace an existing authentication requirement and allow unauthenticated access.

## Permission Components

### Authenticated

A FlowComponent that requires `RequestContext.user` to be non-None. Raises PermissionDenied if no user is present.

### HasRole

A FlowComponent that checks whether the authenticated user has a specific role. Expects the user object to have a `roles` attribute or dictionary key containing a collection of role names.

### HasPermission

A FlowComponent that checks whether the authenticated user has a specific permission. Expects the user object to have a `permissions` attribute or dictionary key containing a collection of permission names.

## Feature Components

### FeatureEnabled

A FlowComponent that checks whether a named feature flag is enabled. Accepts an optional async checker callback; when the checker is omitted, FeatureEnabled reads from `RequestContext.state["features"]`.

## Throttling Components

### RateLimit

A FlowComponent that enforces request rate limits using a pluggable ThrottleBackend. RateLimit tracks requests per key (user ID or IP address by default) within a configurable time window.

### ThrottleBackend

A protocol (interface) for rate limit storage backends. ThrottleBackend defines `increment` and `reset` methods. Implement ThrottleBackend to use external stores such as Redis for distributed rate limiting.

### InMemoryThrottleBackend

The default ThrottleBackend implementation that stores rate limit counters in process memory. InMemoryThrottleBackend is suitable for development and single-process deployments but not for multi-worker production environments.

## Filter and Pagination Components

### QueryFilter

A FlowComponent that extracts specified query string parameters from the request and stores them in `RequestContext.state` under a configurable key (default: `"filters"`).

### LimitOffset

A FlowComponent that parses `limit` and `offset` query parameters for offset-based pagination. LimitOffset stores the parsed values in `RequestContext.state` under a configurable key (default: `"pagination"`).

## Composition

### merge_flows

A function that merges multiple Flow instances using last-writer-wins resolution by ComponentCategory. Later flows' component groups replace earlier flows' groups for the same category. OverrideFlow and DisableFlow directives are processed during the merge.

### OverrideFlow

A composition directive that replaces all FlowComponent instances of a given ComponentCategory when used inside `merge_flows`. Wrap a FlowComponent in OverrideFlow to substitute an entire category.

### DisableFlow

A composition directive that removes all FlowComponent instances of a given ComponentCategory when used inside `merge_flows`. Pass a ComponentCategory to DisableFlow to eliminate that category from the merged result.

## Dependency Integration

### flow_dependency

A function that converts a Flow into a FastAPI-compatible async dependency. Use `flow_dependency` with `Depends()` to execute a Flow as part of FastAPI's dependency injection.

### enrich_openapi

A function that enriches a FastAPI application's OpenAPI schema with metadata derived from Flow components. Call `enrich_openapi` after all routes are registered to inject security schemes, error responses, rate limit headers, and query parameters.

## Hooks

### FlowHook

The base class for flow execution observers. FlowHook defines three lifecycle methods: `on_flow_start`, `on_component`, and `on_flow_end`. Subclass FlowHook to implement custom monitoring, logging, or metrics collection.

### BeforeFlow

A convenience FlowHook that only implements `on_flow_start`. Pass an async callback to BeforeFlow to run logic before Flow execution begins.

### AfterFlow

A convenience FlowHook that only implements `on_flow_end`. Pass an async callback to AfterFlow to run logic after Flow execution completes.

### AfterComponent

A convenience FlowHook that only implements `on_component`. Pass an async callback to AfterComponent to run logic after each FlowComponent executes.

## Exceptions

### FlowException

The base exception class for all flow-related errors.

### FlowAbort

A FlowException subclass for controlled request aborts that translate to HTTP error responses. All built-in abort exceptions (AuthenticationFailed, PermissionDenied, FeatureDisabled, Throttled) inherit from FlowAbort.

### AuthenticationFailed

A FlowAbort that signals authentication failure. Returns HTTP 401.

### PermissionDenied

A FlowAbort that signals insufficient permissions. Returns HTTP 403.

### FeatureDisabled

A FlowAbort that signals a disabled feature flag. Returns HTTP 403.

### Throttled

A FlowAbort that signals a rate limit has been exceeded. Returns HTTP 429. Includes an optional `retry_after` value indicating seconds until the limit resets.

### FlowInternalError

A FlowException subclass for unexpected internal errors during Flow execution. Returns HTTP 500. Wraps the original exception in its `cause` attribute.

## Tracing

### FlowTrace

A dataclass that records the execution trace of a Flow when debug mode is enabled. FlowTrace contains a list of TraceEntry records, the total duration in milliseconds, the outcome (`"OK"`, `"ABORTED"`, or `"ERROR"`), and any exception that occurred.

### TraceEntry

A dataclass that records an individual FlowComponent's execution within a FlowTrace. TraceEntry includes the component name, ComponentCategory, duration in milliseconds, outcome (`"OK"` or `"FAILED"`), and an optional failure reason.
