"""Tests for OverrideFlow, DisableFlow, and merge_flows."""

from __future__ import annotations

import pytest

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent
from fastapi_request_pipeline.composition import DisableFlow, OverrideFlow, merge_flows
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.dependency import flow_dependency
from fastapi_request_pipeline.flow import Flow
from fastapi_request_pipeline.hooks import FlowHook


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
        a1 = _AuthStub()
        a2 = _AuthStub()
        a3 = _AuthStub()
        merged = merge_flows(Flow(a1, a2), Flow(a3))
        assert merged.resolve().components == (a3,)

    def test_permission_components_accumulate(self) -> None:
        p1 = _PermStub()
        p2 = _PermStub()
        p3 = _PermStub()
        merged = merge_flows(Flow(p1, p2), Flow(p3))
        assert merged.resolve().components == (p1, p2, p3)

    def test_same_permission_instance_not_duplicated(self) -> None:
        perm = _PermStub()
        base = Flow(perm)
        merged = merge_flows(base, base)
        assert merged.resolve().components == (perm,)

    def test_override_replaces_accumulated_permissions(self) -> None:
        p3 = _PermStub()
        merged = merge_flows(
            Flow(_PermStub()), Flow(_PermStub()), Flow(OverrideFlow(p3))
        )
        assert merged.resolve().components == (p3,)

    def test_disable_removes_accumulated_permissions(self) -> None:
        merged = merge_flows(
            Flow(_PermStub()),
            Flow(_PermStub()),
            Flow(DisableFlow(ComponentCategory.PERMISSION)),
        )
        assert merged.resolve().components == ()

    def test_permissions_added_after_override_accumulate(self) -> None:
        p2 = _PermStub()
        p3 = _PermStub()
        merged = merge_flows(Flow(_PermStub()), Flow(OverrideFlow(p2)), Flow(p3))
        assert merged.resolve().components == (p2, p3)

    def test_hooks_are_preserved(self) -> None:
        h1 = FlowHook()
        h2 = FlowHook()
        merged = merge_flows(Flow().add_hook(h1), Flow().add_hook(h2))
        assert merged.resolve().hooks == (h1, h2)

    def test_same_hook_instance_not_duplicated(self) -> None:
        hook = FlowHook()
        base = Flow().add_hook(hook)
        merged = merge_flows(base, base)
        assert merged.resolve().hooks == (hook,)

    def test_directive_in_nested_flow_raises(self) -> None:
        nested = Flow(DisableFlow(ComponentCategory.THROTTLING))
        with pytest.raises(ValueError, match="DisableFlow"):
            merge_flows(Flow(_ThrottleStub()), Flow(nested))


class TestDirectivesOutsideMerge:
    def test_override_in_plain_flow_raises_on_resolve(self) -> None:
        flow = Flow(_AuthStub(), OverrideFlow(_AuthStub()))
        with pytest.raises(ValueError, match="OverrideFlow"):
            flow.resolve()

    def test_disable_in_plain_flow_raises_on_resolve(self) -> None:
        flow = Flow(_ThrottleStub(), DisableFlow(ComponentCategory.THROTTLING))
        with pytest.raises(ValueError, match="DisableFlow"):
            flow.resolve()

    def test_directive_in_nested_flow_raises_on_resolve(self) -> None:
        flow = Flow(Flow(OverrideFlow(_AuthStub())))
        with pytest.raises(ValueError, match="merge_flows"):
            flow.resolve()

    def test_flow_dependency_rejects_directive(self) -> None:
        with pytest.raises(ValueError):
            flow_dependency(Flow(OverrideFlow(_AuthStub())))
