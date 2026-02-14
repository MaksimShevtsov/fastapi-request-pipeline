"""Pagination components — LimitOffset."""

from __future__ import annotations

from typing import Any

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.exceptions import FlowAbort


class LimitOffset(FlowComponent):
    """Parses limit/offset from query params into ctx.state."""

    category = ComponentCategory.PAGINATION

    def __init__(
        self,
        *,
        max_limit: int = 100,
        default_limit: int = 20,
        state_key: str = "pagination",
    ) -> None:
        self._max_limit = max_limit
        self._default_limit = default_limit
        self._state_key = state_key

    async def resolve(self, ctx: RequestContext) -> None:
        raw_limit = ctx.request.query_params.get("limit")
        raw_offset = ctx.request.query_params.get("offset")

        try:
            limit = int(raw_limit) if raw_limit is not None else self._default_limit
        except ValueError:
            raise FlowAbort("Invalid limit parameter", status_code=400) from None

        try:
            offset = int(raw_offset) if raw_offset is not None else 0
        except ValueError:
            raise FlowAbort("Invalid offset parameter", status_code=400) from None

        if limit < 0:
            raise FlowAbort("Limit must not be negative", status_code=400)
        if offset < 0:
            raise FlowAbort("Offset must not be negative", status_code=400)

        limit = min(limit, self._max_limit)

        ctx.state[self._state_key] = {"limit": limit, "offset": offset}

    def openapi_spec(self) -> dict[str, Any] | None:
        return {
            "parameters": [
                {
                    "name": "limit",
                    "in": "query",
                    "required": False,
                    "schema": {
                        "type": "integer",
                        "default": self._default_limit,
                        "maximum": self._max_limit,
                    },
                    "description": (
                        f"Max items to return"
                        f" (default: {self._default_limit},"
                        f" max: {self._max_limit})"
                    ),
                },
                {
                    "name": "offset",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "integer", "default": 0, "minimum": 0},
                    "description": "Number of items to skip",
                },
            ],
        }
