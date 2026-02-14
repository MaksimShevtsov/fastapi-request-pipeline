"""Shared type aliases and protocols."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

# Callback types used by authentication components
DecodeCallback = Callable[[str], Awaitable[Any]]
LookupCallback = Callable[[str], Awaitable[Any]]
ValidateCallback = Callable[[str], Awaitable[Any]]
FeatureCheckerCallback = Callable[[str], Awaitable[bool]]
