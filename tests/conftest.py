"""Shared pytest fixtures for fastapi-request-pipeline tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request


@pytest.fixture
def make_request() -> Any:
    """Factory for creating mock Starlette Request objects."""

    def _make(
        method: str = "GET",
        path: str = "/",
        headers: dict[str, str] | None = None,
        query_string: str = "",
    ) -> Request:
        scope: dict[str, Any] = {
            "type": "http",
            "method": method,
            "path": path,
            "query_string": query_string.encode(),
            "headers": [
                (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
            ],
            "root_path": "",
        }
        return Request(scope)

    return _make


@pytest.fixture
def mock_decode() -> AsyncMock:
    """Mock async JWT decode callback that returns a sample user dict."""
    mock = AsyncMock()
    mock.return_value = {"sub": "user-123", "email": "test@example.com"}
    return mock


@pytest.fixture
def mock_lookup() -> AsyncMock:
    """Mock async session lookup callback."""
    mock = AsyncMock()
    mock.return_value = {"id": "user-456", "name": "Cookie User"}
    return mock


@pytest.fixture
def mock_validate() -> AsyncMock:
    """Mock async API key validation callback."""
    mock = AsyncMock()
    mock.return_value = {"id": "service-789", "name": "API Service"}
    return mock


@pytest.fixture
def sample_user() -> dict[str, Any]:
    """Sample user dict for testing."""
    return {
        "sub": "user-123",
        "email": "test@example.com",
        "roles": ["admin", "user"],
        "permissions": ["tickets.read", "tickets.write", "users.delete"],
    }
