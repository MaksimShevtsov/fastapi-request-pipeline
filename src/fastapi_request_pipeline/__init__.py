"""FastAPI Request Pipeline - composable request processing flows for FastAPI."""

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent
from fastapi_request_pipeline.components.authentication import (
    AllowAnonymous,
    APIKeyAuthentication,
    CookieAuthentication,
    JWTAuthentication,
)
from fastapi_request_pipeline.components.features import FeatureEnabled
from fastapi_request_pipeline.components.filters import QueryFilter
from fastapi_request_pipeline.components.pagination import LimitOffset
from fastapi_request_pipeline.components.permissions import (
    Authenticated,
    HasPermission,
    HasRole,
)
from fastapi_request_pipeline.components.throttling import (
    InMemoryThrottleBackend,
    RateLimit,
    ThrottleBackend,
)
from fastapi_request_pipeline.composition import DisableFlow, OverrideFlow, merge_flows
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.dependency import enrich_openapi, flow_dependency
from fastapi_request_pipeline.exceptions import (
    AuthenticationFailed,
    FeatureDisabled,
    FlowAbort,
    FlowException,
    FlowInternalError,
    PermissionDenied,
    Throttled,
)
from fastapi_request_pipeline.flow import Flow
from fastapi_request_pipeline.hooks import (
    AfterComponent,
    AfterFlow,
    BeforeFlow,
    FlowHook,
)
from fastapi_request_pipeline.trace import FlowTrace, TraceEntry

__all__ = [
    "APIKeyAuthentication",
    "AfterComponent",
    "AfterFlow",
    "AllowAnonymous",
    "Authenticated",
    "AuthenticationFailed",
    "BeforeFlow",
    "ComponentCategory",
    "CookieAuthentication",
    "DisableFlow",
    "FeatureDisabled",
    "FeatureEnabled",
    "Flow",
    "FlowAbort",
    "FlowComponent",
    "FlowException",
    "FlowHook",
    "FlowInternalError",
    "FlowTrace",
    "HasPermission",
    "HasRole",
    "InMemoryThrottleBackend",
    "JWTAuthentication",
    "LimitOffset",
    "OverrideFlow",
    "PermissionDenied",
    "QueryFilter",
    "RateLimit",
    "RequestContext",
    "ThrottleBackend",
    "Throttled",
    "TraceEntry",
    "enrich_openapi",
    "flow_dependency",
    "merge_flows",
]
