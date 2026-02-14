"""Tests for ComponentCategory enum and FlowComponent ABC."""

from __future__ import annotations

import pytest

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent
from fastapi_request_pipeline.context import RequestContext


class TestComponentCategory:
    def test_has_all_seven_members(self) -> None:
        members = list(ComponentCategory)
        assert len(members) == 7

    def test_member_values(self) -> None:
        assert ComponentCategory.AUTHENTICATION.value == "authentication"
        assert ComponentCategory.PERMISSION.value == "permission"
        assert ComponentCategory.FEATURE.value == "feature"
        assert ComponentCategory.THROTTLING.value == "throttling"
        assert ComponentCategory.FILTERS.value == "filters"
        assert ComponentCategory.PAGINATION.value == "pagination"
        assert ComponentCategory.CUSTOM.value == "custom"

    def test_ordering(self) -> None:
        ordered = sorted(ComponentCategory, key=lambda c: c.order)
        assert ordered == [
            ComponentCategory.AUTHENTICATION,
            ComponentCategory.PERMISSION,
            ComponentCategory.FEATURE,
            ComponentCategory.THROTTLING,
            ComponentCategory.FILTERS,
            ComponentCategory.PAGINATION,
            ComponentCategory.CUSTOM,
        ]

    def test_order_values_are_sequential(self) -> None:
        for i, cat in enumerate(ComponentCategory, start=1):
            assert cat.order == i


class TestFlowComponent:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            FlowComponent()  # type: ignore[abstract]

    def test_subclass_must_declare_category(self) -> None:
        class BadComponent(FlowComponent):
            async def resolve(self, ctx: RequestContext) -> None:
                pass

        with pytest.raises((TypeError, AttributeError)):
            _ = BadComponent().category  # type: ignore[abstract]

    def test_subclass_with_category_and_resolve(self, make_request: object) -> None:
        class GoodComponent(FlowComponent):
            category = ComponentCategory.CUSTOM

            async def resolve(self, ctx: RequestContext) -> None:
                ctx.state["touched"] = True

        comp = GoodComponent()
        assert comp.category == ComponentCategory.CUSTOM

    def test_openapi_spec_default_returns_none(self) -> None:
        class MinimalComponent(FlowComponent):
            category = ComponentCategory.CUSTOM

            async def resolve(self, ctx: RequestContext) -> None:
                pass

        comp = MinimalComponent()
        assert comp.openapi_spec() is None

    async def test_resolve_is_async(self, make_request: object) -> None:

        class AsyncComponent(FlowComponent):
            category = ComponentCategory.CUSTOM

            async def resolve(self, ctx: RequestContext) -> None:
                ctx.state["async"] = True

        comp = AsyncComponent()
        request = make_request()  # type: ignore[operator]
        ctx = RequestContext(request=request)
        await comp.resolve(ctx)
        assert ctx.state["async"] is True
