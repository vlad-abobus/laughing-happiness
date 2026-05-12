from __future__ import annotations

import asyncio
import logging
from pathlib import Path


class AdminActionLogger:
    """Append-only file log for administrative actions (in addition to DB audit)."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = asyncio.Lock()

    async def log_line(self, line: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        async with self._lock:
            try:
                with self._path.open("a", encoding="utf-8") as f:
                    f.write(line.rstrip("\n") + "\n")
            except OSError as e:
                logging.getLogger(__name__).error("admin log write failed: %s", e)
