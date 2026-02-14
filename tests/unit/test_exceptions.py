"""Tests for FlowException hierarchy."""

from __future__ import annotations

from fastapi_request_pipeline.exceptions import (
    AuthenticationFailed,
    FeatureDisabled,
    FlowAbort,
    FlowException,
    FlowInternalError,
    PermissionDenied,
    Throttled,
)


class TestFlowException:
    def test_is_base_exception(self) -> None:
        exc = FlowException("test")
        assert isinstance(exc, Exception)
        assert str(exc) == "test"


class TestFlowAbort:
    def test_default_status_code(self) -> None:
        exc = FlowAbort("bad request")
        assert exc.status_code == 400
        assert exc.detail == "bad request"

    def test_custom_status_code(self) -> None:
        exc = FlowAbort("not found", status_code=404)
        assert exc.status_code == 404

    def test_is_flow_exception(self) -> None:
        assert issubclass(FlowAbort, FlowException)


class TestAuthenticationFailed:
    def test_default_status_code_401(self) -> None:
        exc = AuthenticationFailed()
        assert exc.status_code == 401
        assert exc.detail == "Authentication failed"

    def test_custom_detail(self) -> None:
        exc = AuthenticationFailed("Token expired")
        assert exc.detail == "Token expired"
        assert exc.status_code == 401

    def test_is_flow_abort(self) -> None:
        assert issubclass(AuthenticationFailed, FlowAbort)


class TestPermissionDenied:
    def test_default_status_code_403(self) -> None:
        exc = PermissionDenied()
        assert exc.status_code == 403
        assert exc.detail == "Permission denied"

    def test_custom_detail(self) -> None:
        exc = PermissionDenied("Insufficient role")
        assert exc.detail == "Insufficient role"

    def test_is_flow_abort(self) -> None:
        assert issubclass(PermissionDenied, FlowAbort)


class TestFeatureDisabled:
    def test_default_status_code_403(self) -> None:
        exc = FeatureDisabled()
        assert exc.status_code == 403
        assert exc.detail == "Feature disabled"

    def test_custom_detail(self) -> None:
        exc = FeatureDisabled("Beta feature not available")
        assert exc.detail == "Beta feature not available"

    def test_is_flow_abort(self) -> None:
        assert issubclass(FeatureDisabled, FlowAbort)


class TestThrottled:
    def test_default_status_code_429(self) -> None:
        exc = Throttled()
        assert exc.status_code == 429
        assert exc.detail == "Rate limit exceeded"

    def test_retry_after(self) -> None:
        exc = Throttled(retry_after=30)
        assert exc.retry_after == 30

    def test_default_retry_after_is_none(self) -> None:
        exc = Throttled()
        assert exc.retry_after is None

    def test_custom_detail(self) -> None:
        exc = Throttled("Too many requests", retry_after=60)
        assert exc.detail == "Too many requests"
        assert exc.retry_after == 60

    def test_is_flow_abort(self) -> None:
        assert issubclass(Throttled, FlowAbort)


class TestFlowInternalError:
    def test_wraps_cause(self) -> None:
        original = ValueError("something broke")
        exc = FlowInternalError("internal error", cause=original)
        assert exc.cause is original
        assert str(exc) == "internal error"

    def test_cause_is_optional(self) -> None:
        exc = FlowInternalError("unknown error")
        assert exc.cause is None

    def test_is_flow_exception(self) -> None:
        assert issubclass(FlowInternalError, FlowException)

    def test_is_not_flow_abort(self) -> None:
        assert not issubclass(FlowInternalError, FlowAbort)
