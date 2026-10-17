"""Flow composition — merge_flows(), OverrideFlow, DisableFlow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent

if TYPE_CHECKING:
    from fastapi_request_pipeline.flow import Flow
    from fastapi_request_pipeline.hooks import FlowHook

# Categories whose components from all merged flows are combined instead of
# replaced, so a router-level check never silently drops an app-level one.
_ACCUMULATING_CATEGORIES = frozenset({ComponentCategory.PERMISSION})


class OverrideFlow:
    """Composition directive that replaces all components of a given category."""

    def __init__(self, component: FlowComponent) -> None:
        self.component = component
        self.category = component.category


class DisableFlow:
    """Composition directive that removes all components of a given category."""

    def __init__(self, category: ComponentCategory) -> None:
        self.category = category


def merge_flows(*flows: Flow) -> Flow:
    """Merge multiple flows by category.

    Later flows' component groups replace earlier flows' groups for the
    same ComponentCategory, except PERMISSION components, which accumulate
    across flows. OverrideFlow and DisableFlow directives are processed
    during merge and can replace or remove any category, including
    PERMISSION. Hooks from all flows are kept, in order.
    """
    from fastapi_request_pipeline.flow import Flow

    category_groups: dict[ComponentCategory, list[FlowComponent]] = {}
    hooks: list[FlowHook] = []
    debug = False

    for flow in flows:
        debug = debug or flow._debug
        for hook in flow._hooks:
            if not any(hook is h for h in hooks):
                hooks.append(hook)

        # Collect this flow's contributions per category
        flow_categories: dict[ComponentCategory, list[FlowComponent]] = {}
        directives: list[OverrideFlow | DisableFlow] = []

        for item in flow._items:
            if isinstance(item, (OverrideFlow, DisableFlow)):
                directives.append(item)
            elif isinstance(item, Flow):
                flat: list[FlowComponent] = []
                Flow._flatten([item], flat)
                for comp in flat:
                    flow_categories.setdefault(comp.category, []).append(comp)
            elif isinstance(item, FlowComponent):
                flow_categories.setdefault(item.category, []).append(item)

        # Apply regular components (last-writer-wins per category,
        # except accumulating categories)
        for cat, comps in flow_categories.items():
            if cat in _ACCUMULATING_CATEGORIES:
                group = category_groups.setdefault(cat, [])
                group.extend(c for c in comps if not any(c is g for g in group))
            else:
                category_groups[cat] = comps

        # Apply directives
        for directive in directives:
            if isinstance(directive, OverrideFlow):
                category_groups[directive.category] = [directive.component]
            elif isinstance(directive, DisableFlow):
                category_groups.pop(directive.category, None)

    # Build final flow from merged components
    all_components: list[FlowComponent] = []
    for cat in sorted(category_groups.keys(), key=lambda c: c.order):
        all_components.extend(category_groups[cat])

    merged = Flow(*all_components, debug=debug)
    for hook in hooks:
        merged.add_hook(hook)
    return merged
