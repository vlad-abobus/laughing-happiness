from __future__ import annotations

from enum import Enum


class ViolationKind(str, Enum):
    SPAM = "spam"
    FLOOD = "flood"
    TOXICITY = "toxicity"
    NSFW_TEXT = "nsfw_text"
    BANNED_WORD = "banned_word"
    LINK = "link"
    SUSPICIOUS = "suspicious"
    NSFW_IMAGE = "nsfw_image"
    SHOCK_IMAGE = "shock_image"
    SYMBOLS_IMAGE = "symbols_image"
    SUSPICIOUS_IMAGE = "suspicious_image"
