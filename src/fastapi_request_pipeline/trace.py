"""FlowTrace and TraceEntry — debug execution recording."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from fastapi_request_pipeline.component import ComponentCategory
from fastapi_request_pipeline.exceptions import FlowException


@dataclass(frozen=True)
class TraceEntry:
    """Single component execution record."""

    component_name: str
    category: ComponentCategory
    duration_ms: float
    outcome: Literal["OK", "FAILED"]
    reason: str | None = None


@dataclass
class FlowTrace:
    """Structured record of a single flow execution."""

    entries: list[TraceEntry] = field(default_factory=list)
    total_duration_ms: float = 0.0
    outcome: Literal["OK", "ABORTED", "ERROR"] = "OK"
    error: FlowException | None = None
