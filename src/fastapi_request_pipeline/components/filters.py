"""Filter components — QueryFilter."""

from __future__ import annotations

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent
from fastapi_request_pipeline.context import RequestContext


class QueryFilter(FlowComponent):
    """Extracts specified query parameters into ctx.state."""

    category = ComponentCategory.FILTERS

    def __init__(self, *fields: str, state_key: str = "filters") -> None:
        self._fields = fields
        self._state_key = state_key

    async def resolve(self, ctx: RequestContext) -> None:
        filters: dict[str, str] = {}
        for field in self._fields:
            value = ctx.request.query_params.get(field)
            if value is not None:
                filters[field] = value
        ctx.state[self._state_key] = filters
