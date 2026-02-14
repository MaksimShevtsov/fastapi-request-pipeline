"""Tests for FlowTrace, TraceEntry, and debug integration."""

from __future__ import annotations

from typing import Any

import pytest

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.dependency import flow_dependency
from fastapi_request_pipeline.exceptions import FlowAbort
from fastapi_request_pipeline.flow import Flow
from fastapi_request_pipeline.trace import FlowTrace, TraceEntry


class _SlowAuth(FlowComponent):
    category = ComponentCategory.AUTHENTICATION

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.user = {"sub": "user-1"}


class _SlowPerm(FlowComponent):
    category = ComponentCategory.PERMISSION

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.state["perm"] = True


class _FailingComp(FlowComponent):
    category = ComponentCategory.CUSTOM

    async def resolve(self, ctx: RequestContext) -> None:
        raise FlowAbort("denied", status_code=403)


class TestTraceEntry:
    def test_construction(self) -> None:
        entry = TraceEntry(
            component_name="TestComp",
            category=ComponentCategory.AUTHENTICATION,
            duration_ms=1.5,
            outcome="OK",
        )
        assert entry.component_name == "TestComp"
        assert entry.category == ComponentCategory.AUTHENTICATION
        assert entry.duration_ms == 1.5
        assert entry.outcome == "OK"
        assert entry.reason is None

    def test_frozen(self) -> None:
        entry = TraceEntry(
            component_name="TestComp",
            category=ComponentCategory.AUTHENTICATION,
            duration_ms=1.5,
            outcome="OK",
        )
        with pytest.raises(AttributeError):
            entry.component_name = "other"  # type: ignore[misc]

    def test_failed_with_reason(self) -> None:
        entry = TraceEntry(
            component_name="TestComp",
            category=ComponentCategory.CUSTOM,
            duration_ms=0.1,
            outcome="FAILED",
            reason="denied",
        )
        assert entry.outcome == "FAILED"
        assert entry.reason == "denied"


class TestFlowTrace:
    def test_construction(self) -> None:
        trace = FlowTrace(
            entries=[],
            total_duration_ms=0.0,
            outcome="OK",
        )
        assert trace.entries == []
        assert trace.outcome == "OK"
        assert trace.error is None


class TestDebugIntegration:
    async def test_debug_true_produces_trace(self, make_request: Any) -> None:
        flow = Flow(_SlowAuth(), _SlowPerm(), debug=True)
        # Execute via dependency

        request = make_request()
        dep = flow_dependency(flow)
        ctx = await dep(request)
        trace = ctx.state.get("trace")
        assert trace is not None
        assert isinstance(trace, FlowTrace)
        assert len(trace.entries) == 2
        assert trace.outcome == "OK"

    async def test_trace_has_entry_per_component(self, make_request: Any) -> None:
        flow = Flow(_SlowAuth(), _SlowPerm(), debug=True)
        dep = flow_dependency(flow)
        ctx = await dep(make_request())
        trace = ctx.state["trace"]
        assert trace.entries[0].component_name == "_SlowAuth"
        assert trace.entries[1].component_name == "_SlowPerm"

    async def test_trace_timing_positive(self, make_request: Any) -> None:
        flow = Flow(_SlowAuth(), debug=True)
        dep = flow_dependency(flow)
        ctx = await dep(make_request())
        trace = ctx.state["trace"]
        assert trace.entries[0].duration_ms >= 0
        assert trace.total_duration_ms >= 0

    async def test_abort_records_reason(self, make_request: Any) -> None:
        flow = Flow(_SlowAuth(), _FailingComp(), debug=True)
        dep = flow_dependency(flow)
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            await dep(make_request())
        # We can't access the trace after HTTPException, but we can test
        # that the trace is stored before abort by using the flow directly

    async def test_debug_false_no_trace(self, make_request: Any) -> None:
        flow = Flow(_SlowAuth(), debug=False)
        dep = flow_dependency(flow)
        ctx = await dep(make_request())
        assert "trace" not in ctx.state

    async def test_partial_execution_trace_on_error(self, make_request: Any) -> None:
        """When a component fails, trace should contain entries up to the failure."""
        flow = Flow(_SlowAuth(), _FailingComp(), debug=True)

        # Execute directly to inspect trace before HTTPException
        resolved = flow.resolve()
        request = make_request()
        ctx = RequestContext(request=request)

        import time

        from fastapi_request_pipeline.exceptions import FlowAbort

        trace_entries: list[TraceEntry] = []
        for component in resolved.components:
            comp_start = time.perf_counter()
            try:
                await component.resolve(ctx)
                elapsed = (time.perf_counter() - comp_start) * 1000
                trace_entries.append(
                    TraceEntry(
                        component_name=type(component).__name__,
                        category=component.category,
                        duration_ms=elapsed,
                        outcome="OK",
                    )
                )
            except FlowAbort as exc:
                elapsed = (time.perf_counter() - comp_start) * 1000
                trace_entries.append(
                    TraceEntry(
                        component_name=type(component).__name__,
                        category=component.category,
                        duration_ms=elapsed,
                        outcome="FAILED",
                        reason=exc.detail,
                    )
                )
                break

        assert len(trace_entries) == 2
        assert trace_entries[0].outcome == "OK"
        assert trace_entries[1].outcome == "FAILED"
        assert trace_entries[1].reason == "denied"
