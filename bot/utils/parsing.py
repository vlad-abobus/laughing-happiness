from __future__ import annotations

import re
from typing import Any

_DURATION_RE = re.compile(
    r"^\s*(\d+)\s*([smhd]?)\s*$", re.IGNORECASE
)


def parse_duration_seconds(token: str) -> int | None:
    """Parse tokens like '600', '10m', '2h', '1d' into seconds."""
    m = _DURATION_RE.match(token.strip().lower())
    if not m:
        return None
    n = int(m.group(1))
    suf = (m.group(2) or "s").lower()
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}.get(suf)
    if mult is None:
        return None
    return max(1, n * mult)


def parse_command_args(text: str) -> tuple[str, list[str]]:
    """Split Telegram command line into command (lowercase) and args."""
    parts = text.split()
    if not parts:
        return "", []
    cmd = parts[0].split("@", 1)[0].lower()
    return cmd, parts[1:]


def extract_target_user_id(message: Any, args: list[str]) -> int | None:
    """Resolve target user from reply or first integer argument."""
    if getattr(message, "reply_to_message", None) and message.reply_to_message.from_user:
        return int(message.reply_to_message.from_user.id)
    if args:
        try:
            return int(args[0])
        except ValueError:
            return None
    return None
