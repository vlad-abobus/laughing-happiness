from __future__ import annotations

import logging
from io import BytesIO
from typing import Any

from aiogram import F, Router
from aiogram.types import Message

from bot.context import AppContext
from bot.utils.parsing import parse_command_args

logger = logging.getLogger(__name__)

router = Router(name="group")


async def _welcome_enabled(ctx: AppContext, chat_id: int) -> bool:
    row = await ctx.repo.get_chat_settings(chat_id)
    if row is not None:
        return row.welcome_enabled
    return ctx.rules.welcome.enabled


@router.message(F.new_chat_members)
async def on_new_members(message: Message, ctx: AppContext) -> None:
    if message.chat.type not in {"group", "supergroup"}:
        return
    if not await _welcome_enabled(ctx, message.chat.id):
        return

    rules_text = ctx.rules.community_rules_text
    wcfg = ctx.rules.welcome
    row = await ctx.repo.get_chat_settings(message.chat.id)
    template = (row.welcome_template if row and row.welcome_template else None) or wcfg.template
    parse_mode = (row.welcome_parse_mode if row and row.welcome_parse_mode else None) or (
        wcfg.parse_mode or "HTML"
    )

    bot_me = await message.bot.me()
    for user in message.new_chat_members:
        if user.is_bot and user.id == bot_me.id:
            continue
        mention = user.mention_html() if user.username else f'<a href="tg://user?id={user.id}">{user.full_name}</a>'
        text = template.format(mention=mention, rules=rules_text, name=user.full_name or "")
        try:
            await message.answer(text, parse_mode=parse_mode, disable_web_page_preview=True)
        except Exception as e:
            logger.warning("welcome failed: %s", e)


@router.message(F.chat.type.in_({"group", "supergroup"}), F.photo)
async def on_group_photo(message: Message, ctx: AppContext, **data: Any) -> None:
    if not message.from_user or message.from_user.is_bot:
        return
    if data.get("is_admin"):
        return

    row = await ctx.repo.get_chat_settings(message.chat.id)
    if row and not row.moderation_enabled:
        return
    if not ctx.rules.moderation.enabled:
        return

    if await ctx.repo.is_chat_banned(message.chat.id, message.from_user.id):
        try:
            await message.delete()
        except Exception:
            pass
        return

    photo = message.photo[-1]
    try:
        buf = BytesIO()
        await message.bot.download(photo, destination=buf)
        raw = buf.getvalue()
    except Exception as e:
        logger.warning("photo download failed: %s", e)
        return

    viol, reason = await ctx.moderation.analyze_image(image_bytes=raw, mime="image/jpeg")
    if viol is None:
        return

    warn = ctx.rules.warning_text(viol.value)
    try:
        await message.delete()
    except Exception as e:
        logger.warning("delete photo message failed: %s", e)

    await ctx.moderation.record_violation_and_escalate(
        message.bot,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        violation=viol,
        message_id=message.message_id,
        warn_text=warn,
        reply_message_id=None,
    )


@router.message(F.chat.type.in_({"group", "supergroup"}), F.from_user.as_("fu"), ~F.from_user.is_bot)
async def on_group_message(message: Message, ctx: AppContext, **data: Any) -> None:
    if message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.id == ctx.bot_user_id:
            return

    content = message.text or message.caption
    if not content:
        return

    cmd, _ = parse_command_args(content)
    if cmd in {
        "/ban",
        "/mute",
        "/warn",
        "/unwarn",
        "/rules",
        "/admins",
        "/ai",
        "/block",
        "/unblock",
        "/start",
        "/help",
    }:
        return

    if data.get("is_admin"):
        return

    row = await ctx.repo.get_chat_settings(message.chat.id)
    if row and not row.moderation_enabled:
        return
    if not ctx.rules.moderation.enabled:
        return

    if await ctx.repo.is_chat_banned(message.chat.id, message.from_user.id):
        try:
            await message.delete()
        except Exception:
            pass
        return

    outcome = await ctx.moderation.analyze_text_message(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        text=content,
        is_admin=False,
    )
    if outcome.violation is None:
        return

    warn = ctx.rules.warning_text(outcome.violation.value)
    await ctx.moderation.record_violation_and_escalate(
        message.bot,
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        violation=outcome.violation,
        message_id=message.message_id,
        warn_text=warn,
        reply_message_id=message.message_id,
    )
