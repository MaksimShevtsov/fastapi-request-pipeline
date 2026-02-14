"""Tests for OverrideFlow, DisableFlow, and merge_flows."""

from __future__ import annotations

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent
from fastapi_request_pipeline.composition import DisableFlow, OverrideFlow, merge_flows
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.flow import Flow


class _AuthStub(FlowComponent):
    category = ComponentCategory.AUTHENTICATION

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.user = {"from": "auth_stub"}


class _PermStub(FlowComponent):
    category = ComponentCategory.PERMISSION

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.state["perm"] = True


class _ThrottleStub(FlowComponent):
    category = ComponentCategory.THROTTLING

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.state["throttle"] = True


class _CustomStub(FlowComponent):
    category = ComponentCategory.CUSTOM

    async def resolve(self, ctx: RequestContext) -> None:
        ctx.state["custom"] = True


class TestOverrideFlow:
    def test_stores_component(self) -> None:
        comp = _AuthStub()
        override = OverrideFlow(comp)
        assert override.component is comp

    def test_derives_category(self) -> None:
        comp = _AuthStub()
        override = OverrideFlow(comp)
        assert override.category == ComponentCategory.AUTHENTICATION


class TestDisableFlow:
    def test_stores_category(self) -> None:
        disable = DisableFlow(ComponentCategory.THROTTLING)
        assert disable.category == ComponentCategory.THROTTLING


class TestMergeFlows:
    def test_last_writer_wins_replaces_category_group(self) -> None:
        auth1 = _AuthStub()
        auth2 = _AuthStub()
        f1 = Flow(auth1)
        f2 = Flow(auth2)
        merged = merge_flows(f1, f2)
        resolved = merged.resolve()
        assert len(resolved.components) == 1
        assert resolved.components[0] is auth2

    def test_override_replaces_category(self) -> None:
        auth1 = _AuthStub()
        auth2 = _AuthStub()
        f1 = Flow(auth1)
        f2 = Flow(OverrideFlow(auth2))
        merged = merge_flows(f1, f2)
        resolved = merged.resolve()
        assert len(resolved.components) == 1
        assert resolved.components[0] is auth2

    def test_disable_removes_category(self) -> None:
        f1 = Flow(_AuthStub(), _ThrottleStub())
        f2 = Flow(DisableFlow(ComponentCategory.THROTTLING))
        merged = merge_flows(f1, f2)
        resolved = merged.resolve()
        categories = [c.category for c in resolved.components]
        assert ComponentCategory.THROTTLING not in categories
        assert ComponentCategory.AUTHENTICATION in categories

    def test_merging_zero_flows_returns_empty(self) -> None:
        merged = merge_flows()
        resolved = merged.resolve()
        assert len(resolved.components) == 0

    def test_two_overrides_same_category_last_wins(self) -> None:
        auth1 = _AuthStub()
        auth2 = _AuthStub()
        f1 = Flow(OverrideFlow(auth1))
        f2 = Flow(OverrideFlow(auth2))
        merged = merge_flows(f1, f2)
        resolved = merged.resolve()
        assert len(resolved.components) == 1
        assert resolved.components[0] is auth2

    def test_disable_then_override_re_adds(self) -> None:
        auth = _AuthStub()
        f1 = Flow(_AuthStub())
        f2 = Flow(DisableFlow(ComponentCategory.AUTHENTICATION))
        f3 = Flow(OverrideFlow(auth))
        merged = merge_flows(f1, f2, f3)
        resolved = merged.resolve()
        assert len(resolved.components) == 1
        assert resolved.components[0] is auth

    def test_preserves_unaffected_categories(self) -> None:
        f1 = Flow(_AuthStub(), _PermStub(), _ThrottleStub())
        f2 = Flow(DisableFlow(ComponentCategory.THROTTLING))
        merged = merge_flows(f1, f2)
        resolved = merged.resolve()
        categories = [c.category for c in resolved.components]
        assert ComponentCategory.AUTHENTICATION in categories
        assert ComponentCategory.PERMISSION in categories
        assert ComponentCategory.THROTTLING not in categories

    def test_multiple_components_per_category_replaced_as_group(self) -> None:
        p1 = _PermStub()
        p2 = _PermStub()
        p3 = _PermStub()
        f1 = Flow(p1, p2)
        f2 = Flow(p3)
        merged = merge_flows(f1, f2)
        resolved = merged.resolve()
        perm_components = [
            c for c in resolved.components if c.category == ComponentCategory.PERMISSION
        ]
        assert len(perm_components) == 1
        assert perm_components[0] is p3
