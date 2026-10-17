"""FlowException hierarchy for controlled flow aborts."""

from __future__ import annotations


class FlowException(Exception):
    """Base for all flow exceptions."""


class FlowAbort(FlowException):
    """Controlled abort with HTTP status code and detail."""

    def __init__(
        self,
        detail: str,
        *,
        status_code: int = 400,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.headers = headers


class AuthenticationFailed(FlowAbort):
    """Authentication check failed (401)."""

    def __init__(self, detail: str = "Authentication failed") -> None:
        super().__init__(detail, status_code=401)


class PermissionDenied(FlowAbort):
    """Permission or role check failed (403)."""

    def __init__(self, detail: str = "Permission denied") -> None:
        super().__init__(detail, status_code=403)


class FeatureDisabled(FlowAbort):
    """Feature flag is disabled (403)."""

    def __init__(self, detail: str = "Feature disabled") -> None:
        super().__init__(detail, status_code=403)


class Throttled(FlowAbort):
    """Rate limit exceeded (429)."""

    def __init__(
        self, detail: str = "Rate limit exceeded", *, retry_after: int | None = None
    ) -> None:
        headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
        super().__init__(detail, status_code=429, headers=headers)
        self.retry_after = retry_after


class FlowInternalError(FlowException):
    """Engine-level error wrapping unexpected exceptions."""

    def __init__(self, detail: str, *, cause: Exception | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.cause = cause
