"""Throttling components — RateLimit, ThrottleBackend, InMemoryThrottleBackend."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.exceptions import Throttled


@runtime_checkable
class ThrottleBackend(Protocol):
    """Pluggable storage interface for rate limit counters."""

    async def increment(self, key: str, window_seconds: int) -> tuple[int, int]: ...
    async def reset(self, key: str) -> None: ...


class InMemoryThrottleBackend:
    """Default in-memory throttle backend. Single-process only."""

    def __init__(self) -> None:
        self._counters: dict[str, tuple[int, float]] = {}

    async def increment(self, key: str, window_seconds: int) -> tuple[int, int]:
        now = time.monotonic()
        if key in self._counters:
            count, window_start = self._counters[key]
            elapsed = now - window_start
            if elapsed >= window_seconds:
                # Window expired, reset
                self._counters[key] = (1, now)
                return 1, window_seconds
            else:
                new_count = count + 1
                self._counters[key] = (new_count, window_start)
                remaining_ttl = int(window_seconds - elapsed)
                return new_count, max(remaining_ttl, 1)
        else:
            self._counters[key] = (1, now)
            return 1, window_seconds

    async def reset(self, key: str) -> None:
        self._counters.pop(key, None)


def _default_key_func(ctx: RequestContext) -> str:
    """Derive rate limit key from client IP or user identity."""
    if ctx.user is not None:
        return f"user:{ctx.user}"
    client = ctx.request.client
    if client is not None:
        return f"ip:{client.host}"
    forwarded = ctx.request.headers.get("x-forwarded-for")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    return "ip:unknown"


class RateLimit(FlowComponent):
    """Enforces rate limits with pluggable backend."""

    category = ComponentCategory.THROTTLING

    def __init__(
        self,
        rate: int,
        window_seconds: int = 60,
        *,
        key_func: Callable[[RequestContext], str] | None = None,
        backend: ThrottleBackend | None = None,
    ) -> None:
        self._rate = rate
        self._window_seconds = window_seconds
        self._key_func = key_func or _default_key_func
        self._backend: ThrottleBackend = backend or InMemoryThrottleBackend()

    async def resolve(self, ctx: RequestContext) -> None:
        key = self._key_func(ctx)
        count, ttl = await self._backend.increment(key, self._window_seconds)
        if count > self._rate:
            raise Throttled(retry_after=ttl)

    def openapi_spec(self) -> dict[str, Any] | None:
        return {
            "responses": {
                "429": {
                    "description": "Rate limit exceeded",
                    "headers": {
                        "Retry-After": {
                            "description": "Seconds until rate limit resets",
                            "schema": {"type": "integer"},
                        }
                    },
                }
            },
        }
