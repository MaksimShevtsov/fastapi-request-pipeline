"""Flow composition — merge_flows(), OverrideFlow, DisableFlow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent

if TYPE_CHECKING:
    from fastapi_request_pipeline.flow import Flow


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
    """Merge multiple flows with last-writer-wins by category.

    Later flows' component groups replace earlier flows' groups
    for the same ComponentCategory. OverrideFlow and DisableFlow
    directives are processed during merge.
    """
    from fastapi_request_pipeline.flow import Flow

    category_groups: dict[ComponentCategory, list[FlowComponent]] = {}
    debug = False

    for flow in flows:
        debug = debug or flow._debug

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

        # Apply regular components (last-writer-wins per category)
        for cat, comps in flow_categories.items():
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

    return Flow(*all_components, debug=debug)
