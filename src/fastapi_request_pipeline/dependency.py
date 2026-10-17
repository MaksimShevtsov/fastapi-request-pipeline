"""flow_dependency() — factory producing FastAPI-compatible dependency callables."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException
from starlette.requests import Request

from fastapi_request_pipeline.component import FlowComponent
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.exceptions import (
    FlowAbort,
    FlowException,
    FlowInternalError,
)
from fastapi_request_pipeline.flow import Flow, ResolvedFlow
from fastapi_request_pipeline.openapi import collect_openapi_metadata
from fastapi_request_pipeline.trace import FlowTrace, TraceEntry

logger = logging.getLogger(__name__)


def flow_dependency(flow: Flow) -> Callable[..., Awaitable[RequestContext]]:
    """Return a FastAPI-compatible dependency that executes the flow."""
    resolved = flow.resolve()
    metadata = collect_openapi_metadata(resolved)

    dep = _make_dependency(resolved)

    # Attach metadata for OpenAPI enrichment
    dep._flow_openapi_metadata = metadata  # type: ignore[attr-defined]
    dep._flow_resolved = resolved  # type: ignore[attr-defined]

    return dep


def _make_dependency(
    resolved: ResolvedFlow,
) -> Callable[..., Awaitable[RequestContext]]:
    async def dependency(request: Request) -> RequestContext:
        ctx = RequestContext(request=request)
        trace: FlowTrace | None = None
        if resolved.debug:
            trace = FlowTrace()
            ctx.state["trace"] = trace
        flow_start = time.perf_counter()
        error: FlowException | None = None

        try:
            for hook in resolved.hooks:
                await hook.on_flow_start(ctx)
            for component in resolved.components:
                await _run_component(resolved, ctx, component, trace)
        except FlowException as exc:
            error = exc
        except Exception as exc:
            logger.exception("Unexpected error in flow hook")
            error = _internal_error(exc)

        if trace is not None:
            _finish_trace(trace, flow_start, error)

        try:
            for hook in resolved.hooks:
                await hook.on_flow_end(ctx)
        except Exception as exc:
            logger.exception("Unexpected error in on_flow_end hook")
            if error is None:
                error = _internal_error(exc)
                if trace is not None:
                    _finish_trace(trace, flow_start, error)

        if error is None:
            return ctx
        if isinstance(error, FlowAbort):
            raise HTTPException(
                status_code=error.status_code,
                detail=error.detail,
                headers=error.headers,
            ) from error
        if isinstance(error, FlowInternalError):
            raise HTTPException(status_code=500, detail=error.detail) from error
        raise error

    return dependency


async def _run_component(
    resolved: ResolvedFlow,
    ctx: RequestContext,
    component: FlowComponent,
    trace: FlowTrace | None,
) -> None:
    """Run one component, record it in the trace and notify hooks.

    Raises the component's FlowException, or a FlowInternalError wrapping
    any other exception, after the hooks have seen it.
    """
    name = type(component).__name__
    start = time.perf_counter()
    error: FlowException | None = None
    reason: str | None = None
    try:
        await component.resolve(ctx)
    except FlowAbort as exc:
        logger.debug("Flow aborted by %s: %s %s", name, exc.status_code, exc.detail)
        error = exc
        reason = exc.detail
    except FlowException as exc:
        error = exc
        reason = str(exc)
    except Exception as exc:
        logger.exception("Unexpected error in flow component %s", name)
        error = _internal_error(exc)
        reason = str(exc)

    if trace is not None:
        trace.entries.append(
            TraceEntry(
                component_name=name,
                category=component.category,
                duration_ms=(time.perf_counter() - start) * 1000,
                outcome="OK" if error is None else "FAILED",
                reason=reason,
            )
        )

    for hook in resolved.hooks:
        await hook.on_component(ctx, component, error)

    if error is not None:
        raise error


def _internal_error(exc: Exception) -> FlowInternalError:
    wrapped = FlowInternalError("Internal flow error", cause=exc)
    wrapped.__cause__ = exc
    return wrapped


def _finish_trace(
    trace: FlowTrace, flow_start: float, error: FlowException | None
) -> None:
    trace.total_duration_ms = (time.perf_counter() - flow_start) * 1000
    trace.error = error
    if error is None:
        trace.outcome = "OK"
    elif isinstance(error, FlowAbort):
        trace.outcome = "ABORTED"
    else:
        trace.outcome = "ERROR"


def enrich_openapi(app: Any) -> None:
    """Enrich FastAPI app's OpenAPI schema with flow metadata.

    Call this after all routes are registered to inject security schemes,
    responses, parameters, and extensions from flow components.
    """
    from fastapi import FastAPI
    from fastapi.routing import APIRoute

    if not isinstance(app, FastAPI):
        return

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue

        # Find flow dependency metadata in route dependencies
        metadata = _find_flow_metadata(route)
        if not metadata:
            continue

        # Inject security
        if "security" in metadata:
            route.openapi_extra = route.openapi_extra or {}
            route.openapi_extra["security"] = metadata["security"]

        # Inject responses
        if "responses" in metadata:
            existing = route.responses or {}
            for code, resp in metadata["responses"].items():
                if isinstance(resp, str):
                    existing[int(code)] = {"description": resp}
                else:
                    existing[int(code)] = resp
            route.responses = existing

        # Inject parameters
        if "parameters" in metadata:
            route.openapi_extra = route.openapi_extra or {}
            route.openapi_extra["parameters"] = metadata["parameters"]

        # Inject extensions
        for key, value in metadata.items():
            if key.startswith("x-"):
                route.openapi_extra = route.openapi_extra or {}
                route.openapi_extra[key] = value

    # Register security schemes at app level
    _register_security_schemes(app)


def _find_flow_metadata(route: Any) -> dict[str, Any] | None:
    """Find flow OpenAPI metadata attached to route dependencies."""
    for dep in route.dependant.dependencies:
        call = dep.call
        if hasattr(call, "_flow_openapi_metadata"):
            result: dict[str, Any] = call._flow_openapi_metadata
            return result
    return None


def _register_security_schemes(app: Any) -> None:
    """Register all flow security schemes in the app's OpenAPI schema."""
    from fastapi.routing import APIRoute

    all_schemes: dict[str, Any] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for dep in route.dependant.dependencies:
            call = dep.call
            if hasattr(call, "_flow_openapi_metadata"):
                meta: dict[str, Any] = call._flow_openapi_metadata  # type: ignore[union-attr]
                if "security_schemes" in meta:
                    all_schemes.update(meta["security_schemes"])

    if all_schemes:
        original_schema = app.openapi

        def custom_openapi() -> dict[str, Any]:
            schema: dict[str, Any] = original_schema()
            components = schema.setdefault("components", {})
            schemes = components.setdefault("securitySchemes", {})
            schemes.update(all_schemes)
            return schema

        app.openapi = custom_openapi
