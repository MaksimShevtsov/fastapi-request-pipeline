"""FlowComponent abstract base class and ComponentCategory enum."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, ClassVar

from fastapi_request_pipeline.context import RequestContext


class ComponentCategory(Enum):
    """Processing component categories, defining strict execution order."""

    PRE_AUTH = "pre_auth"
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
            "pre_auth": 1,
            "authentication": 2,
            "permission": 3,
            "feature": 4,
            "throttling": 5,
            "filters": 6,
            "pagination": 7,
            "custom": 8,
        }
        return _ORDER[self.value]


class FlowComponent(ABC):
    """Base abstraction for all processing units in a flow."""

    category: ClassVar[ComponentCategory]

    @abstractmethod
    async def resolve(self, ctx: RequestContext) -> None: ...

    def openapi_spec(self) -> dict[str, Any] | None:
        return None
