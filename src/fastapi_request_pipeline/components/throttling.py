"""Throttling components — RateLimit, PreAuthRateLimit and throttle backends."""

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
    """Default in-memory fixed-window throttle backend. Single-process only.

    Expired keys are evicted in a sweep that runs at most once every
    ``sweep_interval`` seconds, so memory stays bounded by the number of
    keys active within one window.
    """

    def __init__(
        self,
        *,
        sweep_interval: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if sweep_interval <= 0:
            raise ValueError(f"sweep_interval must be positive, got {sweep_interval}")
        # key -> (count, window_start, window_seconds)
        self._counters: dict[str, tuple[int, float, int]] = {}
        self._sweep_interval = sweep_interval
        self._clock = clock
        self._next_sweep = clock() + sweep_interval

    def __len__(self) -> int:
        """Number of keys currently tracked."""
        return len(self._counters)

    async def increment(self, key: str, window_seconds: int) -> tuple[int, int]:
        now = self._clock()
        if now >= self._next_sweep:
            self._sweep(now)

        if key in self._counters:
            count, window_start, _ = self._counters[key]
            elapsed = now - window_start
            if elapsed >= window_seconds:
                # Window expired, reset
                self._counters[key] = (1, now, window_seconds)
                return 1, window_seconds
            else:
                new_count = count + 1
                self._counters[key] = (new_count, window_start, window_seconds)
                remaining_ttl = int(window_seconds - elapsed)
                return new_count, max(remaining_ttl, 1)
        else:
            self._counters[key] = (1, now, window_seconds)
            return 1, window_seconds

    async def reset(self, key: str) -> None:
        self._counters.pop(key, None)

    def _sweep(self, now: float) -> None:
        self._counters = {
            key: entry
            for key, entry in self._counters.items()
            if now - entry[1] < entry[2]
        }
        self._next_sweep = now + self._sweep_interval


_IDENTITY_FIELDS = ("sub", "id")


def _user_identity(user: Any) -> str | None:
    """Return a stable identifier for user from its ``sub`` or ``id`` field."""
    for name in _IDENTITY_FIELDS:
        value = user.get(name) if isinstance(user, dict) else getattr(user, name, None)
        if value is not None:
            return str(value)
    return None


def _default_key_func(ctx: RequestContext) -> str:
    """Derive rate limit key from user identity (``sub``/``id``) or client IP."""
    if ctx.user is not None:
        identity = _user_identity(ctx.user)
        if identity is not None:
            return f"user:{identity}"
    return _ip_key_func(ctx)


def _ip_key_func(ctx: RequestContext) -> str:
    """Derive rate limit key from client IP."""
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
        if rate <= 0:
            raise ValueError(f"rate must be positive, got {rate}")
        if window_seconds <= 0:
            raise ValueError(f"window_seconds must be positive, got {window_seconds}")
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


class PreAuthRateLimit(RateLimit):
    """Rate limit that runs before authentication, keyed by client IP.

    Because it runs ahead of AUTHENTICATION, requests with invalid
    credentials are counted too, which limits credential guessing.
    """

    category = ComponentCategory.PRE_AUTH

    def __init__(
        self,
        rate: int,
        window_seconds: int = 60,
        *,
        key_func: Callable[[RequestContext], str] | None = None,
        backend: ThrottleBackend | None = None,
    ) -> None:
        super().__init__(
            rate,
            window_seconds,
            key_func=key_func or _ip_key_func,
            backend=backend,
        )
