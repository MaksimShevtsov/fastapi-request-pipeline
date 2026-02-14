"""Tests for FlowHook, BeforeFlow, AfterFlow, AfterComponent."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.dependency import flow_dependency
from fastapi_request_pipeline.exceptions import FlowAbort, FlowException
from fastapi_request_pipeline.flow import Flow
from fastapi_request_pipeline.hooks import (
    AfterComponent,
    AfterFlow,
    BeforeFlow,
    FlowHook,
)


class _AuthStub(FlowComponent):
    category = ComponentCategory.AUTHENTICATION

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.user = {"sub": "user-1"}


class _CustomStub(FlowComponent):
    category = ComponentCategory.CUSTOM

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.state["custom"] = True


class _FailStub(FlowComponent):
    category = ComponentCategory.CUSTOM

    async def resolve(self, ctx: RequestContext) -> None:
        raise FlowAbort("denied", status_code=403)


class TestFlowHookBase:
    async def test_default_methods_are_noop(self, make_request: Any) -> None:
        class MinimalHook(FlowHook):
            pass

        hook = MinimalHook()
        ctx = RequestContext(request=make_request())
        await hook.on_flow_start(ctx)
        await hook.on_flow_end(ctx)
        await hook.on_component(ctx, _AuthStub(), None)


class TestBeforeFlow:
    async def test_callback_fires_on_flow_start(self, make_request: Any) -> None:
        callback = AsyncMock()
        flow = Flow(_AuthStub()).add_hook(BeforeFlow(callback))
        dep = flow_dependency(flow)
        await dep(make_request())
        callback.assert_awaited_once()

    async def test_only_fires_on_start(self, make_request: Any) -> None:
        start_called = []

        async def on_start(ctx: RequestContext) -> None:
            start_called.append(True)

        hook = BeforeFlow(on_start)
        ctx = RequestContext(request=make_request())
        await hook.on_flow_start(ctx)
        assert len(start_called) == 1

        # on_flow_end and on_component should be no-ops
        await hook.on_flow_end(ctx)
        await hook.on_component(ctx, _AuthStub(), None)


class TestAfterFlow:
    async def test_callback_fires_on_flow_end(self, make_request: Any) -> None:
        callback = AsyncMock()
        flow = Flow(_AuthStub()).add_hook(AfterFlow(callback))
        dep = flow_dependency(flow)
        await dep(make_request())
        callback.assert_awaited_once()

    async def test_fires_even_after_abort(self, make_request: Any) -> None:
        callback = AsyncMock()
        flow = Flow(_FailStub()).add_hook(AfterFlow(callback))
        dep = flow_dependency(flow)
        with pytest.raises(HTTPException):
            await dep(make_request())
        callback.assert_awaited_once()


class TestAfterComponent:
    async def test_callback_fires_after_each_component(self, make_request: Any) -> None:
        calls: list[tuple[str, bool]] = []

        async def on_comp(
            ctx: RequestContext, component: FlowComponent, error: FlowException | None
        ) -> None:
            calls.append((type(component).__name__, error is None))

        flow = Flow(_AuthStub(), _CustomStub()).add_hook(AfterComponent(on_comp))
        dep = flow_dependency(flow)
        await dep(make_request())
        assert len(calls) == 2
        assert calls[0] == ("_AuthStub", True)
        assert calls[1] == ("_CustomStub", True)

    async def test_fires_with_error_on_failure(self, make_request: Any) -> None:
        calls: list[tuple[str, bool]] = []

        async def on_comp(
            ctx: RequestContext, component: FlowComponent, error: FlowException | None
        ) -> None:
            calls.append((type(component).__name__, error is not None))

        flow = Flow(_AuthStub(), _FailStub()).add_hook(AfterComponent(on_comp))
        dep = flow_dependency(flow)
        with pytest.raises(HTTPException):
            await dep(make_request())
        assert len(calls) == 2
        assert calls[0] == ("_AuthStub", False)
        assert calls[1] == ("_FailStub", True)


class TestCustomComponentCategory:
    async def test_custom_component_executes_last(self, make_request: Any) -> None:
        order: list[str] = []

        class Auth(FlowComponent):
            category = ComponentCategory.AUTHENTICATION

            async def resolve(self, ctx: RequestContext) -> None:
                order.append("auth")

        class Custom(FlowComponent):
            category = ComponentCategory.CUSTOM

            async def resolve(self, ctx: RequestContext) -> None:
                order.append("custom")

        flow = Flow(Custom(), Auth())
        dep = flow_dependency(flow)
        await dep(make_request())
        assert order == ["auth", "custom"]
