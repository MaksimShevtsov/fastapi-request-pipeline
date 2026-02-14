"""Contract tests — verify all public symbols are importable from top-level."""

from __future__ import annotations

import fastapi_request_pipeline

# All symbols from contracts/public-api.md
PUBLIC_SYMBOLS = [
    # Core
    "Flow",
    "RequestContext",
    "FlowComponent",
    "ComponentCategory",
    "flow_dependency",
    "merge_flows",
    # Composition directives
    "OverrideFlow",
    "DisableFlow",
    # Exceptions
    "FlowException",
    "FlowAbort",
    "AuthenticationFailed",
    "PermissionDenied",
    "FeatureDisabled",
    "Throttled",
    "FlowInternalError",
    # Trace
    "FlowTrace",
    "TraceEntry",
    # Hooks
    "FlowHook",
    "BeforeFlow",
    "AfterFlow",
    "AfterComponent",
    # Built-in components
    "JWTAuthentication",
    "CookieAuthentication",
    "APIKeyAuthentication",
    "AllowAnonymous",
    "Authenticated",
    "HasPermission",
    "HasRole",
    "FeatureEnabled",
    "RateLimit",
    "QueryFilter",
    "LimitOffset",
    # Throttle backend
    "ThrottleBackend",
    "InMemoryThrottleBackend",
]


class TestPublicAPIContract:
    def test_all_symbols_importable(self) -> None:
        for symbol in PUBLIC_SYMBOLS:
            assert hasattr(fastapi_request_pipeline, symbol), (
                f"Symbol '{symbol}' not found in fastapi_request_pipeline"
            )

    def test_all_symbols_in_all(self) -> None:
        for symbol in PUBLIC_SYMBOLS:
            assert symbol in fastapi_request_pipeline.__all__, (
                f"Symbol '{symbol}' not in __all__"
            )

    def test_flow_has_init_add_resolve(self) -> None:
        from fastapi_request_pipeline import Flow

        assert callable(Flow)
        flow = Flow()
        assert hasattr(flow, "add")
        assert hasattr(flow, "add_hook")
        assert hasattr(flow, "resolve")

    def test_flow_component_is_abstract(self) -> None:
        import pytest

        from fastapi_request_pipeline import FlowComponent

        with pytest.raises(TypeError):
            FlowComponent()  # type: ignore[abstract]

    def test_request_context_is_dataclass(self) -> None:
        from dataclasses import fields

        from fastapi_request_pipeline import RequestContext

        field_names = [f.name for f in fields(RequestContext)]
        assert "request" in field_names
        assert "user" in field_names
        assert "state" in field_names

    def test_flow_dependency_returns_callable(self) -> None:
        from fastapi_request_pipeline import Flow, flow_dependency

        dep = flow_dependency(Flow())
        assert callable(dep)

    def test_merge_flows_returns_flow(self) -> None:
        from fastapi_request_pipeline import Flow, merge_flows

        result = merge_flows(Flow(), Flow())
        assert isinstance(result, Flow)

    def test_exception_hierarchy(self) -> None:
        from fastapi_request_pipeline import (
            AuthenticationFailed,
            FeatureDisabled,
            FlowAbort,
            FlowException,
            FlowInternalError,
            PermissionDenied,
            Throttled,
        )

        assert issubclass(FlowAbort, FlowException)
        assert issubclass(AuthenticationFailed, FlowAbort)
        assert issubclass(PermissionDenied, FlowAbort)
        assert issubclass(FeatureDisabled, FlowAbort)
        assert issubclass(Throttled, FlowAbort)
        assert issubclass(FlowInternalError, FlowException)
        assert not issubclass(FlowInternalError, FlowAbort)

    def test_component_category_has_seven_members(self) -> None:
        from fastapi_request_pipeline import ComponentCategory

        assert len(list(ComponentCategory)) == 7

    def test_trace_entry_is_frozen(self) -> None:
        from fastapi_request_pipeline import ComponentCategory, TraceEntry

        entry = TraceEntry(
            component_name="Test",
            category=ComponentCategory.CUSTOM,
            duration_ms=0.0,
            outcome="OK",
        )
        import pytest

        with pytest.raises(AttributeError):
            entry.component_name = "other"  # type: ignore[misc]
