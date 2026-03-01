from __future__ import annotations

from typing import Iterable

import httpx
from fastapi import Request, Response

from crypto_proxy_service.config import HOP_BY_HOP_HEADERS, Settings


def _filter_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    filtered: dict[str, str] = {}
    for key, value in headers:
        if key.lower() in HOP_BY_HOP_HEADERS:
            continue
        filtered[key] = value
    return filtered


async def proxy_http_request(
    request: Request,
    upstream_base: str,
    settings: Settings,
) -> Response:
    path = request.url.path
    if request.url.query:
        path = f"{path}?{request.url.query}"

    url = f"{upstream_base}{path}"

    body = await request.body()
    headers = _filter_headers(request.headers.items())

    timeout = httpx.Timeout(settings.read_timeout, connect=settings.connect_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        upstream_response = await client.request(
            request.method,
            url,
            content=body,
            headers=headers,
        )

    response_headers = _filter_headers(upstream_response.headers.items())
    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
    )
