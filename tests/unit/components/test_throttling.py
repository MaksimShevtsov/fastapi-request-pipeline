"""Tests for throttling components."""

from __future__ import annotations

from typing import Any

import pytest

from fastapi_request_pipeline.component import ComponentCategory
from fastapi_request_pipeline.components.throttling import (
    InMemoryThrottleBackend,
    RateLimit,
)
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.exceptions import Throttled


class TestThrottleBackendProtocol:
    def test_in_memory_conforms(self) -> None:
        backend = InMemoryThrottleBackend()
        assert hasattr(backend, "increment")
        assert hasattr(backend, "reset")


class TestInMemoryThrottleBackend:
    async def test_increment_returns_count_and_ttl(self) -> None:
        backend = InMemoryThrottleBackend()
        count, ttl = await backend.increment("key1", 60)
        assert count == 1
        assert ttl > 0 and ttl <= 60

    async def test_increments_counter(self) -> None:
        backend = InMemoryThrottleBackend()
        await backend.increment("key1", 60)
        count, _ = await backend.increment("key1", 60)
        assert count == 2

    async def test_reset_clears_counter(self) -> None:
        backend = InMemoryThrottleBackend()
        await backend.increment("key1", 60)
        await backend.increment("key1", 60)
        await backend.reset("key1")
        count, _ = await backend.increment("key1", 60)
        assert count == 1

    async def test_separate_keys(self) -> None:
        backend = InMemoryThrottleBackend()
        await backend.increment("key1", 60)
        await backend.increment("key1", 60)
        count, _ = await backend.increment("key2", 60)
        assert count == 1


class TestRateLimit:
    def test_category_is_throttling(self) -> None:
        assert RateLimit(rate=10).category == ComponentCategory.THROTTLING

    async def test_allows_requests_under_limit(self, make_request: Any) -> None:
        backend = InMemoryThrottleBackend()
        comp = RateLimit(rate=5, window_seconds=60, backend=backend)
        for _ in range(5):
            request = make_request(headers={"x-forwarded-for": "1.2.3.4"})
            ctx = RequestContext(request=request)
            await comp.resolve(ctx)

    async def test_raises_when_limit_exceeded(self, make_request: Any) -> None:
        backend = InMemoryThrottleBackend()
        comp = RateLimit(rate=2, window_seconds=60, backend=backend)
        for _ in range(2):
            request = make_request(headers={"x-forwarded-for": "1.2.3.4"})
            ctx = RequestContext(request=request)
            await comp.resolve(ctx)

        request = make_request(headers={"x-forwarded-for": "1.2.3.4"})
        ctx = RequestContext(request=request)
        with pytest.raises(Throttled) as exc_info:
            await comp.resolve(ctx)
        assert exc_info.value.retry_after is not None
        assert exc_info.value.retry_after > 0

    async def test_uses_key_func_for_identity(self, make_request: Any) -> None:
        backend = InMemoryThrottleBackend()

        def key_func(ctx: RequestContext) -> str:
            return str(ctx.user)

        comp = RateLimit(rate=1, window_seconds=60, key_func=key_func, backend=backend)

        request = make_request()
        ctx1 = RequestContext(request=request, user="user-1")
        await comp.resolve(ctx1)

        ctx2 = RequestContext(request=request, user="user-2")
        await comp.resolve(ctx2)  # different key, should pass

    async def test_uses_custom_backend(self, make_request: Any) -> None:
        backend = InMemoryThrottleBackend()
        comp = RateLimit(rate=10, window_seconds=60, backend=backend)
        request = make_request(headers={"x-forwarded-for": "1.2.3.4"})
        ctx = RequestContext(request=request)
        await comp.resolve(ctx)

    async def test_defaults_to_in_memory_backend(self, make_request: Any) -> None:
        comp = RateLimit(rate=10, window_seconds=60)
        request = make_request(headers={"x-forwarded-for": "1.2.3.4"})
        ctx = RequestContext(request=request)
        await comp.resolve(ctx)  # should not raise
