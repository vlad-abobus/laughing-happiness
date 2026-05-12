from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from collections.abc import Hashable


class SlidingWindowRateLimiter:
    """Simple in-memory sliding window limiter (spam / burst protection)."""

    def __init__(self, *, window_sec: int, max_events: int) -> None:
        self._window_sec = max(1, window_sec)
        self._max_events = max(1, max_events)
        self._events: dict[Hashable, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, key: Hashable) -> bool:
        """Return True if allowed, False if rate-limited."""
        now = time.monotonic()
        async with self._lock:
            q = self._events[key]
            while q and now - q[0] > self._window_sec:
                q.popleft()
            if len(q) >= self._max_events:
                return False
            q.append(now)
            return True
