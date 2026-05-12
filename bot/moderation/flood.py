from __future__ import annotations

import asyncio
import re
import time
from collections import defaultdict, deque
from collections.abc import Hashable


class FloodTracker:
    """Per-(chat,user) timestamps for flood detection."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._events: dict[tuple[int, int], deque[float]] = defaultdict(deque)

    async def is_flood(
        self, chat_id: int, user_id: int, *, window_sec: int, max_messages: int
    ) -> bool:
        """Return True if user exceeded the flood threshold in the chat."""
        now = time.monotonic()
        key = (chat_id, user_id)
        async with self._lock:
            q = self._events[key]
            while q and now - q[0] > window_sec:
                q.popleft()
            if len(q) >= max_messages:
                return True
            q.append(now)
            return False
