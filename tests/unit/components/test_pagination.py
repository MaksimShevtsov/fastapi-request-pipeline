"""Tests for LimitOffset component."""

from __future__ import annotations

from typing import Any

import pytest

from fastapi_request_pipeline.component import ComponentCategory
from fastapi_request_pipeline.components.pagination import LimitOffset
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.exceptions import FlowAbort


class TestLimitOffset:
    def test_category_is_pagination(self) -> None:
        assert LimitOffset().category == ComponentCategory.PAGINATION

    async def test_parses_limit_offset(self, make_request: Any) -> None:
        request = make_request(query_string="limit=20&offset=40")
        ctx = RequestContext(request=request)
        await LimitOffset().resolve(ctx)
        assert ctx.state["pagination"] == {"limit": 20, "offset": 40}

    async def test_applies_default_limit(self, make_request: Any) -> None:
        request = make_request(query_string="")
        ctx = RequestContext(request=request)
        await LimitOffset(default_limit=25).resolve(ctx)
        assert ctx.state["pagination"]["limit"] == 25
        assert ctx.state["pagination"]["offset"] == 0

    async def test_caps_at_max_limit(self, make_request: Any) -> None:
        request = make_request(query_string="limit=500")
        ctx = RequestContext(request=request)
        await LimitOffset(max_limit=100).resolve(ctx)
        assert ctx.state["pagination"]["limit"] == 100

    async def test_raises_on_negative_limit(self, make_request: Any) -> None:
        request = make_request(query_string="limit=-1")
        ctx = RequestContext(request=request)
        with pytest.raises(FlowAbort):
            await LimitOffset().resolve(ctx)

    async def test_raises_on_negative_offset(self, make_request: Any) -> None:
        request = make_request(query_string="offset=-5")
        ctx = RequestContext(request=request)
        with pytest.raises(FlowAbort):
            await LimitOffset().resolve(ctx)

    async def test_custom_state_key(self, make_request: Any) -> None:
        request = make_request(query_string="limit=10")
        ctx = RequestContext(request=request)
        await LimitOffset(state_key="page").resolve(ctx)
        assert "page" in ctx.state

    async def test_raises_on_non_numeric_limit(self, make_request: Any) -> None:
        request = make_request(query_string="limit=abc")
        ctx = RequestContext(request=request)
        with pytest.raises(FlowAbort):
            await LimitOffset().resolve(ctx)

    async def test_default_values(self, make_request: Any) -> None:
        request = make_request(query_string="")
        ctx = RequestContext(request=request)
        await LimitOffset().resolve(ctx)
        assert ctx.state["pagination"] == {"limit": 20, "offset": 0}
