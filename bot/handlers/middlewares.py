from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from bot.context import AppContext

logger = logging.getLogger(__name__)


class ContextMiddleware(BaseMiddleware):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self._ctx = ctx

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["ctx"] = self._ctx
        if isinstance(event, Message) and event.from_user:
            data["is_admin"] = event.from_user.id in self._ctx.settings.admin_ids
        else:
            data["is_admin"] = False
        return await handler(event, data)


class UserRateLimitMiddleware(BaseMiddleware):
    """Global per-user message rate limit (anti-spam burst)."""

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self._ctx = ctx

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.from_user:
            ok = await self._ctx.rate_limiter.check(event.from_user.id)
            if not ok:
                logger.info("rate_limited user=%s", event.from_user.id)
                return None
        return await handler(event, data)
