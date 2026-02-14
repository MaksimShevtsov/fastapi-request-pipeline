"""RequestContext — per-request state container."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from starlette.requests import Request


@dataclass
class RequestContext:
    """Lightweight per-request state container mutated by flow components."""

    request: Request
    user: Any | None = None
    state: dict[str, Any] = field(default_factory=dict)
