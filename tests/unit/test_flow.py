"""Tests for Flow class and ResolvedFlow."""

from __future__ import annotations

from typing import Any

import pytest

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.flow import Flow, ResolvedFlow


class _AuthStub(FlowComponent):
    category = ComponentCategory.AUTHENTICATION

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.state["auth"] = True


class _PermStub(FlowComponent):
    category = ComponentCategory.PERMISSION

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.state["perm"] = True


class _CustomStub(FlowComponent):
    category = ComponentCategory.CUSTOM

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.state["custom"] = True


class _FilterStub(FlowComponent):
    category = ComponentCategory.FILTERS

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.state["filter"] = True


class TestFlowInit:
    def test_init_with_components(self) -> None:
        flow = Flow(_AuthStub(), _PermStub())
        resolved = flow.resolve()
        assert len(resolved.components) == 2

    def test_init_empty(self) -> None:
        flow = Flow()
        resolved = flow.resolve()
        assert len(resolved.components) == 0

    def test_add_returns_self(self) -> None:
        flow = Flow()
        result = flow.add(_AuthStub())
        assert result is flow


class TestFlowResolve:
    def test_components_sorted_by_category_order(self) -> None:
        flow = Flow(_CustomStub(), _AuthStub(), _PermStub())
        resolved = flow.resolve()
        categories = [c.category for c in resolved.components]
        assert categories == [
            ComponentCategory.AUTHENTICATION,
            ComponentCategory.PERMISSION,
            ComponentCategory.CUSTOM,
        ]

    def test_preserves_registration_order_within_category(self) -> None:
        class Perm1(FlowComponent):
            category = ComponentCategory.PERMISSION

            async def resolve(self, ctx: RequestContext) -> None:
                pass

        class Perm2(FlowComponent):
            category = ComponentCategory.PERMISSION

            async def resolve(self, ctx: RequestContext) -> None:
                pass

        p1 = Perm1()
        p2 = Perm2()
        flow = Flow(p1, p2)
        resolved = flow.resolve()
        assert resolved.components == (p1, p2)

    def test_nested_flow_flattening(self) -> None:
        inner = Flow(_PermStub())
        outer = Flow(_AuthStub(), inner, _CustomStub())
        resolved = outer.resolve()
        categories = [c.category for c in resolved.components]
        assert categories == [
            ComponentCategory.AUTHENTICATION,
            ComponentCategory.PERMISSION,
            ComponentCategory.CUSTOM,
        ]

    def test_empty_flow_resolves_to_empty(self) -> None:
        flow = Flow()
        resolved = flow.resolve()
        assert resolved.components == ()

    def test_resolve_returns_resolved_flow(self) -> None:
        flow = Flow(_AuthStub())
        resolved = flow.resolve()
        assert isinstance(resolved, ResolvedFlow)

    def test_resolved_flow_components_are_tuple(self) -> None:
        flow = Flow(_AuthStub())
        resolved = flow.resolve()
        assert isinstance(resolved.components, tuple)

    def test_resolve_caches_result(self) -> None:
        flow = Flow(_AuthStub())
        r1 = flow.resolve()
        r2 = flow.resolve()
        assert r1 is r2

    def test_debug_flag_propagated(self) -> None:
        flow = Flow(_AuthStub(), debug=True)
        resolved = flow.resolve()
        assert resolved.debug is True

    def test_debug_default_false(self) -> None:
        flow = Flow(_AuthStub())
        resolved = flow.resolve()
        assert resolved.debug is False


class TestFlowEdgeCases:
    """Edge case tests per spec (T055)."""

    def test_empty_flow_executes_as_noop(self) -> None:
        flow = Flow()
        resolved = flow.resolve()
        assert len(resolved.components) == 0

    def test_deeply_nested_flow_flattening(self) -> None:
        inner_inner = Flow(_AuthStub())
        inner = Flow(inner_inner)
        outer = Flow(inner, _CustomStub())
        resolved = outer.resolve()
        categories = [c.category for c in resolved.components]
        assert categories == [
            ComponentCategory.AUTHENTICATION,
            ComponentCategory.CUSTOM,
        ]

    async def test_non_flow_exception_wrapped_in_internal_error(
        self, make_request: Any
    ) -> None:
        from fastapi import HTTPException

        from fastapi_request_pipeline.dependency import flow_dependency

        class Broken(FlowComponent):
            category = ComponentCategory.CUSTOM

            async def resolve(self, ctx: RequestContext) -> None:
                raise RuntimeError("boom")

        flow = Flow(Broken())
        dep = flow_dependency(flow)
        with pytest.raises(HTTPException) as exc_info:
            await dep(make_request())
        assert exc_info.value.status_code == 500

    def test_add_invalidates_resolve_cache(self) -> None:
        flow = Flow(_AuthStub())
        r1 = flow.resolve()
        flow.add(_CustomStub())
        r2 = flow.resolve()
        assert r1 is not r2
        assert len(r2.components) == 2
