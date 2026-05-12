from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS global_bot_blocks (
    user_id INTEGER PRIMARY KEY,
    reason TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_bans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reason TEXT,
    created_at REAL NOT NULL,
    UNIQUE(chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS chat_mutes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    until_ts REAL NOT NULL,
    reason TEXT,
    created_at REAL NOT NULL,
    UNIQUE(chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS warnings (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL,
    PRIMARY KEY (chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    violation_type TEXT NOT NULL,
    detail TEXT,
    message_id INTEGER,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_settings (
    chat_id INTEGER PRIMARY KEY,
    welcome_enabled INTEGER NOT NULL DEFAULT 1,
    welcome_parse_mode TEXT,
    welcome_template TEXT,
    moderation_enabled INTEGER NOT NULL DEFAULT 1,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at REAL NOT NULL,
    chat_id INTEGER,
    admin_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    target_user_id INTEGER,
    detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_violations_user_chat
ON violations(chat_id, user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_admin_audit_created
ON admin_audit(created_at);
"""


async def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)
        await db.commit()
    logger.info("SQLite schema ready at %s", db_path)


@asynccontextmanager
async def get_connection(db_path: Path) -> AsyncIterator[aiosqlite.Connection]:
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()
