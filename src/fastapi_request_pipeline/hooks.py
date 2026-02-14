"""FlowHook base and convenience hook classes."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi_request_pipeline.component import FlowComponent
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.exceptions import FlowException


class FlowHook:
    """Base abstraction for lifecycle hooks. All methods are no-op by default."""

    async def on_flow_start(self, ctx: RequestContext) -> None:
        pass

    async def on_flow_end(self, ctx: RequestContext) -> None:
        pass

    async def on_component(
        self,
        ctx: RequestContext,
        component: FlowComponent,
        error: FlowException | None,
    ) -> None:
        pass


class BeforeFlow(FlowHook):
    """Convenience hook that only fires on flow start."""

    def __init__(self, callback: Callable[[RequestContext], Awaitable[None]]) -> None:
        self._callback = callback

    async def on_flow_start(self, ctx: RequestContext) -> None:
        await self._callback(ctx)


class AfterFlow(FlowHook):
    """Convenience hook that only fires on flow end."""

    def __init__(self, callback: Callable[[RequestContext], Awaitable[None]]) -> None:
        self._callback = callback

    async def on_flow_end(self, ctx: RequestContext) -> None:
        await self._callback(ctx)


class AfterComponent(FlowHook):
    """Convenience hook that fires after each component."""

    def __init__(
        self,
        callback: Callable[
            [RequestContext, FlowComponent, FlowException | None], Awaitable[None]
        ],
    ) -> None:
        self._callback = callback

    async def on_component(
        self,
        ctx: RequestContext,
        component: FlowComponent,
        error: FlowException | None,
    ) -> None:
        await self._callback(ctx, component, error)
