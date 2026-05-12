from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from aiogram import Bot
from aiogram.types import ChatPermissions

from bot.ai.openrouter import OpenRouterClient
from bot.config.rules import CommunityRules
from bot.database.repository import Repository
from bot.moderation.flood import FloodTracker
from bot.moderation.heuristics import heuristic_check
from bot.moderation.types import ViolationKind
from bot.utils.admin_log import AdminActionLogger

if TYPE_CHECKING:
    from bot.config.settings import Settings

logger = logging.getLogger(__name__)


def _map_ai_text_category(cat: str) -> ViolationKind | None:
    c = cat.lower().strip()
    mapping = {
        "spam": ViolationKind.SPAM,
        "flood": ViolationKind.FLOOD,
        "toxicity": ViolationKind.TOXICITY,
        "nsfw_text": ViolationKind.NSFW_TEXT,
        "suspicious": ViolationKind.SUSPICIOUS,
    }
    return mapping.get(c)


def _map_ai_image_category(cat: str) -> ViolationKind | None:
    c = cat.lower().strip()
    mapping = {
        "nsfw_image": ViolationKind.NSFW_IMAGE,
        "shock_image": ViolationKind.SHOCK_IMAGE,
        "forbidden_symbols": ViolationKind.SYMBOLS_IMAGE,
        "suspicious_image": ViolationKind.SUSPICIOUS_IMAGE,
    }
    return mapping.get(c)


@dataclass(slots=True)
class TextModerationOutcome:
    violation: ViolationKind | None
    detail: str | None = None


class ModerationService:
    """Coordinates heuristics, flood tracking, optional AI classification, and escalation."""

    def __init__(
        self,
        *,
        settings: Settings,
        rules: CommunityRules,
        repo: Repository,
        ai: OpenRouterClient,
        flood: FloodTracker,
        admin_logger: AdminActionLogger,
    ) -> None:
        self._settings = settings
        self._rules = rules
        self._repo = repo
        self._ai = ai
        self._flood = flood
        self._admin_logger = admin_logger

    async def analyze_text_message(
        self,
        *,
        chat_id: int,
        user_id: int,
        text: str | None,
        is_admin: bool,
    ) -> TextModerationOutcome:
        cfg = self._rules.moderation
        if not cfg.enabled:
            return TextModerationOutcome(None)

        if await self._repo.is_chat_banned(chat_id, user_id):
            return TextModerationOutcome(None)

        flood_violation = await self._flood.is_flood(
            chat_id,
            user_id,
            window_sec=cfg.flood_window_seconds,
            max_messages=cfg.flood_max_messages,
        )
        if flood_violation:
            return TextModerationOutcome(ViolationKind.FLOOD)

        h = heuristic_check(text, rules=cfg, is_admin=is_admin)
        if h is not None:
            return TextModerationOutcome(h)

        if cfg.enable_ai_text_moderation and text and len(text) >= 8 and not is_admin:
            try:
                r = await self._ai.moderate_text(text)
                if r.violation and r.categories:
                    for c in r.categories:
                        vk = _map_ai_text_category(c)
                        if vk is not None:
                            return TextModerationOutcome(vk, r.reason)
                    return TextModerationOutcome(
                        ViolationKind.SUSPICIOUS, r.reason or "ai_flag"
                    )
            except Exception as e:
                logger.warning("AI text moderation error: %s", e)

        return TextModerationOutcome(None)

    async def analyze_image(
        self, *, image_bytes: bytes, mime: str = "image/jpeg"
    ) -> tuple[ViolationKind | None, str | None]:
        cfg = self._rules.moderation
        if not cfg.enabled or not cfg.enable_ai_image_moderation:
            return None, None
        try:
            r = await self._ai.moderate_image(image_bytes, mime=mime)
            if not r.violation:
                return None, r.reason
            for c in r.categories:
                vk = _map_ai_image_category(c)
                if vk is not None:
                    return vk, r.reason
            return ViolationKind.SUSPICIOUS_IMAGE, r.reason
        except Exception as e:
            logger.warning("AI image moderation error: %s", e)
            return None, str(e)

    async def record_violation_and_escalate(
        self,
        bot: Bot,
        *,
        chat_id: int,
        user_id: int,
        violation: ViolationKind,
        message_id: int | None,
        warn_text: str,
        reply_message_id: int | None = None,
    ) -> None:
        await self._repo.log_violation(
            chat_id, user_id, violation.value, None, message_id
        )
        count = await self._repo.add_warning(chat_id, user_id, delta=1)
        esc = self._rules.escalation

        try:
            if reply_message_id:
                await bot.send_message(
                    chat_id,
                    f"{warn_text}\n\nПредупреждений: {count}/{esc.warnings_before_ban}",
                    reply_to_message_id=reply_message_id,
                )
            else:
                await bot.send_message(
                    chat_id,
                    f"{warn_text}\n\nПредупреждений: {count}/{esc.warnings_before_ban}",
                )
        except Exception as e:
            logger.warning("send warning failed: %s", e)

        if count >= esc.warnings_before_ban:
            try:
                await bot.ban_chat_member(chat_id, user_id)
            except Exception as e:
                logger.warning("ban failed: %s", e)
            await self._repo.add_chat_ban(chat_id, user_id, reason="auto_escalation")
            await self._admin_logger.log_line(
                f"auto_ban chat={chat_id} user={user_id} warnings={count}"
            )
            return

        if count >= esc.warnings_before_mute:
            until_dt = datetime.now(tz=timezone.utc) + timedelta(
                seconds=esc.mute_duration_seconds
            )
            until_ts = until_dt.timestamp()
            try:
                await bot.restrict_chat_member(
                    chat_id,
                    user_id,
                    permissions=ChatPermissions(
                        can_send_messages=False,
                        can_send_audios=False,
                        can_send_documents=False,
                        can_send_photos=False,
                        can_send_videos=False,
                        can_send_video_notes=False,
                        can_send_voice_notes=False,
                        can_send_polls=False,
                        can_send_other_messages=False,
                        can_add_web_page_previews=False,
                        can_change_info=False,
                        can_invite_users=False,
                        can_pin_messages=False,
                        can_manage_topics=False,
                    ),
                    until_date=until_dt,
                )
            except Exception as e:
                logger.warning("mute failed: %s", e)
            await self._repo.set_mute(
                chat_id, user_id, until_ts, reason="auto_escalation"
            )
            await self._admin_logger.log_line(
                f"auto_mute chat={chat_id} user={user_id} until={until_ts}"
            )
