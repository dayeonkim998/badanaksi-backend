"""TTL 인메모리 캐시 — NIFS API 응답 재사용."""
import time
from typing import Any

_store: dict[str, tuple[Any, float]] = {}


def get(key: str, ttl: int) -> Any | None:
    if key not in _store:
        return None
    value, ts = _store[key]
    if time.time() - ts > ttl:
        del _store[key]
        return None
    return value


def set(key: str, value: Any) -> None:
    _store[key] = (value, time.time())
