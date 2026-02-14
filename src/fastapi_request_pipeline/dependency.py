"""flow_dependency() — factory producing FastAPI-compatible dependency callables."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException
from starlette.requests import Request

from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.exceptions import (
    FlowAbort,
    FlowException,
    FlowInternalError,
)
from fastapi_request_pipeline.flow import Flow, ResolvedFlow
from fastapi_request_pipeline.openapi import collect_openapi_metadata
from fastapi_request_pipeline.trace import FlowTrace, TraceEntry


def flow_dependency(flow: Flow) -> Callable[..., Awaitable[RequestContext]]:
    """Return a FastAPI-compatible dependency that executes the flow."""
    resolved = flow.resolve()
    metadata = collect_openapi_metadata(resolved)

    if resolved.debug:
        dep = _make_debug_dependency(resolved)
    else:
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

        for hook in resolved.hooks:
            await hook.on_flow_start(ctx)

        try:
            for component in resolved.components:
                try:
                    await component.resolve(ctx)
                except FlowAbort as exc:
                    for hook in resolved.hooks:
                        await hook.on_component(ctx, component, exc)
                    raise
                else:
                    for hook in resolved.hooks:
                        await hook.on_component(ctx, component, None)
        except FlowAbort as exc:
            for hook in resolved.hooks:
                await hook.on_flow_end(ctx)
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        except FlowException:
            for hook in resolved.hooks:
                await hook.on_flow_end(ctx)
            raise
        except Exception as exc:
            for hook in resolved.hooks:
                await hook.on_flow_end(ctx)
            wrapped = FlowInternalError("Internal flow error", cause=exc)
            raise HTTPException(status_code=500, detail=wrapped.detail) from wrapped

        for hook in resolved.hooks:
            await hook.on_flow_end(ctx)

        return ctx

    return dependency


def _make_debug_dependency(
    resolved: ResolvedFlow,
) -> Callable[..., Awaitable[RequestContext]]:
    async def dependency(request: Request) -> RequestContext:
        ctx = RequestContext(request=request)
        trace = FlowTrace()
        flow_start = time.perf_counter()

        for hook in resolved.hooks:
            await hook.on_flow_start(ctx)

        try:
            for component in resolved.components:
                comp_start = time.perf_counter()
                try:
                    await component.resolve(ctx)
                    elapsed = (time.perf_counter() - comp_start) * 1000
                    trace.entries.append(
                        TraceEntry(
                            component_name=type(component).__name__,
                            category=component.category,
                            duration_ms=elapsed,
                            outcome="OK",
                        )
                    )
                    for hook in resolved.hooks:
                        await hook.on_component(ctx, component, None)
                except FlowAbort as exc:
                    elapsed = (time.perf_counter() - comp_start) * 1000
                    trace.entries.append(
                        TraceEntry(
                            component_name=type(component).__name__,
                            category=component.category,
                            duration_ms=elapsed,
                            outcome="FAILED",
                            reason=exc.detail,
                        )
                    )
                    for hook in resolved.hooks:
                        await hook.on_component(ctx, component, exc)
                    trace.total_duration_ms = (time.perf_counter() - flow_start) * 1000
                    trace.outcome = "ABORTED"
                    trace.error = exc
                    ctx.state["trace"] = trace
                    for hook in resolved.hooks:
                        await hook.on_flow_end(ctx)
                    raise HTTPException(
                        status_code=exc.status_code, detail=exc.detail
                    ) from exc
                except FlowException:
                    for hook in resolved.hooks:
                        await hook.on_flow_end(ctx)
                    raise
                except Exception as exc:
                    elapsed = (time.perf_counter() - comp_start) * 1000
                    trace.entries.append(
                        TraceEntry(
                            component_name=type(component).__name__,
                            category=component.category,
                            duration_ms=elapsed,
                            outcome="FAILED",
                            reason=str(exc),
                        )
                    )
                    trace.total_duration_ms = (time.perf_counter() - flow_start) * 1000
                    trace.outcome = "ERROR"
                    wrapped = FlowInternalError("Internal flow error", cause=exc)
                    trace.error = wrapped
                    ctx.state["trace"] = trace
                    for hook in resolved.hooks:
                        await hook.on_flow_end(ctx)
                    raise HTTPException(
                        status_code=500, detail=wrapped.detail
                    ) from wrapped
        except HTTPException:
            raise
        except FlowException:
            raise

        trace.total_duration_ms = (time.perf_counter() - flow_start) * 1000
        trace.outcome = "OK"
        ctx.state["trace"] = trace

        for hook in resolved.hooks:
            await hook.on_flow_end(ctx)

        return ctx

    return dependency


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
