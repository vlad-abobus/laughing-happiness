from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import aiosqlite


@dataclass(slots=True)
class ChatSettingsRow:
    chat_id: int
    welcome_enabled: bool
    welcome_parse_mode: str | None
    welcome_template: str | None
    moderation_enabled: bool


class Repository:
    """Persistence for moderation, audits, and per-chat overrides."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db
        self._lock = asyncio.Lock()

    async def is_globally_bot_blocked(self, user_id: int) -> bool:
        async with self._lock:
            cur = await self._db.execute(
                "SELECT 1 FROM global_bot_blocks WHERE user_id = ? LIMIT 1",
                (user_id,),
            )
            row = await cur.fetchone()
            await cur.close()
            return row is not None

    async def add_global_bot_block(self, user_id: int, reason: str | None) -> None:
        async with self._lock:
            await self._db.execute(
                """
                INSERT INTO global_bot_blocks(user_id, reason, created_at)
                VALUES(?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET reason=excluded.reason
                """,
                (user_id, reason, time.time()),
            )
            await self._db.commit()

    async def remove_global_bot_block(self, user_id: int) -> None:
        async with self._lock:
            await self._db.execute(
                "DELETE FROM global_bot_blocks WHERE user_id = ?", (user_id,)
            )
            await self._db.commit()

    async def add_chat_ban(
        self, chat_id: int, user_id: int, reason: str | None
    ) -> None:
        async with self._lock:
            await self._db.execute(
                """
                INSERT INTO chat_bans(chat_id, user_id, reason, created_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET reason=excluded.reason
                """,
                (chat_id, user_id, reason, time.time()),
            )
            await self._db.commit()

    async def remove_chat_ban(self, chat_id: int, user_id: int) -> None:
        async with self._lock:
            await self._db.execute(
                "DELETE FROM chat_bans WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )
            await self._db.commit()

    async def is_chat_banned(self, chat_id: int, user_id: int) -> bool:
        async with self._lock:
            cur = await self._db.execute(
                "SELECT 1 FROM chat_bans WHERE chat_id = ? AND user_id = ? LIMIT 1",
                (chat_id, user_id),
            )
            row = await cur.fetchone()
            await cur.close()
            return row is not None

    async def set_mute(
        self, chat_id: int, user_id: int, until_ts: float, reason: str | None
    ) -> None:
        async with self._lock:
            now = time.time()
            await self._db.execute(
                """
                INSERT INTO chat_mutes(chat_id, user_id, until_ts, reason, created_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                    until_ts=excluded.until_ts,
                    reason=excluded.reason,
                    created_at=excluded.created_at
                """,
                (chat_id, user_id, until_ts, reason, now),
            )
            await self._db.commit()

    async def clear_mute(self, chat_id: int, user_id: int) -> None:
        async with self._lock:
            await self._db.execute(
                "DELETE FROM chat_mutes WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )
            await self._db.commit()

    async def get_active_mute_until(
        self, chat_id: int, user_id: int
    ) -> float | None:
        async with self._lock:
            cur = await self._db.execute(
                "SELECT until_ts FROM chat_mutes WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )
            row = await cur.fetchone()
            await cur.close()
            if not row:
                return None
            until_ts = float(row["until_ts"])
            if until_ts <= time.time():
                await self._db.execute(
                    "DELETE FROM chat_mutes WHERE chat_id = ? AND user_id = ?",
                    (chat_id, user_id),
                )
                await self._db.commit()
                return None
            return until_ts

    async def get_warnings(self, chat_id: int, user_id: int) -> int:
        async with self._lock:
            cur = await self._db.execute(
                "SELECT count FROM warnings WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )
            row = await cur.fetchone()
            await cur.close()
            return int(row["count"]) if row else 0

    async def set_warnings(self, chat_id: int, user_id: int, count: int) -> None:
        async with self._lock:
            now = time.time()
            await self._db.execute(
                """
                INSERT INTO warnings(chat_id, user_id, count, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                    count=excluded.count,
                    updated_at=excluded.updated_at
                """,
                (chat_id, user_id, count, now),
            )
            await self._db.commit()

    async def add_warning(self, chat_id: int, user_id: int, delta: int = 1) -> int:
        async with self._lock:
            cur = await self._db.execute(
                "SELECT count FROM warnings WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            )
            row = await cur.fetchone()
            await cur.close()
            new_count = int(row["count"]) + delta if row else max(delta, 0)
            new_count = max(new_count, 0)
            now = time.time()
            await self._db.execute(
                """
                INSERT INTO warnings(chat_id, user_id, count, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                    count=excluded.count,
                    updated_at=excluded.updated_at
                """,
                (chat_id, user_id, new_count, now),
            )
            await self._db.commit()
            return new_count

    async def log_violation(
        self,
        chat_id: int,
        user_id: int,
        violation_type: str,
        detail: str | None,
        message_id: int | None,
    ) -> None:
        async with self._lock:
            await self._db.execute(
                """
                INSERT INTO violations(chat_id, user_id, violation_type, detail, message_id, created_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (chat_id, user_id, violation_type, detail, message_id, time.time()),
            )
            await self._db.commit()

    async def log_admin_action(
        self,
        admin_id: int,
        action: str,
        chat_id: int | None,
        target_user_id: int | None,
        detail: str | None,
    ) -> None:
        async with self._lock:
            await self._db.execute(
                """
                INSERT INTO admin_audit(created_at, chat_id, admin_id, action, target_user_id, detail)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (time.time(), chat_id, admin_id, action, target_user_id, detail),
            )
            await self._db.commit()

    async def get_chat_settings(self, chat_id: int) -> ChatSettingsRow | None:
        async with self._lock:
            cur = await self._db.execute(
                "SELECT * FROM chat_settings WHERE chat_id = ?", (chat_id,)
            )
            row = await cur.fetchone()
            await cur.close()
            if not row:
                return None
            return ChatSettingsRow(
                chat_id=int(row["chat_id"]),
                welcome_enabled=bool(row["welcome_enabled"]),
                welcome_parse_mode=row["welcome_parse_mode"],
                welcome_template=row["welcome_template"],
                moderation_enabled=bool(row["moderation_enabled"]),
            )

    async def upsert_chat_settings(
        self,
        chat_id: int,
        *,
        welcome_enabled: bool | None = None,
        welcome_parse_mode: str | None = None,
        welcome_template: str | None = None,
        moderation_enabled: bool | None = None,
    ) -> None:
        async with self._lock:
            cur = await self._db.execute(
                "SELECT * FROM chat_settings WHERE chat_id = ?", (chat_id,)
            )
            existing = await cur.fetchone()
            await cur.close()
            now = time.time()
            if existing is None:
                await self._db.execute(
                    """
                    INSERT INTO chat_settings(
                        chat_id, welcome_enabled, welcome_parse_mode, welcome_template,
                        moderation_enabled, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chat_id,
                        int(welcome_enabled if welcome_enabled is not None else True),
                        welcome_parse_mode,
                        welcome_template,
                        int(moderation_enabled if moderation_enabled is not None else True),
                        now,
                    ),
                )
            else:
                ex = ChatSettingsRow(
                    chat_id=int(existing["chat_id"]),
                    welcome_enabled=bool(existing["welcome_enabled"]),
                    welcome_parse_mode=existing["welcome_parse_mode"],
                    welcome_template=existing["welcome_template"],
                    moderation_enabled=bool(existing["moderation_enabled"]),
                )
                we = (
                    int(welcome_enabled)
                    if welcome_enabled is not None
                    else int(ex.welcome_enabled)
                )
                wpm = (
                    welcome_parse_mode
                    if welcome_parse_mode is not None
                    else ex.welcome_parse_mode
                )
                wt = (
                    welcome_template
                    if welcome_template is not None
                    else ex.welcome_template
                )
                me = (
                    int(moderation_enabled)
                    if moderation_enabled is not None
                    else int(ex.moderation_enabled)
                )
                await self._db.execute(
                    """
                    UPDATE chat_settings SET
                        welcome_enabled = ?,
                        welcome_parse_mode = ?,
                        welcome_template = ?,
                        moderation_enabled = ?,
                        updated_at = ?
                    WHERE chat_id = ?
                    """,
                    (we, wpm, wt, me, now, chat_id),
                )
            await self._db.commit()
