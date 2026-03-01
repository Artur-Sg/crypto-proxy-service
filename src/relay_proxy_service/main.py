from __future__ import annotations

import uvicorn
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from http import HTTPStatus
import logging

from relay_proxy_service.config import Settings, UpstreamPicker, load_settings
from relay_proxy_service.health import HealthState
from relay_proxy_service.metrics import HTTP_ERRORS_TOTAL, HTTP_RESPONSE_TIME_SECONDS
from relay_proxy_service.proxy.http import ProxyResult, proxy_http_request
from relay_proxy_service.proxy.ws import proxy_ws_request


settings = load_settings()


def _effective_ws_upstreams() -> list[str]:
    if "ws" not in settings.enabled_protocols:
        return []
    if settings.ws_upstreams:
        return settings.ws_upstreams
    if "http" in settings.enabled_protocols:
        return settings.http_upstreams
    return []


http_upstreams = settings.http_upstreams if "http" in settings.enabled_protocols else []
ws_upstreams = _effective_ws_upstreams()

http_picker = UpstreamPicker(http_upstreams, settings.strategy) if http_upstreams else None
ws_picker = UpstreamPicker(ws_upstreams, settings.strategy) if ws_upstreams else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    timeout = httpx.Timeout(settings.read_timeout, connect=settings.connect_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        app.state.http_client = client
        yield

app = FastAPI(title="Relay Proxy Service", lifespan=lifespan)
access_logger = logging.getLogger("uvicorn.error")
health_state = HealthState()


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    import time

    request.state.start_time = time.perf_counter()
    return await call_next(request)


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    data = generate_latest()
    return PlainTextResponse(content=data, media_type=CONTENT_TYPE_LATEST)


@app.get("/livez")
async def livez() -> PlainTextResponse:
    return PlainTextResponse(content="ok", status_code=200)


@app.get("/readyz")
async def readyz() -> PlainTextResponse:
    if "http" in settings.enabled_protocols and not http_upstreams:
        return PlainTextResponse(content="no http upstreams", status_code=503)
    if "ws" in settings.enabled_protocols and not ws_upstreams:
        return PlainTextResponse(content="no ws upstreams", status_code=503)
    if "http" in settings.enabled_protocols:
        snapshot = await health_state.snapshot(settings.health_window_seconds)
        if snapshot.status != "ok":
            return PlainTextResponse(content="degraded", status_code=503)
    return PlainTextResponse(content="ready", status_code=200)


@app.get("/healthz")
async def healthz() -> PlainTextResponse:
    snapshot = await health_state.snapshot(settings.health_window_seconds)
    status = "ok"
    if "http" in settings.enabled_protocols and snapshot.status != "ok":
        status = "degraded"
    if "http" in settings.enabled_protocols and not http_upstreams:
        status = "degraded"
    if "ws" in settings.enabled_protocols and not ws_upstreams:
        status = "degraded"
    data = {
        "status": status,
        "http_upstreams": len(http_upstreams),
        "ws_upstreams": len(ws_upstreams),
        "last_success_ago_s": snapshot.last_success_ago_s,
        "last_error_ago_s": snapshot.last_error_ago_s,
        "error_count": snapshot.error_count,
    }
    return PlainTextResponse(content=str(data), status_code=200 if status == "ok" else 503)


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def http_proxy(path: str, request: Request):
    if "http" not in settings.enabled_protocols:
        return PlainTextResponse(content="HTTP disabled", status_code=503)
    if not http_picker:
        return PlainTextResponse(content="No HTTP upstreams", status_code=503)
    first = http_picker.pick()
    ordered = [first] + [u for u in http_upstreams if u != first]
    start = request.state.start_time if hasattr(request.state, "start_time") else None
    if start is None:
        import time

        start = time.perf_counter()

    result: ProxyResult = await proxy_http_request(
        request, ordered, request.app.state.http_client, settings
    )
    duration = None
    try:
        import time

        duration = time.perf_counter() - start
    except Exception:
        duration = None

    labels = {
        "method": request.method,
        "path": request.url.path,
        "status": str(result.response.status_code),
        "result": result.result,
        "upstream_status": str(result.upstream_status or ""),
    }
    if duration is not None:
        HTTP_RESPONSE_TIME_SECONDS.labels(**labels).observe(duration)
    if result.response.status_code >= 400:
        HTTP_ERRORS_TOTAL.labels(**labels).inc()
        await health_state.record_error()
    else:
        await health_state.record_success()

    try:
        client = request.client
        host = client.host if client else "-"
        port = client.port if client else "-"
        http_version = request.scope.get("http_version", "1.1")
        try:
            phrase = HTTPStatus(result.response.status_code).phrase
        except ValueError:
            phrase = ""
        upstream_used = result.upstream or (ordered[0] if ordered else "-")
        access_logger.info(
            '%s:%s - "%s %s HTTP/%s" %s %s upstream=%s',
            host,
            port,
            request.method,
            request.url.path,
            http_version,
            result.response.status_code,
            phrase,
            upstream_used,
        )
    except Exception:
        access_logger.exception("Failed to write access log")

    return result.response


@app.websocket("/{path:path}")
async def ws_proxy(path: str, websocket: WebSocket):
    if "ws" not in settings.enabled_protocols:
        await websocket.close(code=1011, reason="WS disabled")
        return
    if not ws_picker:
        await websocket.close(code=1011, reason="No WS upstreams")
        return
    first = ws_picker.pick()
    ordered = [first] + [u for u in ws_upstreams if u != first]
    full_path = f"/{path}"
    await proxy_ws_request(websocket, ordered, full_path, websocket.url.query or None, settings)


def run() -> None:
    uvicorn.run("relay_proxy_service.main:app", host="0.0.0.0", port=8080, reload=True)


if __name__ == "__main__":
    run()
