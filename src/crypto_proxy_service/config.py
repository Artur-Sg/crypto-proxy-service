from __future__ import annotations

import os
import random
from dataclasses import dataclass
from itertools import cycle
from typing import Iterable

from dotenv import load_dotenv


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


@dataclass(slots=True)
class Settings:
    upstreams: list[str]
    strategy: str
    connect_timeout: float
    read_timeout: float


def _parse_upstreams(value: str) -> list[str]:
    items = [item.strip().rstrip("/") for item in value.split(",")]
    return [item for item in items if item]


def load_settings() -> Settings:
    load_dotenv()
    upstreams_raw = os.getenv("UPSTREAMS", "")
    upstreams = _parse_upstreams(upstreams_raw)
    if not upstreams:
        upstreams = ["http://localhost:9000"]

    strategy = os.getenv("UPSTREAM_STRATEGY", "random").lower()
    connect_timeout = float(os.getenv("CONNECT_TIMEOUT", "5"))
    read_timeout = float(os.getenv("READ_TIMEOUT", "30"))

    return Settings(
        upstreams=upstreams,
        strategy=strategy,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
    )


class UpstreamPicker:
    def __init__(self, upstreams: Iterable[str], strategy: str) -> None:
        self._upstreams = list(upstreams)
        self._strategy = strategy
        self._cycle = cycle(self._upstreams)

    def pick(self) -> str:
        if not self._upstreams:
            raise RuntimeError("No upstreams configured")
        if self._strategy == "round_robin":
            return next(self._cycle)
        return random.choice(self._upstreams)
