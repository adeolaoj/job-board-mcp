"""A small in-memory cache whose entries expire after a fixed time."""

import time
from collections.abc import Callable
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.monotonic):
        self._ttl_seconds = ttl_seconds
        self._clock = clock

        # The cache is a dictionary mapping keys to tuples of (timestamp, value)
        self._cache: dict[str, tuple[float, Any]] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Return the cached value, or default if it's missing or expired."""
        entry = self._cache.get(key)
        if entry is None:
            return default

        timestamp, value = entry

        if self._clock() - timestamp >= self._ttl_seconds:
            del self._cache[key]
            return default

        return value

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = (self._clock(), value)