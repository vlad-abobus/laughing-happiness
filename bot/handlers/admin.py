from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import ChatPermissions, Message

from bot.context import AppContext
from bot.utils.parsing import extract_target_user_id, parse_command_args, parse_duration_seconds

logger = logging.getLogger(__name__)

router = Router(name="admin")


def _require_admin(message: Message, data: dict[str, Any]) -> bool:
    return bool(data.get("is_admin"))


async def _audit(
    ctx: AppContext,
    *,
    admin_id: int,
    chat_id: int | None,
    action: str,
    target_user_id: int | None,
    detail: str | None,
) -> None:
    await ctx.repo.log_admin_action(admin_id, action, chat_id, target_user_id, detail)
    line = (
        f"{datetime.now(tz=timezone.utc).isoformat()} "
        f"admin={admin_id} chat={chat_id} action={action} target={target_user_id} detail={detail!r}"
    )
    await ctx.admin_logger.log_line(line)


@router.message(Command("admins"))
async def cmd_admins(message: Message, ctx: AppContext) -> None:
    lines = ["<b>Администраторы (Telegram ID):</b>"]
    for aid in sorted(ctx.settings.admin_ids):
        lines.append(f"• <code>{aid}</code>")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("rules"))
async def cmd_rules(message: Message, ctx: AppContext) -> None:
    text = ctx.rules.community_rules_text or "Правила не заданы."
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("ban"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_ban(message: Message, ctx: AppContext, **data: Any) -> None:
    if not _require_admin(message, data):
        await message.reply("⛔️ Эта команда только для администраторов.")
        return
    _, args = parse_command_args(message.text or "")
    target = extract_target_user_id(message, args)
    if target is None:
        await message.reply("Использование: ответьте на сообщение или <code>/ban &lt;user_id&gt;</code>")
        return
    reason = " ".join(args[1:]) if len(args) > 1 else None
    try:
        await message.bot.ban_chat_member(message.chat.id, target)
    except Exception as e:
        await message.reply(f"Не удалось забанить: {e}")
        return
    await ctx.repo.add_chat_ban(message.chat.id, target, reason)
    await _audit(
        ctx,
        admin_id=message.from_user.id,
        chat_id=message.chat.id,
        action="ban",
        target_user_id=target,
        detail=reason,
    )
    await message.reply(f"Пользователь <code>{target}</code> забанен.", parse_mode="HTML")


@router.message(Command("mute"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_mute(message: Message, ctx: AppContext, **data: Any) -> None:
    if not _require_admin(message, data):
        await message.reply("⛔️ Эта команда только для администраторов.")
        return
    _, args = parse_command_args(message.text or "")
    target = extract_target_user_id(message, args)
    if target is None:
        await message.reply(
            "Использование: ответьте на сообщение и укажите длительность, например "
            "<code>/mute 30m</code> или <code>/mute 3600</code> (секунды), "
            "либо <code>/mute &lt;user_id&gt; 30m</code>"
        )
        return

    dur_token: str | None = None
    if message.reply_to_message:
        dur_token = args[0] if args else None
    else:
        dur_token = args[1] if len(args) > 1 else None

    if not dur_token:
        await message.reply("Укажите длительность мута, например <code>30m</code>.")
        return

    seconds = parse_duration_seconds(dur_token)
    if seconds is None:
        await message.reply("Не удалось разобрать длительность. Примеры: <code>10m</code>, <code>2h</code>.")
        return

    until_dt = datetime.now(tz=timezone.utc) + timedelta(seconds=seconds)
    until_ts = until_dt.timestamp()
    try:
        await message.bot.restrict_chat_member(
            message.chat.id,
            target,
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
        await message.reply(f"Не удалось замутить: {e}")
        return

    await ctx.repo.set_mute(message.chat.id, target, until_ts, reason="admin_mute")
    await _audit(
        ctx,
        admin_id=message.from_user.id,
        chat_id=message.chat.id,
        action="mute",
        target_user_id=target,
        detail=f"seconds={seconds}",
    )
    await message.reply(
        f"Пользователь <code>{target}</code> замьючен на <code>{seconds}</code> сек.",
        parse_mode="HTML",
    )


@router.message(Command("warn"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_warn(message: Message, ctx: AppContext, **data: Any) -> None:
    if not _require_admin(message, data):
        await message.reply("⛔️ Эта команда только для администраторов.")
        return
    _, args = parse_command_args(message.text or "")
    target = extract_target_user_id(message, args)
    if target is None:
        await message.reply("Использование: ответьте на сообщение или <code>/warn &lt;user_id&gt;</code>")
        return
    note: str | None
    if message.reply_to_message:
        note = " ".join(args).strip() or None
    else:
        note = " ".join(args[1:]).strip() if len(args) > 1 else None
    count = await ctx.repo.add_warning(message.chat.id, target, delta=1)
    await _audit(
        ctx,
        admin_id=message.from_user.id,
        chat_id=message.chat.id,
        action="warn",
        target_user_id=target,
        detail=note or None,
    )
    await message.reply(
        f"Выдано предупреждение пользователю <code>{target}</code>. Всего: <b>{count}</b>.",
        parse_mode="HTML",
    )


@router.message(Command("unwarn"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_unwarn(message: Message, ctx: AppContext, **data: Any) -> None:
    if not _require_admin(message, data):
        await message.reply("⛔️ Эта команда только для администраторов.")
        return
    _, args = parse_command_args(message.text or "")
    target = extract_target_user_id(message, args)
    if target is None:
        await message.reply("Использование: ответьте на сообщение или <code>/unwarn &lt;user_id&gt;</code>")
        return
    count = await ctx.repo.add_warning(message.chat.id, target, delta=-1)
    await _audit(
        ctx,
        admin_id=message.from_user.id,
        chat_id=message.chat.id,
        action="unwarn",
        target_user_id=target,
        detail=f"new_count={count}",
    )
    await message.reply(
        f"Снято одно предупреждение у <code>{target}</code>. Сейчас: <b>{count}</b>.",
        parse_mode="HTML",
    )


@router.message(Command("block"))
async def cmd_block_global(message: Message, ctx: AppContext, **data: Any) -> None:
    """Block user from using bot AI features (global)."""
    if not _require_admin(message, data):
        await message.reply("⛔️ Эта команда только для администраторов.")
        return
    _, args = parse_command_args(message.text or "")
    if not args:
        await message.reply("Использование: <code>/block &lt;user_id&gt;</code>")
        return
    try:
        uid = int(args[0])
    except ValueError:
        await message.reply("Некорректный user_id.")
        return
    reason = " ".join(args[1:]) if len(args) > 1 else None
    await ctx.repo.add_global_bot_block(uid, reason)
    await _audit(
        ctx,
        admin_id=message.from_user.id,
        chat_id=message.chat.id if message.chat else None,
        action="global_block",
        target_user_id=uid,
        detail=reason,
    )
    await message.reply(f"Пользователь <code>{uid}</code> заблокирован для функций бота.", parse_mode="HTML")


@router.message(Command("unblock"))
async def cmd_unblock_global(message: Message, ctx: AppContext, **data: Any) -> None:
    if not _require_admin(message, data):
        await message.reply("⛔️ Эта команда только для администраторов.")
        return
    _, args = parse_command_args(message.text or "")
    if not args:
        await message.reply("Использование: <code>/unblock &lt;user_id&gt;</code>")
        return
    try:
        uid = int(args[0])
    except ValueError:
        await message.reply("Некорректный user_id.")
        return
    await ctx.repo.remove_global_bot_block(uid)
    await _audit(
        ctx,
        admin_id=message.from_user.id,
        chat_id=message.chat.id if message.chat else None,
        action="global_unblock",
        target_user_id=uid,
        detail=None,
    )
    await message.reply(f"Пользователь <code>{uid}</code> разблокирован.", parse_mode="HTML")
