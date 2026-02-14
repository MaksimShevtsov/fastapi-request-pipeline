"""Performance benchmark for flow execution overhead."""

from __future__ import annotations

import time
from typing import Any

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.dependency import flow_dependency
from fastapi_request_pipeline.flow import Flow


class _AuthComp(FlowComponent):
    category = ComponentCategory.AUTHENTICATION

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.user = {"sub": "user-1"}


class _PermComp(FlowComponent):
    category = ComponentCategory.PERMISSION

    async def resolve(self, ctx: RequestContext) -> None:
        pass


class _ThrottleComp(FlowComponent):
    category = ComponentCategory.THROTTLING

    async def resolve(self, ctx: RequestContext) -> None:
        pass


class _FilterComp(FlowComponent):
    category = ComponentCategory.FILTERS

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.state["filters"] = {}


class _PaginationComp(FlowComponent):
    category = ComponentCategory.PAGINATION

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.state["pagination"] = {"limit": 20, "offset": 0}


class TestPerformance:
    async def test_five_component_flow_overhead_under_500us(
        self, make_request: Any
    ) -> None:
        """Flow overhead < 0.5ms for 5-component flow."""
        flow = Flow(
            _AuthComp(),
            _PermComp(),
            _ThrottleComp(),
            _FilterComp(),
            _PaginationComp(),
            debug=False,
        )
        dep = flow_dependency(flow)

        # Warmup
        for _ in range(10):
            await dep(make_request())

        # Measure
        iterations = 1000
        request = make_request()
        start = time.perf_counter()
        for _ in range(iterations):
            await dep(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        avg_ms = elapsed_ms / iterations
        # Allow generous margin — 0.5ms target per request
        assert avg_ms < 0.5, (
            f"Average flow overhead {avg_ms:.3f}ms exceeds 0.5ms target"
        )
