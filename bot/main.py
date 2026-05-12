from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import aiosqlite
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.ai.openrouter import OpenRouterClient
from bot.config.rules import load_rules
from bot.config.settings import get_settings
from bot.context import AppContext
from bot.database.connection import init_db
from bot.database.repository import Repository
from bot.handlers import admin, ai_cmd, group
from bot.handlers.middlewares import ContextMiddleware, UserRateLimitMiddleware
from bot.moderation.flood import FloodTracker
from bot.moderation.service import ModerationService
from bot.utils.admin_log import AdminActionLogger
from bot.utils.rate_limit import SlidingWindowRateLimiter

logger = logging.getLogger(__name__)


async def _http_ping_server(host: str, port: int) -> None:
    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            data = await reader.read(8192)
            first_line = data.decode("utf-8", errors="ignore").split("\r\n", 1)[0]
            if first_line.startswith("GET /ping"):
                body = b"OK"
                header = (
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: text/plain; charset=utf-8\r\n"
                    + f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
                )
                writer.write(header + body)
            else:
                writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    server = await asyncio.start_server(handle_client, host=host, port=port)
    async with server:
        await server.serve_forever()


async def _heartbeat_loop() -> None:
    while True:
        try:
            Path("status.txt").write_text(str(time.time()), encoding="utf-8")
        except OSError as e:
            logger.warning("heartbeat write failed: %s", e)
        await asyncio.sleep(30)


async def amain() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = get_settings()
    await init_db(settings.database_path)

    db = await aiosqlite.connect(settings.database_path)
    db.row_factory = aiosqlite.Row

    rules = load_rules(settings.rules_json_path)
    repo = Repository(db)
    ai_client = OpenRouterClient(settings)
    flood = FloodTracker()
    admin_logger = AdminActionLogger(settings.admin_log_path)
    moderation = ModerationService(
        settings=settings,
        rules=rules,
        repo=repo,
        ai=ai_client,
        flood=flood,
        admin_logger=admin_logger,
    )
    rate_limiter = SlidingWindowRateLimiter(
        window_sec=settings.rate_limit_window_sec,
        max_events=settings.rate_limit_max_messages,
    )

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    me = await bot.get_me()
    ctx = AppContext(
        settings=settings,
        rules=rules,
        repo=repo,
        ai=ai_client,
        moderation=moderation,
        rate_limiter=rate_limiter,
        admin_logger=admin_logger,
        bot_user_id=me.id,
    )

    dp = Dispatcher()
    dp.update.outer_middleware(ContextMiddleware(ctx))
    dp.update.outer_middleware(UserRateLimitMiddleware(ctx))

    dp.include_router(admin.router)
    dp.include_router(ai_cmd.router)
    dp.include_router(group.router)

    asyncio.create_task(_heartbeat_loop(), name="heartbeat")

    async def _ping_runner() -> None:
        try:
            await _http_ping_server(settings.ping_host, settings.ping_port)
        except OSError as e:
            logger.warning("HTTP /ping server not started (%s:%s): %s", settings.ping_host, settings.ping_port, e)

    asyncio.create_task(_ping_runner(), name="http_ping")

    logger.info("Bot @%s starting polling…", me.username or me.id)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await ai_client.aclose()
        await db.close()


def main() -> None:
    asyncio.run(amain())
