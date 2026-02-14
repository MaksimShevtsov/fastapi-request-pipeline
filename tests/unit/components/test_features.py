"""Tests for feature flag components."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from fastapi_request_pipeline.component import ComponentCategory
from fastapi_request_pipeline.components.features import FeatureEnabled
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.exceptions import FeatureDisabled


class TestFeatureEnabled:
    def test_category_is_feature(self) -> None:
        assert FeatureEnabled("beta").category == ComponentCategory.FEATURE

    async def test_passes_when_checker_returns_true(self, make_request: Any) -> None:
        checker = AsyncMock(return_value=True)
        ctx = RequestContext(request=make_request())
        await FeatureEnabled("beta", checker=checker).resolve(ctx)
        checker.assert_awaited_once_with("beta")

    async def test_raises_when_checker_returns_false(self, make_request: Any) -> None:
        checker = AsyncMock(return_value=False)
        ctx = RequestContext(request=make_request())
        with pytest.raises(FeatureDisabled):
            await FeatureEnabled("beta", checker=checker).resolve(ctx)

    async def test_passes_when_feature_in_state(self, make_request: Any) -> None:
        ctx = RequestContext(request=make_request(), state={"features": {"beta": True}})
        await FeatureEnabled("beta").resolve(ctx)

    async def test_raises_when_feature_not_in_state(self, make_request: Any) -> None:
        ctx = RequestContext(request=make_request())
        with pytest.raises(FeatureDisabled):
            await FeatureEnabled("beta").resolve(ctx)

    async def test_raises_when_feature_false_in_state(self, make_request: Any) -> None:
        ctx = RequestContext(
            request=make_request(), state={"features": {"beta": False}}
        )
        with pytest.raises(FeatureDisabled):
            await FeatureEnabled("beta").resolve(ctx)
