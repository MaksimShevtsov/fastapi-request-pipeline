"""Tests for throttling components."""

from __future__ import annotations

from typing import Any

import pytest

from fastapi_request_pipeline.component import ComponentCategory
from fastapi_request_pipeline.components.throttling import (
    InMemoryThrottleBackend,
    PreAuthRateLimit,
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


class _FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class TestInMemoryThrottleBackendEviction:
    async def test_expired_keys_are_evicted(self) -> None:
        clock = _FakeClock()
        backend = InMemoryThrottleBackend(clock=clock, sweep_interval=30)
        for i in range(100):
            await backend.increment(f"ip:{i}", 10)
        assert len(backend) == 100
        clock.now += 60
        await backend.increment("ip:new", 10)
        assert len(backend) == 1

    async def test_live_keys_are_kept(self) -> None:
        clock = _FakeClock()
        backend = InMemoryThrottleBackend(clock=clock, sweep_interval=30)
        await backend.increment("short", 10)
        await backend.increment("long", 3600)
        clock.now += 60
        await backend.increment("other", 10)
        assert len(backend) == 2
        count, _ = await backend.increment("long", 3600)
        assert count == 2

    async def test_no_sweep_before_interval(self) -> None:
        clock = _FakeClock()
        backend = InMemoryThrottleBackend(clock=clock, sweep_interval=300)
        await backend.increment("a", 10)
        clock.now += 60
        await backend.increment("b", 10)
        assert len(backend) == 2

    async def test_expired_window_restarts_count(self) -> None:
        clock = _FakeClock()
        backend = InMemoryThrottleBackend(clock=clock)
        await backend.increment("a", 10)
        await backend.increment("a", 10)
        clock.now += 11
        assert await backend.increment("a", 10) == (1, 10)

    def test_rejects_non_positive_sweep_interval(self) -> None:
        with pytest.raises(ValueError):
            InMemoryThrottleBackend(sweep_interval=0)


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


class TestDefaultKeyFunc:
    async def test_dict_user_keyed_by_sub_not_whole_payload(
        self, make_request: Any
    ) -> None:
        comp = RateLimit(rate=1, window_seconds=60)
        request = make_request()
        await comp.resolve(
            RequestContext(request=request, user={"sub": "u1", "iat": 1})
        )
        with pytest.raises(Throttled):
            await comp.resolve(
                RequestContext(request=request, user={"sub": "u1", "iat": 2})
            )

    async def test_dict_user_keyed_by_id(self, make_request: Any) -> None:
        comp = RateLimit(rate=1, window_seconds=60)
        request = make_request()
        await comp.resolve(RequestContext(request=request, user={"id": 7, "v": 1}))
        with pytest.raises(Throttled):
            await comp.resolve(RequestContext(request=request, user={"id": 7, "v": 2}))

    async def test_object_user_keyed_by_id_attr(self, make_request: Any) -> None:
        class User:
            def __init__(self, id: str) -> None:
                self.id = id

        comp = RateLimit(rate=1, window_seconds=60)
        request = make_request()
        await comp.resolve(RequestContext(request=request, user=User("u1")))
        with pytest.raises(Throttled):
            await comp.resolve(RequestContext(request=request, user=User("u1")))

    async def test_different_users_have_separate_limits(
        self, make_request: Any
    ) -> None:
        comp = RateLimit(rate=1, window_seconds=60)
        request = make_request()
        await comp.resolve(RequestContext(request=request, user={"sub": "u1"}))
        await comp.resolve(RequestContext(request=request, user={"sub": "u2"}))

    async def test_user_without_identity_falls_back_to_ip(
        self, make_request: Any
    ) -> None:
        comp = RateLimit(rate=1, window_seconds=60)

        def ctx(user: object) -> RequestContext:
            request = make_request(headers={"x-forwarded-for": "1.2.3.4"})
            return RequestContext(request=request, user=user)

        await comp.resolve(ctx(object()))
        with pytest.raises(Throttled):
            await comp.resolve(ctx(object()))


class TestPreAuthRateLimit:
    def test_category_is_pre_auth(self) -> None:
        assert PreAuthRateLimit(rate=10).category == ComponentCategory.PRE_AUTH

    async def test_keys_by_ip_even_when_user_set(self, make_request: Any) -> None:
        comp = PreAuthRateLimit(rate=1, window_seconds=60)

        def ctx(user: object) -> RequestContext:
            request = make_request(headers={"x-forwarded-for": "1.2.3.4"})
            return RequestContext(request=request, user=user)

        await comp.resolve(ctx({"sub": "u1"}))
        with pytest.raises(Throttled):
            await comp.resolve(ctx({"sub": "u2"}))

    async def test_separate_ips_have_separate_limits(self, make_request: Any) -> None:
        comp = PreAuthRateLimit(rate=1, window_seconds=60)
        for ip in ("1.1.1.1", "2.2.2.2"):
            request = make_request(headers={"x-forwarded-for": ip})
            await comp.resolve(RequestContext(request=request))
