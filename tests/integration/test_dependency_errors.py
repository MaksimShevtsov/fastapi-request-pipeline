"""Error-path behavior of flow_dependency: hooks, traces and logging."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from fastapi_request_pipeline.component import ComponentCategory, FlowComponent
from fastapi_request_pipeline.components.authentication import JWTAuthentication
from fastapi_request_pipeline.context import RequestContext
from fastapi_request_pipeline.dependency import flow_dependency
from fastapi_request_pipeline.exceptions import (
    FlowAbort,
    FlowException,
    FlowInternalError,
    PermissionDenied,
)
from fastapi_request_pipeline.flow import Flow
from fastapi_request_pipeline.hooks import FlowHook
from fastapi_request_pipeline.trace import FlowTrace


class _Ok(FlowComponent):
    category = ComponentCategory.CUSTOM

    async def resolve(self, ctx: RequestContext) -> None:
        pass


class _Deny(FlowComponent):
    category = ComponentCategory.PERMISSION

    async def resolve(self, ctx: RequestContext) -> None:
        raise PermissionDenied("nope")


class _Broken(FlowComponent):
    category = ComponentCategory.CUSTOM

    async def resolve(self, ctx: RequestContext) -> None:
        raise RuntimeError("boom")


class _Recorder(FlowHook):
    def __init__(self) -> None:
        self.component_errors: list[FlowException | None] = []
        self.end_traces: list[FlowTrace | None] = []
        self.ended = 0

    async def on_component(
        self,
        ctx: RequestContext,
        component: FlowComponent,
        error: FlowException | None,
    ) -> None:
        self.component_errors.append(error)

    async def on_flow_end(self, ctx: RequestContext) -> None:
        self.ended += 1
        self.end_traces.append(ctx.state.get("trace"))


def _make_app(flow: Flow) -> FastAPI:
    app = FastAPI()

    @app.get("/test")
    async def endpoint(
        ctx: RequestContext = Depends(flow_dependency(flow)),  # noqa: B008
    ) -> dict[str, Any]:
        return {"ok": True}

    return app


async def _get(app: FastAPI, **kwargs: Any) -> Any:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/test", **kwargs)


@pytest.fixture(params=[False, True], ids=["normal", "debug"])
def debug(request: pytest.FixtureRequest) -> bool:
    value: bool = request.param
    return value


class TestAbort:
    async def test_abort_reaches_hooks(self, debug: bool) -> None:
        rec = _Recorder()
        flow = Flow(_Deny(), debug=debug).add_hook(rec)
        resp = await _get(_make_app(flow))
        assert resp.status_code == 403
        assert len(rec.component_errors) == 1
        assert isinstance(rec.component_errors[0], PermissionDenied)
        assert rec.ended == 1

    async def test_debug_trace_visible_to_end_hook_on_abort(self) -> None:
        rec = _Recorder()
        flow = Flow(_Ok(), _Deny(), debug=True).add_hook(rec)
        await _get(_make_app(flow))
        trace = rec.end_traces[0]
        assert trace is not None
        assert trace.outcome == "ABORTED"
        assert [e.outcome for e in trace.entries] == ["FAILED"]
        assert trace.entries[0].reason == "nope"
        assert isinstance(trace.error, PermissionDenied)


class TestUnexpectedComponentError:
    async def test_returns_500(self, debug: bool) -> None:
        resp = await _get(_make_app(Flow(_Broken(), debug=debug)))
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal flow error"

    async def test_reaches_on_component_as_internal_error(self, debug: bool) -> None:
        rec = _Recorder()
        flow = Flow(_Broken(), debug=debug).add_hook(rec)
        await _get(_make_app(flow))
        assert len(rec.component_errors) == 1
        error = rec.component_errors[0]
        assert isinstance(error, FlowInternalError)
        assert isinstance(error.cause, RuntimeError)
        assert rec.ended == 1

    async def test_debug_trace_records_error(self) -> None:
        rec = _Recorder()
        flow = Flow(_Broken(), debug=True).add_hook(rec)
        await _get(_make_app(flow))
        trace = rec.end_traces[0]
        assert trace is not None
        assert trace.outcome == "ERROR"
        assert trace.entries[0].outcome == "FAILED"
        assert trace.entries[0].reason == "boom"

    async def test_is_logged_with_traceback(
        self, debug: bool, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.ERROR, logger="fastapi_request_pipeline"):
            await _get(_make_app(Flow(_Broken(), debug=debug)))
        records = [r for r in caplog.records if r.name.startswith("fastapi_request")]
        assert len(records) == 1
        assert "_Broken" in records[0].getMessage()
        assert records[0].exc_info is not None


class _FailingStartHook(FlowHook):
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def on_flow_start(self, ctx: RequestContext) -> None:
        raise self._exc


class _FailingComponentHook(FlowHook):
    async def on_component(
        self,
        ctx: RequestContext,
        component: FlowComponent,
        error: FlowException | None,
    ) -> None:
        raise RuntimeError("hook boom")


class TestHookErrors:
    async def test_start_hook_error_returns_500(self, debug: bool) -> None:
        rec = _Recorder()
        flow = Flow(_Ok(), debug=debug)
        flow.add_hook(_FailingStartHook(RuntimeError("x"))).add_hook(rec)
        resp = await _get(_make_app(flow))
        assert resp.status_code == 500
        assert rec.ended == 1

    async def test_start_hook_abort_returns_its_status(self, debug: bool) -> None:
        flow = Flow(_Ok(), debug=debug)
        flow.add_hook(_FailingStartHook(FlowAbort("teapot", status_code=418)))
        resp = await _get(_make_app(flow))
        assert resp.status_code == 418
        assert resp.json()["detail"] == "teapot"

    async def test_component_hook_error_returns_500(self, debug: bool) -> None:
        flow = Flow(_Ok(), debug=debug).add_hook(_FailingComponentHook())
        resp = await _get(_make_app(flow))
        assert resp.status_code == 500

    async def test_component_hook_error_does_not_mark_component_failed(
        self,
    ) -> None:
        rec = _Recorder()
        flow = Flow(_Ok(), debug=True)
        flow.add_hook(_FailingComponentHook()).add_hook(rec)
        await _get(_make_app(flow))
        trace = rec.end_traces[0]
        assert trace is not None
        assert [e.outcome for e in trace.entries] == ["OK"]
        assert trace.outcome == "ERROR"


class TestAuthenticationLogging:
    async def test_decode_failure_logged_at_debug(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        decode = AsyncMock(side_effect=ValueError("bad signature"))
        flow = Flow(JWTAuthentication(decode=decode))
        with caplog.at_level(logging.DEBUG, logger="fastapi_request_pipeline"):
            resp = await _get(_make_app(flow), headers={"Authorization": "Bearer x"})
        assert resp.status_code == 401
        records = [
            r
            for r in caplog.records
            if r.name.startswith("fastapi_request_pipeline")
            and r.levelno == logging.DEBUG
            and r.exc_info is not None
        ]
        assert records
        assert isinstance(records[0].exc_info[1], ValueError)  # type: ignore[index]


class _FailingEndHook(FlowHook):
    async def on_flow_end(self, ctx: RequestContext) -> None:
        raise RuntimeError("end boom")


class _CustomFlowError(FlowException):
    pass


class _RaisesCustom(FlowComponent):
    category = ComponentCategory.CUSTOM

    async def resolve(self, ctx: RequestContext) -> None:
        raise _CustomFlowError("custom")


class TestEndHookErrors:
    async def test_end_hook_error_returns_500(self, debug: bool) -> None:
        flow = Flow(_Ok(), debug=debug).add_hook(_FailingEndHook())
        resp = await _get(_make_app(flow))
        assert resp.status_code == 500

    async def test_end_hook_error_keeps_original_abort(self, debug: bool) -> None:
        flow = Flow(_Deny(), debug=debug).add_hook(_FailingEndHook())
        resp = await _get(_make_app(flow))
        assert resp.status_code == 403


class TestCustomFlowException:
    async def test_propagates_unchanged_after_hooks(self, debug: bool) -> None:
        rec = _Recorder()
        flow = Flow(_RaisesCustom(), debug=debug).add_hook(rec)
        with pytest.raises(_CustomFlowError):
            await _get(_make_app(flow))
        assert isinstance(rec.component_errors[0], _CustomFlowError)
        assert rec.ended == 1
