"""Feature flag components."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.exceptions import FeatureDisabled


class FeatureEnabled(FlowComponent):
    """Checks a feature flag is enabled via callback or ctx.state."""

    category = ComponentCategory.FEATURE

    def __init__(
        self,
        feature: str,
        checker: Callable[[str], Awaitable[bool]] | None = None,
    ) -> None:
        self._feature = feature
        self._checker = checker

    async def resolve(self, ctx: RequestContext) -> None:
        if self._checker is not None:
            enabled = await self._checker(self._feature)
            if not enabled:
                raise FeatureDisabled()
            return

        features = ctx.state.get("features", {})
        if not features.get(self._feature):
            raise FeatureDisabled()

    def openapi_spec(self) -> dict[str, Any] | None:
        return {
            "responses": {"403": {"description": "Feature disabled"}},
        }
