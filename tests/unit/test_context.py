"""Tests for RequestContext dataclass."""

from __future__ import annotations

from typing import Any

from fastapi_request_pipeline.context import RequestContext


class TestRequestContext:
    def test_construction_with_request(self, make_request: Any) -> None:
        request = make_request()
        ctx = RequestContext(request=request)
        assert ctx.request is request

    def test_default_user_is_none(self, make_request: Any) -> None:
        ctx = RequestContext(request=make_request())
        assert ctx.user is None

    def test_default_state_is_empty_dict(self, make_request: Any) -> None:
        ctx = RequestContext(request=make_request())
        assert ctx.state == {}
        assert isinstance(ctx.state, dict)

    def test_user_can_be_set(self, make_request: Any) -> None:
        ctx = RequestContext(request=make_request())
        ctx.user = {"id": "user-1"}
        assert ctx.user == {"id": "user-1"}

    def test_state_is_mutable(self, make_request: Any) -> None:
        ctx = RequestContext(request=make_request())
        ctx.state["key"] = "value"
        assert ctx.state["key"] == "value"

    def test_state_not_shared_between_instances(self, make_request: Any) -> None:
        ctx1 = RequestContext(request=make_request())
        ctx2 = RequestContext(request=make_request())
        ctx1.state["x"] = 1
        assert "x" not in ctx2.state

    def test_construction_with_explicit_user(self, make_request: Any) -> None:
        user = {"id": "user-1"}
        ctx = RequestContext(request=make_request(), user=user)
        assert ctx.user is user

    def test_construction_with_explicit_state(self, make_request: Any) -> None:
        state = {"preloaded": True}
        ctx = RequestContext(request=make_request(), state=state)
        assert ctx.state is state
