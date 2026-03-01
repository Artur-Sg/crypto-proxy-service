from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass(slots=True)
class HealthSnapshot:
    status: str
    last_success_ago_s: float | None
    last_error_ago_s: float | None
    error_count: int


class HealthState:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._last_success: float | None = None
        self._last_error: float | None = None
        self._error_count: int = 0

    async def record_success(self) -> None:
        async with self._lock:
            self._last_success = time.monotonic()

    async def record_error(self) -> None:
        async with self._lock:
            self._last_error = time.monotonic()
            self._error_count += 1

    async def snapshot(self, window_seconds: float) -> HealthSnapshot:
        async with self._lock:
            now = time.monotonic()
            last_success_ago = None if self._last_success is None else now - self._last_success
            last_error_ago = None if self._last_error is None else now - self._last_error
            status = "ok"
            if last_success_ago is None or last_success_ago > window_seconds:
                status = "degraded"
            return HealthSnapshot(
                status=status,
                last_success_ago_s=last_success_ago,
                last_error_ago_s=last_error_ago,
                error_count=self._error_count,
            )
