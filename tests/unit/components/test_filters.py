"""Tests for QueryFilter component."""

from __future__ import annotations

from typing import Any

from fastapi_request_pipeline.component import ComponentCategory
from fastapi_request_pipeline.components.filters import QueryFilter
from fastapi_request_pipeline.context import RequestContext


class TestQueryFilter:
    def test_category_is_filters(self) -> None:
        assert QueryFilter("status").category == ComponentCategory.FILTERS

    async def test_parses_specified_query_params(self, make_request: Any) -> None:
        request = make_request(query_string="status=active&priority=high")
        ctx = RequestContext(request=request)
        await QueryFilter("status", "priority").resolve(ctx)
        assert ctx.state["filters"] == {"status": "active", "priority": "high"}

    async def test_ignores_unspecified_params(self, make_request: Any) -> None:
        request = make_request(query_string="status=active&unknown=val")
        ctx = RequestContext(request=request)
        await QueryFilter("status").resolve(ctx)
        assert ctx.state["filters"] == {"status": "active"}
        assert "unknown" not in ctx.state["filters"]

    async def test_handles_missing_params_gracefully(self, make_request: Any) -> None:
        request = make_request(query_string="")
        ctx = RequestContext(request=request)
        await QueryFilter("status", "priority").resolve(ctx)
        assert ctx.state["filters"] == {}

    async def test_custom_state_key(self, make_request: Any) -> None:
        request = make_request(query_string="status=active")
        ctx = RequestContext(request=request)
        await QueryFilter("status", state_key="my_filters").resolve(ctx)
        assert ctx.state["my_filters"] == {"status": "active"}

    async def test_partial_params_present(self, make_request: Any) -> None:
        request = make_request(query_string="status=active")
        ctx = RequestContext(request=request)
        await QueryFilter("status", "priority").resolve(ctx)
        assert ctx.state["filters"] == {"status": "active"}
