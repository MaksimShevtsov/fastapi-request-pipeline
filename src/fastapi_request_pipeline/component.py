"""FlowComponent abstract base class and ComponentCategory enum."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, ClassVar

from fastapi_request_pipeline.context import RequestContext


class ComponentCategory(Enum):
    """Processing component categories, defining strict execution order."""

    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    FEATURE = "feature"
    THROTTLING = "throttling"
    FILTERS = "filters"
    PAGINATION = "pagination"
    CUSTOM = "custom"

    @property
    def order(self) -> int:
        _ORDER = {
            "authentication": 1,
            "permission": 2,
            "feature": 3,
            "throttling": 4,
            "filters": 5,
            "pagination": 6,
            "custom": 7,
        }
        return _ORDER[self.value]


class FlowComponent(ABC):
    """Base abstraction for all processing units in a flow."""

    category: ClassVar[ComponentCategory]

    @abstractmethod
    async def resolve(self, ctx: RequestContext) -> None: ...

    def openapi_spec(self) -> dict[str, Any] | None:
        return None
