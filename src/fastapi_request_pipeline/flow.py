"""Flow class — ordered container and execution engine for FlowComponents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi_request_pipeline.component import FlowComponent

if TYPE_CHECKING:
    from fastapi_request_pipeline.composition import DisableFlow, OverrideFlow
    from fastapi_request_pipeline.hooks import FlowHook


@dataclass(frozen=True)
class ResolvedFlow:
    """Immutable, pre-computed execution plan."""

    components: tuple[FlowComponent, ...]
    hooks: tuple[FlowHook, ...] = ()
    debug: bool = False


class Flow:
    """Ordered container of FlowComponent instances."""

    def __init__(
        self,
        *components: FlowComponent | Flow | OverrideFlow | DisableFlow,
        debug: bool = False,
    ) -> None:
        self._items: list[FlowComponent | Flow | OverrideFlow | DisableFlow] = list(
            components
        )
        self._hooks: list[FlowHook] = []
        self._debug = debug
        self._resolved: ResolvedFlow | None = None

    def add(
        self, *components: FlowComponent | Flow | OverrideFlow | DisableFlow
    ) -> Flow:
        self._items.extend(components)
        self._resolved = None
        return self

    def add_hook(self, hook: FlowHook) -> Flow:
        self._hooks.append(hook)
        self._resolved = None
        return self

    def resolve(self) -> ResolvedFlow:
        if self._resolved is not None:
            return self._resolved

        flat: list[FlowComponent] = []
        self._flatten(self._items, flat)

        sorted_components = sorted(flat, key=lambda c: c.category.order)

        self._resolved = ResolvedFlow(
            components=tuple(sorted_components),
            hooks=tuple(self._hooks),
            debug=self._debug,
        )
        return self._resolved

    @staticmethod
    def _flatten(
        items: list[FlowComponent | Flow | OverrideFlow | DisableFlow],
        out: list[FlowComponent],
    ) -> None:
        for item in items:
            if isinstance(item, Flow):
                Flow._flatten(item._items, out)
            elif isinstance(item, FlowComponent):
                out.append(item)
            # OverrideFlow and DisableFlow are handled by merge_flows, not here
