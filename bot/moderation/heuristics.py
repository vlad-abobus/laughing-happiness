from __future__ import annotations

import re
from typing import TYPE_CHECKING

from bot.moderation.types import ViolationKind

if TYPE_CHECKING:
    from bot.config.rules import ModerationRulesConfig

_URL_RE = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)


def heuristic_check(
    text: str | None,
    *,
    rules: ModerationRulesConfig,
    is_admin: bool,
) -> ViolationKind | None:
    if not text:
        return None
    lowered = text.lower()

    for w in rules.banned_words:
        if w and w in lowered:
            return ViolationKind.BANNED_WORD

    if _URL_RE.search(text):
        if is_admin and rules.allow_links_for_admins:
            return None
        if not rules.blocked_link_domains:
            return ViolationKind.LINK
        for d in rules.blocked_link_domains:
            if d and d in lowered:
                return ViolationKind.LINK
        return None

    if len(text) >= rules.spam_min_len_for_caps_check:
        letters = [c for c in text if c.isalpha()]
        if letters:
            caps = sum(1 for c in letters if c.isupper())
            if caps / len(letters) >= rules.spam_caps_ratio:
                return ViolationKind.SPAM

    if re.search(r"(.)\1{%d,}" % (rules.spam_min_repeated_char - 1), text):
        return ViolationKind.SPAM

    if len(text) > 4000 and len(set(text)) < 12:
        return ViolationKind.SPAM

    return None
