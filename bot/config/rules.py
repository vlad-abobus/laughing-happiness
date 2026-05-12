from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WelcomeConfig:
    enabled: bool
    parse_mode: str | None
    template: str


@dataclass(frozen=True)
class EscalationConfig:
    warnings_before_mute: int
    warnings_before_ban: int
    mute_duration_seconds: int


@dataclass(frozen=True)
class ModerationRulesConfig:
    enabled: bool
    banned_words: tuple[str, ...]
    blocked_link_domains: tuple[str, ...]
    allow_links_for_admins: bool
    flood_window_seconds: int
    flood_max_messages: int
    spam_min_repeated_char: int
    spam_caps_ratio: float
    spam_min_len_for_caps_check: int
    enable_ai_text_moderation: bool
    enable_ai_image_moderation: bool


@dataclass(frozen=True)
class CommunityRules:
    community_rules_text: str
    welcome: WelcomeConfig
    warning_templates: dict[str, str]
    escalation: EscalationConfig
    moderation: ModerationRulesConfig

    def warning_text(self, key: str) -> str:
        return self.warning_templates.get(key) or self.warning_templates.get(
            "default", "⚠️ Нарушение правил."
        )


def _default_rules_path() -> Path:
    return Path(__file__).with_name("default_rules.json")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)  # type: ignore[arg-type]
        else:
            out[k] = v
    return out


def load_rules(rules_path: Path) -> CommunityRules:
    base = _read_json(_default_rules_path())
    if rules_path.exists():
        try:
            base = _merge(base, _read_json(rules_path))
        except OSError as e:
            logger.warning("Failed to read %s: %s — using defaults", rules_path, e)
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON in %s: %s — using defaults", rules_path, e)

    w = base.get("welcome", {}) or {}
    e = base.get("escalation", {}) or {}
    m = base.get("moderation", {}) or {}

    return CommunityRules(
        community_rules_text=str(base.get("community_rules_text", "")),
        welcome=WelcomeConfig(
            enabled=bool(w.get("enabled", True)),
            parse_mode=w.get("parse_mode"),
            template=str(
                w.get(
                    "template",
                    "Привет, {mention}!\\n\\n{rules}",
                )
            ),
        ),
        warning_templates=dict(base.get("warning_templates", {}) or {}),
        escalation=EscalationConfig(
            warnings_before_mute=int(e.get("warnings_before_mute", 3)),
            warnings_before_ban=int(e.get("warnings_before_ban", 6)),
            mute_duration_seconds=int(e.get("mute_duration_seconds", 3600)),
        ),
        moderation=ModerationRulesConfig(
            enabled=bool(m.get("enabled", True)),
            banned_words=tuple(str(x).lower() for x in (m.get("banned_words") or [])),
            blocked_link_domains=tuple(
                str(x).lower() for x in (m.get("blocked_link_domains") or [])
            ),
            allow_links_for_admins=bool(m.get("allow_links_for_admins", True)),
            flood_window_seconds=int(m.get("flood_window_seconds", 8)),
            flood_max_messages=int(m.get("flood_max_messages", 6)),
            spam_min_repeated_char=int(m.get("spam_min_repeated_char", 8)),
            spam_caps_ratio=float(m.get("spam_caps_ratio", 0.75)),
            spam_min_len_for_caps_check=int(m.get("spam_min_len_for_caps_check", 24)),
            enable_ai_text_moderation=bool(m.get("enable_ai_text_moderation", True)),
            enable_ai_image_moderation=bool(
                m.get("enable_ai_image_moderation", True)
            ),
        ),
    )
